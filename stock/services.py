"""Seul endroit qui modifie les quantités en stock.

Chaque fonction verrouille le lot (select_for_update), contrôle, met à jour
la quantité et écrit le mouvement correspondant, dans une transaction.
"""
from django.db import transaction

from .models import LotStock, MouvementStock


class StockError(Exception):
    """Opération de stock refusée ; le message s'affiche tel quel à l'utilisateur."""


def _verrouiller(lot_id):
    return LotStock.objects.select_for_update().select_related("medicament").get(pk=lot_id)


@transaction.atomic
def entrer(ligne_reception, utilisateur):
    """Entrée de stock d'une ligne de réception (RG04, RG05)."""
    if ligne_reception.mouvements.exists():
        raise StockError("Cette ligne de réception est déjà entrée en stock.")
    q = ligne_reception.quantite_recue
    if q <= 0:
        raise StockError("La quantité reçue doit être positive.")
    medicament = ligne_reception.ligne_achat.medicament
    lot, cree = LotStock.objects.select_for_update().get_or_create(
        medicament=medicament, numero_lot=ligne_reception.numero_lot,
        defaults={"date_peremption": ligne_reception.date_peremption},
    )
    if not cree and lot.date_peremption != ligne_reception.date_peremption:
        raise StockError(
            f"Le lot {lot.numero_lot} existe déjà avec la péremption "
            f"{lot.date_peremption:%d/%m/%Y} : vérifiez la date saisie.")
    lot.quantite_recue += q
    lot.quantite_disponible += q
    lot.save(update_fields=["quantite_recue", "quantite_disponible"])
    MouvementStock.objects.create(lot=lot, type=MouvementStock.Type.ENTREE, quantite=q,
                                  ligne_reception=ligne_reception, utilisateur=utilisateur)
    ligne_reception.lot = lot
    ligne_reception.save(update_fields=["lot"])
    return lot


@transaction.atomic
def sortir(lot, quantite, ligne_vente, utilisateur):
    """Sortie de stock d'une ligne de vente (RG06, RG07, RG08)."""
    if quantite <= 0:
        raise StockError("La quantité vendue doit être positive.")
    lot = _verrouiller(lot.pk)
    if lot.bloque:
        raise StockError(f"Le lot {lot.numero_lot} de {lot.medicament} est bloqué.")
    if lot.est_perime():
        raise StockError(f"Le lot {lot.numero_lot} de {lot.medicament} est périmé.")
    if lot.quantite_disponible < quantite:
        raise StockError(f"Stock insuffisant pour {lot.medicament} (lot {lot.numero_lot}) : "
                         f"{lot.quantite_disponible} disponible(s), {quantite} demandé(s).")
    lot.quantite_disponible -= quantite
    lot.save(update_fields=["quantite_disponible"])
    return MouvementStock.objects.create(lot=lot, type=MouvementStock.Type.SORTIE, quantite=-quantite,
                                         ligne_vente=ligne_vente, utilisateur=utilisateur)


@transaction.atomic
def annuler_sortie(ligne_vente, utilisateur, motif=""):
    """Opération compensatoire : remet en stock ce qu'une ligne vendue avait sorti (RG10)."""
    lot = _verrouiller(ligne_vente.lot_id)
    q = ligne_vente.quantite - ligne_vente.quantite_retournee_en_stock()
    if q <= 0:
        return None
    lot.quantite_disponible += q
    lot.save(update_fields=["quantite_disponible"])
    return MouvementStock.objects.create(lot=lot, type=MouvementStock.Type.ANNULATION, quantite=q,
                                         ligne_vente=ligne_vente, motif=motif, utilisateur=utilisateur)


@transaction.atomic
def reintegrer_retour(retour, utilisateur):
    lot = _verrouiller(retour.ligne_vente.lot_id)
    lot.quantite_disponible += retour.quantite
    lot.save(update_fields=["quantite_disponible"])
    return MouvementStock.objects.create(lot=lot, type=MouvementStock.Type.RETOUR,
                                         quantite=retour.quantite, retour=retour,
                                         motif=retour.motif, utilisateur=utilisateur)


@transaction.atomic
def corriger(lot, quantite_comptee, motif, utilisateur):
    """Inventaire physique : aligne le stock sur la quantité comptée."""
    if not motif.strip():
        raise StockError("Le motif de la correction est obligatoire.")
    if quantite_comptee < 0:
        raise StockError("La quantité comptée ne peut pas être négative.")
    lot = _verrouiller(lot.pk)
    ecart = quantite_comptee - lot.quantite_disponible
    if ecart == 0:
        return None
    lot.quantite_disponible = quantite_comptee
    lot.save(update_fields=["quantite_disponible"])
    return MouvementStock.objects.create(lot=lot, type=MouvementStock.Type.CORRECTION, quantite=ecart,
                                         motif=motif, utilisateur=utilisateur)


def repartir_fefo(medicament, quantite):
    """FEFO : découpe une quantité sur les lots vendables, péremption la plus proche d'abord.

    Renvoie une liste [(lot, quantité)]. Lève StockError si le stock vendable est insuffisant.
    """
    if quantite <= 0:
        raise StockError("La quantité doit être supérieure à zéro.")
    if not medicament.est_actif:
        raise StockError(f"{medicament} est archivé et ne peut pas être vendu.")
    reste, repartition = quantite, []
    for lot in medicament.lots_vendables():
        if reste == 0:
            break
        pris = min(reste, lot.quantite_disponible)
        repartition.append((lot, pris))
        reste -= pris
    if reste:
        raise StockError(f"Stock vendable insuffisant pour {medicament} : "
                         f"{quantite - reste} disponible(s), {quantite} demandé(s).")
    return repartition
