from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.db.models import Q, Sum
from django.urls import reverse
from django.utils import timezone

from rapports.templatetags.pharmagest import format_ar
from utilisateurs.models import JournalAudit
from utilisateurs.utils import prochain_numero


class VenteError(Exception):
    pass


class Vente(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = "brouillon", "En cours"
        VALIDEE = "validee", "Validée"
        ANNULEE = "annulee", "Annulée"

    numero = models.CharField("numéro", max_length=20, unique=True, null=True, blank=True,
                              editable=False)
    client = models.ForeignKey("clients.Client", on_delete=models.PROTECT, null=True, blank=True,
                               related_name="ventes")
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.BROUILLON)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    caissier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                 related_name="ventes")
    cree_le = models.DateTimeField(auto_now_add=True)
    valide_le = models.DateTimeField(null=True, blank=True, db_index=True)
    annule_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True,
                                   blank=True, related_name="ventes_annulees")
    annule_le = models.DateTimeField(null=True, blank=True)
    motif_annulation = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-cree_le"]
        permissions = [
            ("valider_vente", "Valider une vente (sortie de stock)"),
            ("annuler_vente", "Annuler une vente validée"),
        ]

    def __str__(self):
        return self.numero or f"Vente en cours n° {self.pk}"

    def get_absolute_url(self):
        if self.statut == self.Statut.BROUILLON:
            return reverse("ventes:caisse", args=[self.pk])
        return reverse("ventes:detail", args=[self.pk])

    # ----- Panier -----
    def _verifier_brouillon(self):
        if self.statut != self.Statut.BROUILLON:
            raise VenteError("Cette vente est déjà clôturée : elle ne peut plus être modifiée.")

    def calculer_total(self):
        return self.lignes.aggregate(t=Sum("sous_total"))["t"] or Decimal("0")

    @transaction.atomic
    def ajouter(self, medicament, quantite):
        """Ajoute un médicament ; FEFO choisit les lots (une ligne par lot)."""
        from stock.services import StockError, repartir_fefo

        self._verifier_brouillon()
        deja = self.lignes.filter(medicament=medicament).aggregate(t=Sum("quantite"))["t"] or 0
        try:
            repartition = repartir_fefo(medicament, deja + quantite)
        except StockError as e:
            raise VenteError(str(e)) from e
        self.lignes.filter(medicament=medicament).delete()
        for lot, q in repartition:
            LigneVente.objects.create(vente=self, medicament=medicament, lot=lot, quantite=q,
                                      prix_unitaire=medicament.prix_vente,
                                      sous_total=q * medicament.prix_vente)
        self.total = self.calculer_total()
        self.save(update_fields=["total"])

    @transaction.atomic
    def retirer(self, medicament):
        self._verifier_brouillon()
        self.lignes.filter(medicament=medicament).delete()
        self.total = self.calculer_total()
        self.save(update_fields=["total"])

    # ----- Paiement -----
    def montant_paye(self):
        return self.paiements.filter(statut=Paiement.Statut.CONFIRME).aggregate(
            t=Sum("montant"))["t"] or Decimal("0")

    def reste_a_payer(self):
        return max(self.total - self.montant_paye(), Decimal("0"))

    def monnaie_a_rendre(self):
        return max(self.montant_paye() - self.total, Decimal("0"))

    # ----- Validation (cahier 4.8, séquence 8.1) -----
    @transaction.atomic
    def valider(self, utilisateur):
        from stock.services import StockError, sortir

        vente = Vente.objects.select_for_update().get(pk=self.pk)
        if vente.statut != self.Statut.BROUILLON:
            raise VenteError("Cette vente est déjà validée : aucune nouvelle sortie de stock.")
        lignes = list(vente.lignes.select_related("lot", "medicament"))
        if not lignes:
            raise VenteError("Le panier est vide.")
        vente.total = vente.calculer_total()
        if vente.montant_paye() < vente.total:
            raise VenteError(f"Paiement insuffisant : {format_ar(vente.montant_paye())} confirmés "
                             f"pour un total de {format_ar(vente.total)}.")
        for ligne in lignes:
            try:
                sortir(ligne.lot, ligne.quantite, ligne, utilisateur)
            except StockError as e:
                raise VenteError(str(e)) from e
        vente.numero = prochain_numero(Vente, "V", largeur=6)
        vente.statut, vente.valide_le = self.Statut.VALIDEE, timezone.now()
        vente.save(update_fields=["numero", "statut", "valide_le", "total"])
        JournalAudit.enregistrer(utilisateur, "VALIDER", vente, total=vente.total)
        self.refresh_from_db()

    @transaction.atomic
    def annuler(self, utilisateur, motif):
        """Opération compensatoire : la vente reste, le stock est remis (RG10)."""
        from stock.services import annuler_sortie

        if not motif.strip():
            raise VenteError("Le motif d'annulation est obligatoire.")
        vente = Vente.objects.select_for_update().get(pk=self.pk)
        if vente.statut != self.Statut.VALIDEE:
            raise VenteError("Seule une vente validée peut être annulée.")
        if RetourVente.objects.filter(ligne_vente__vente=vente, statut=RetourVente.Statut.DEMANDE).exists():
            raise VenteError("Traitez d'abord les retours en attente sur cette vente.")
        for ligne in vente.lignes.all():
            annuler_sortie(ligne, utilisateur, motif=motif)
        vente.statut, vente.annule_par, vente.annule_le = self.Statut.ANNULEE, utilisateur, timezone.now()
        vente.motif_annulation = motif
        vente.save(update_fields=["statut", "annule_par", "annule_le", "motif_annulation"])
        JournalAudit.enregistrer(utilisateur, "ANNULER", vente, motif=motif)
        self.refresh_from_db()


