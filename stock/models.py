from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


class LotStock(models.Model):
    medicament = models.ForeignKey("medicaments.Medicament", on_delete=models.PROTECT,
                                   related_name="lots", verbose_name="médicament")
    numero_lot = models.CharField("numéro de lot", max_length=50)
    date_peremption = models.DateField("date de péremption")
    quantite_recue = models.PositiveIntegerField("quantité reçue", default=0)
    quantite_disponible = models.IntegerField("quantité disponible", default=0)
    bloque = models.BooleanField("bloqué", default=False)
    motif_blocage = models.CharField("motif de blocage", max_length=255, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date_peremption", "id"]
        verbose_name = "lot"
        permissions = [
            ("corriger_stock", "Corriger le stock (inventaire)"),
            ("bloquer_lot", "Bloquer ou débloquer un lot"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["medicament", "numero_lot"], name="lot_unique_par_medicament"),
            models.CheckConstraint(condition=Q(quantite_disponible__gte=0), name="stock_jamais_negatif"),
        ]

    def __str__(self):
        return f"{self.medicament} — lot {self.numero_lot}"

    def get_absolute_url(self):
        return reverse("stock:lot", args=[self.pk])

    def jours_avant_peremption(self):
        return (self.date_peremption - timezone.localdate()).days

    def est_perime(self):
        return self.date_peremption < timezone.localdate()

    def est_proche_peremption(self, jours=None):
        if jours is None:
            from utilisateurs.models import ParametrePharmacie
            jours = ParametrePharmacie.courant().jours_alerte_peremption
        return not self.est_perime() and self.jours_avant_peremption() <= jours

    def est_vendable(self):
        """RG08 : un lot périmé, bloqué ou vide n'est jamais proposé à la vente."""
        return (not self.bloque and not self.est_perime() and self.quantite_disponible > 0
                and self.medicament.est_actif)

    def etat(self):
        if self.bloque:
            return "bloque", "Bloqué"
        if self.est_perime():
            return "perime", "Périmé"
        if self.quantite_disponible <= 0:
            return "epuise", "Épuisé"
        if self.est_proche_peremption():
            return "proche", "Péremption proche"
        return "ok", "Vendable"


class MouvementStock(models.Model):
    """Journal de toutes les entrées et sorties (RG05, RG06, RG09).

    La somme des quantités d'un lot est toujours égale à sa quantité disponible.
    """

    class Type(models.TextChoices):
        ENTREE = "entree", "Entrée (réception)"
        SORTIE = "sortie", "Sortie (vente)"
        RETOUR = "retour", "Retour client"
        CORRECTION = "correction", "Correction d'inventaire"
        ANNULATION = "annulation", "Annulation de vente"

    lot = models.ForeignKey(LotStock, on_delete=models.PROTECT, related_name="mouvements")
    type = models.CharField(max_length=12, choices=Type.choices)
    quantite = models.IntegerField("quantité")
    ligne_reception = models.ForeignKey("achats.LigneReception", on_delete=models.PROTECT,
                                        null=True, blank=True, related_name="mouvements")
    ligne_vente = models.ForeignKey("ventes.LigneVente", on_delete=models.PROTECT,
                                    null=True, blank=True, related_name="mouvements")
    retour = models.ForeignKey("ventes.RetourVente", on_delete=models.PROTECT,
                               null=True, blank=True, related_name="mouvements")
    motif = models.CharField(max_length=255, blank=True)
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="mouvements_stock")
    date = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "mouvement de stock"
        verbose_name_plural = "mouvements de stock"
        constraints = [
            models.CheckConstraint(condition=~Q(quantite=0), name="mouvement_non_nul"),
            models.UniqueConstraint(fields=["ligne_reception"], condition=Q(ligne_reception__isnull=False),
                                    name="une_entree_par_ligne_reception"),
            models.UniqueConstraint(fields=["ligne_vente", "type"], condition=Q(ligne_vente__isnull=False),
                                    name="une_sortie_par_ligne_vente"),
        ]

    def __str__(self):
        return f"{self.get_type_display()} {self.quantite:+d} — {self.lot}"
