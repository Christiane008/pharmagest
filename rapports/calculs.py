"""Indicateurs calculés à partir des données réelles (cahier 4.10)."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from achats.models import ReceptionAchat
from medicaments.models import Medicament
from stock.models import LotStock
from stock.views import medicaments_avec_stock
from utilisateurs.models import ParametrePharmacie
from ventes.models import LigneVente, Paiement, RetourVente, Vente


def ventes_validees(debut, fin):
    """Ventes validées et non annulées sur la période (dates incluses)."""
    return Vente.objects.filter(statut=Vente.Statut.VALIDEE,
                                valide_le__date__gte=debut, valide_le__date__lte=fin)


def chiffre_affaires(debut, fin):
    return ventes_validees(debut, fin).aggregate(t=Sum("total"))["t"] or Decimal("0")


def remboursements(debut, fin):
    return RetourVente.objects.filter(statut=RetourVente.Statut.VALIDE, valide_le__date__gte=debut,
                                      valide_le__date__lte=fin).aggregate(
        t=Sum("montant_rembourse"))["t"] or Decimal("0")


def cout_ligne(ligne):
    """Coût d'achat réel du lot vendu (prix de la commande qui l'a fait entrer)."""
    lr = ligne.lot.lignes_reception.select_related("ligne_achat").first()
    prix = lr.ligne_achat.prix_achat_unitaire if lr else ligne.medicament.prix_achat
    return prix * ligne.quantite


def marge_commerciale(debut, fin):
    lignes = LigneVente.objects.filter(vente__in=ventes_validees(debut, fin)).select_related(
        "lot", "medicament")
    ca = sum((l.sous_total for l in lignes), Decimal("0"))
    cout = sum((cout_ligne(l) for l in lignes), Decimal("0"))
    return ca - cout


def encaissements_par_mode(debut, fin):
    """Paiements confirmés des ventes validées, monnaie rendue déduite des espèces."""
    ventes = ventes_validees(debut, fin)
    par_mode = {m.label: Decimal("0") for m in Paiement.Mode}
    for v in ventes.prefetch_related("paiements"):
        rendu = v.monnaie_a_rendre()
        for p in v.paiements.all():
            if p.statut == Paiement.Statut.CONFIRME:
                par_mode[p.get_mode_display()] += p.montant
        par_mode[Paiement.Mode.ESPECES.label] -= rendu
    return par_mode


def achats_recus(debut, fin):
    recs = ReceptionAchat.objects.filter(statut=ReceptionAchat.Statut.VALIDEE, recu_le__date__gte=debut,
                                         recu_le__date__lte=fin).prefetch_related("lignes__ligne_achat")
    return sum((r.total() for r in recs), Decimal("0")), recs.count()


def ventes_par_jour(debut, fin):
    rows = (ventes_validees(debut, fin).annotate(jour=TruncDate("valide_le"))
            .values("jour").annotate(total=Sum("total"), nb=Count("id")).order_by("jour"))
    par_jour = {r["jour"]: r for r in rows}
    jours, j = [], debut
    while j <= fin:
        r = par_jour.get(j)
        jours.append({"jour": j, "total": float(r["total"]) if r else 0, "nb": r["nb"] if r else 0})
        j += timedelta(days=1)
    return jours


def top_produits(debut, fin, n=10):
    return (LigneVente.objects.filter(vente__in=ventes_validees(debut, fin))
            .values("medicament__nom_commercial", "medicament__dosage")
            .annotate(quantite=Sum("quantite"), montant=Sum("sous_total"))
            .order_by("-quantite")[:n])


def alertes_stock():
    return medicaments_avec_stock().filter(stock_vendable__lte=F("seuil_alerte")).order_by("stock_vendable")


def lots_a_surveiller():
    aujourdhui = timezone.localdate()
    jours = ParametrePharmacie.courant().jours_alerte_peremption
    base = LotStock.objects.filter(quantite_disponible__gt=0).select_related("medicament")
    return {
        "perimes": base.filter(date_peremption__lt=aujourdhui).order_by("date_peremption"),
        "proches": base.filter(date_peremption__gte=aujourdhui,
                               date_peremption__lte=aujourdhui + timedelta(days=jours)).order_by("date_peremption"),
        "jours": jours,
    }


def indicateurs_du_jour():
    aujourdhui = timezone.localdate()
    lots = lots_a_surveiller()
    return {
        "medicaments_actifs": Medicament.objects.filter(statut="actif").count(),
        "ca_jour": chiffre_affaires(aujourdhui, aujourdhui),
        "nb_ventes_jour": ventes_validees(aujourdhui, aujourdhui).count(),
        "stocks_faibles": alertes_stock().count(),
        "peremptions_proches": lots["proches"].count(),
        "lots_perimes": lots["perimes"].count(),
    }
