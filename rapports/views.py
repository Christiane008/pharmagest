from datetime import date, timedelta

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from achats.models import CommandeAchat, ReceptionAchat
from stock.views import medicaments_avec_stock
from ventes.models import Vente

from . import calculs, pdf


def periode(request, jours_defaut=30):
    fin = timezone.localdate()
    debut = fin - timedelta(days=jours_defaut - 1)
    try:
        if request.GET.get("debut"):
            debut = date.fromisoformat(request.GET["debut"])
        if request.GET.get("fin"):
            fin = date.fromisoformat(request.GET["fin"])
    except ValueError:
        pass
    if debut > fin:
        debut, fin = fin, debut
    return debut, fin


@login_required
def accueil(request):
    return redirect("tableau_de_bord")


@login_required
@permission_required("utilisateurs.voir_tableau_de_bord", raise_exception=True)
def tableau_de_bord(request):
    u = request.user
    debut, fin = periode(request)
    ctx = {"debut": debut, "fin": fin, "kpi": calculs.indicateurs_du_jour()}
    if u.has_perm("stock.view_lotstock"):
        ctx["alertes"] = calculs.alertes_stock()[:8]
        ctx["lots"] = calculs.lots_a_surveiller()
    if u.has_perm("utilisateurs.voir_statistiques"):
        ca, remb = calculs.chiffre_affaires(debut, fin), calculs.remboursements(debut, fin)
        achats, nb_receptions = calculs.achats_recus(debut, fin)
        ctx.update({
            "stats": True, "ca": ca, "remboursements": remb, "ca_net": ca - remb,
            "marge": calculs.marge_commerciale(debut, fin),
            "encaissements": calculs.encaissements_par_mode(debut, fin),
            "achats": achats, "nb_receptions": nb_receptions,
            "top": calculs.top_produits(debut, fin),
            "serie": calculs.ventes_par_jour(debut, fin),
        })
    return render(request, "rapports/tableau_de_bord.html", ctx)


@login_required
@permission_required("utilisateurs.voir_rapports", raise_exception=True)
def rapports(request):
    debut, fin = periode(request)
    return render(request, "rapports/rapports.html", {"debut": debut, "fin": fin})


# ---------- PDF ----------
@login_required
@permission_required("ventes.view_vente", raise_exception=True)
def recu_pdf(request, pk):
    vente = get_object_or_404(Vente.objects.exclude(statut="brouillon"), pk=pk)
    return pdf.document_vente(vente, facture=False)


@login_required
@permission_required("ventes.view_vente", raise_exception=True)
def facture_pdf(request, pk):
    vente = get_object_or_404(Vente.objects.exclude(statut="brouillon"), pk=pk)
    return pdf.document_vente(vente, facture=True)


@login_required
@permission_required("achats.view_commandeachat", raise_exception=True)
def bon_commande_pdf(request, pk):
    return pdf.bon_commande(get_object_or_404(CommandeAchat, pk=pk))


@login_required
@permission_required("achats.view_receptionachat", raise_exception=True)
def bon_reception_pdf(request, pk):
    return pdf.bon_reception(get_object_or_404(ReceptionAchat, pk=pk))


@login_required
@permission_required("utilisateurs.voir_rapports", raise_exception=True)
def rapport_stock_pdf(request):
    return pdf.rapport_stock(medicaments_avec_stock().order_by("nom_commercial"))


@login_required
@permission_required("utilisateurs.voir_rapports", raise_exception=True)
def rapport_peremptions_pdf(request):
    return pdf.rapport_peremptions(calculs.lots_a_surveiller())


@login_required
@permission_required(["utilisateurs.voir_rapports", "ventes.view_vente"], raise_exception=True)
def rapport_ventes_pdf(request):
    debut, fin = periode(request)
    ventes = calculs.ventes_validees(debut, fin).select_related("client", "caissier").order_by("valide_le")
    return pdf.rapport_ventes(debut, fin, ventes, calculs.chiffre_affaires(debut, fin),
                              calculs.remboursements(debut, fin), calculs.marge_commerciale(debut, fin),
                              calculs.encaissements_par_mode(debut, fin))


@login_required
@permission_required(["utilisateurs.voir_rapports", "achats.view_commandeachat"], raise_exception=True)
def rapport_achats_pdf(request):
    debut, fin = periode(request)
    recs = (ReceptionAchat.objects.filter(statut="validee", recu_le__date__gte=debut, recu_le__date__lte=fin)
            .select_related("commande__fournisseur").prefetch_related("lignes__ligne_achat").order_by("recu_le"))
    total, _ = calculs.achats_recus(debut, fin)
    return pdf.rapport_achats(debut, fin, recs, total)