class LigneVente(models.Model):
    vente = models.ForeignKey(Vente, on_delete=models.CASCADE, related_name="lignes")
    medicament = models.ForeignKey("medicaments.Medicament", on_delete=models.PROTECT,
                                   related_name="lignes_vente")
    lot = models.ForeignKey("stock.LotStock", on_delete=models.PROTECT, related_name="lignes_vente")
    quantite = models.PositiveIntegerField("quantité")
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    sous_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["id"]
        verbose_name = "ligne de vente"
        constraints = [
            models.CheckConstraint(condition=Q(quantite__gt=0), name="quantite_vendue_positive"),
        ]

    def __str__(self):
        return f"{self.medicament} × {self.quantite}"

    def quantite_retournee(self):
        return self.retours.exclude(statut=RetourVente.Statut.REFUSE).aggregate(
            t=Sum("quantite"))["t"] or 0

    def quantite_retournee_en_stock(self):
        return self.retours.filter(statut=RetourVente.Statut.VALIDE, remise_en_stock=True).aggregate(
            t=Sum("quantite"))["t"] or 0

    def quantite_retournable(self):
        return self.quantite - self.quantite_retournee()


class Paiement(models.Model):
    class Mode(models.TextChoices):
        ESPECES = "especes", "Espèces"
        MOBILE_MONEY = "mobile_money", "Mobile money"
        AUTRE = "autre", "Autre (carte, chèque…)"

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        CONFIRME = "confirme", "Confirmé"
        ECHOUE = "echoue", "Échoué"

    vente = models.ForeignKey(Vente, on_delete=models.CASCADE, related_name="paiements")
    mode = models.CharField(max_length=15, choices=Mode.choices, default=Mode.ESPECES)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField("référence de transaction", max_length=100, blank=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE)
    encaisse_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                     related_name="paiements")
    cree_le = models.DateTimeField(auto_now_add=True)
    confirme_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["cree_le"]
        constraints = [
            models.CheckConstraint(condition=Q(montant__gt=0), name="paiement_positif"),
        ]

    def __str__(self):
        return f"{self.get_mode_display()} {format_ar(self.montant)} ({self.get_statut_display()})"

    def confirmer(self):
        """Un paiement électronique n'est confirmé qu'après vérification de sa référence."""
        if self.mode != self.Mode.ESPECES and not self.reference.strip():
            raise VenteError("Saisissez la référence de la transaction avant de la confirmer.")
        self.statut, self.confirme_le = self.Statut.CONFIRME, timezone.now()
        self.save(update_fields=["statut", "confirme_le"])


class RetourVente(models.Model):
    class Statut(models.TextChoices):
        DEMANDE = "demande", "Demandé"
        VALIDE = "valide", "Validé"
        REFUSE = "refuse", "Refusé"

    ligne_vente = models.ForeignKey(LigneVente, on_delete=models.PROTECT, related_name="retours")
    quantite = models.PositiveIntegerField("quantité retournée")
    motif = models.CharField(max_length=255)
    remise_en_stock = models.BooleanField("remettre en stock", default=False)
    montant_rembourse = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.DEMANDE)
    demande_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="retours_demandes")
    demande_le = models.DateTimeField(auto_now_add=True)
    valide_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True,
                                   blank=True, related_name="retours_traites")
    valide_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-demande_le"]
        verbose_name = "retour de vente"
        verbose_name_plural = "retours de vente"
        permissions = [("valider_retour", "Valider ou refuser un retour")]
        constraints = [
            models.CheckConstraint(condition=Q(quantite__gt=0), name="quantite_retour_positive"),
        ]

    def __str__(self):
        return f"Retour {self.pk} — {self.ligne_vente.medicament} × {self.quantite}"

    @classmethod
    @transaction.atomic
    def demander(cls, ligne_vente, quantite, motif, utilisateur):
        ligne = LigneVente.objects.select_for_update().select_related("vente").get(pk=ligne_vente.pk)
        if ligne.vente.statut != Vente.Statut.VALIDEE:
            raise VenteError("Un retour ne concerne qu'une vente validée.")
        if quantite <= 0 or quantite > ligne.quantite_retournable():
            raise VenteError(f"Quantité invalide : {ligne.quantite_retournable()} unité(s) retournable(s).")
        if not motif.strip():
            raise VenteError("Le motif du retour est obligatoire.")
        retour = cls.objects.create(ligne_vente=ligne, quantite=quantite, motif=motif,
                                    demande_par=utilisateur)
        JournalAudit.enregistrer(utilisateur, "DEMANDER_RETOUR", retour, vente=ligne.vente.numero)
        return retour

    @transaction.atomic
    def valider(self, utilisateur, remise_en_stock):
        from stock.services import reintegrer_retour

        retour = RetourVente.objects.select_for_update().select_related("ligne_vente__lot").get(pk=self.pk)
        if retour.statut != self.Statut.DEMANDE:
            raise VenteError("Ce retour a déjà été traité.")
        lot = retour.ligne_vente.lot
        if remise_en_stock and (lot.est_perime() or lot.bloque):
            raise VenteError("Le lot d'origine est périmé ou bloqué : le produit ne peut pas être "
                             "remis en stock. Validez sans remise en stock.")
        retour.remise_en_stock = remise_en_stock
        retour.montant_rembourse = retour.quantite * retour.ligne_vente.prix_unitaire
        retour.statut, retour.valide_par, retour.valide_le = self.Statut.VALIDE, utilisateur, timezone.now()
        retour.save()
        if remise_en_stock:
            reintegrer_retour(retour, utilisateur)
        JournalAudit.enregistrer(utilisateur, "VALIDER_RETOUR", retour,
                                 rembourse=retour.montant_rembourse, remis_en_stock=remise_en_stock)
        self.refresh_from_db()

    @transaction.atomic
    def refuser(self, utilisateur):
        retour = RetourVente.objects.select_for_update().get(pk=self.pk)
        if retour.statut != self.Statut.DEMANDE:
            raise VenteError("Ce retour a déjà été traité.")
        retour.statut, retour.valide_par, retour.valide_le = self.Statut.REFUSE, utilisateur, timezone.now()
        retour.save(update_fields=["statut", "valide_par", "valide_le"])
        JournalAudit.enregistrer(utilisateur, "REFUSER_RETOUR", retour)
        self.refresh_from_db()
