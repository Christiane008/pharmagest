from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.db.models import Q, Sum
from django.urls import reverse
from django.utils import timezone

from utilisateurs.models import JournalAudit
from utilisateurs.utils import prochain_numero


class AchatError(Exception):
    pass


class CommandeAchat(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = "brouillon", "Brouillon"
        COMMANDEE = "commandee", "Commandée"
        PARTIELLE = "partielle", "Partiellement réceptionnée"
        COMPLETE = "complete", "Entièrement réceptionnée"
        ANNULEE = "annulee", "Annulée"

    numero = models.CharField("numéro", max_length=20, unique=True, editable=False)
    fournisseur = models.ForeignKey("fournisseurs.Fournisseur", on_delete=models.PROTECT,
                                    related_name="commandes")
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.BROUILLON)
    notes = models.TextField(blank=True)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                 related_name="commandes_creees")
    cree_le = models.DateTimeField(auto_now_add=True)
    valide_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   null=True, blank=True, related_name="commandes_validees")
    valide_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "commande d'achat"
        verbose_name_plural = "commandes d'achat"
        permissions = [("valider_commande", "Valider ou annuler une commande d'achat")]

    def __str__(self):
        return self.numero

    def get_absolute_url(self):
        return reverse("achats:commande", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.numero:
            with transaction.atomic():
                self.numero = prochain_numero(CommandeAchat, "CA")
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    @property
    def est_modifiable(self):
        return self.statut == self.Statut.BROUILLON

    @property
    def peut_etre_receptionnee(self):
        return self.statut in (self.Statut.COMMANDEE, self.Statut.PARTIELLE)

    def total(self):
        return sum((l.montant() for l in self.lignes.all()), Decimal("0"))

    def montant_recu(self):
        return sum((l.quantite_recue() * l.prix_achat_unitaire for l in self.lignes.all()), Decimal("0"))

    @transaction.atomic
    def valider(self, utilisateur):
        cmd = CommandeAchat.objects.select_for_update().get(pk=self.pk)
        if cmd.statut != self.Statut.BROUILLON:
            raise AchatError("Seule une commande en brouillon peut être validée.")
        if not cmd.lignes.exists():
            raise AchatError("La commande ne contient aucune ligne.")
        cmd.statut, cmd.valide_par, cmd.valide_le = self.Statut.COMMANDEE, utilisateur, timezone.now()
        cmd.save(update_fields=["statut", "valide_par", "valide_le"])
        JournalAudit.enregistrer(utilisateur, "VALIDER", cmd, total=cmd.total())
        self.refresh_from_db()

    @transaction.atomic
    def annuler(self, utilisateur):
        cmd = CommandeAchat.objects.select_for_update().get(pk=self.pk)
        if cmd.statut not in (self.Statut.BROUILLON, self.Statut.COMMANDEE):
            raise AchatError("Une commande déjà réceptionnée, même en partie, ne peut pas être annulée.")
        if cmd.receptions.filter(statut=ReceptionAchat.Statut.VALIDEE).exists():
            raise AchatError("Cette commande a des réceptions validées.")
        cmd.statut = self.Statut.ANNULEE
        cmd.save(update_fields=["statut"])
        cmd.receptions.filter(statut=ReceptionAchat.Statut.BROUILLON).delete()
        JournalAudit.enregistrer(utilisateur, "ANNULER", cmd)
        self.refresh_from_db()

    def mettre_a_jour_statut(self):
        lignes = list(self.lignes.all())
        recu = [l.quantite_recue() for l in lignes]
        if all(r >= l.quantite_commandee for r, l in zip(recu, lignes)):
            self.statut = self.Statut.COMPLETE
        elif any(recu):
            self.statut = self.Statut.PARTIELLE
        self.save(update_fields=["statut"])


class LigneAchat(models.Model):
    commande = models.ForeignKey(CommandeAchat, on_delete=models.CASCADE, related_name="lignes")
    medicament = models.ForeignKey("medicaments.Medicament", on_delete=models.PROTECT,
                                   related_name="lignes_achat", verbose_name="médicament")
    quantite_commandee = models.PositiveIntegerField("quantité")
    prix_achat_unitaire = models.DecimalField("prix d'achat unitaire (Ar)", max_digits=10,
                                              decimal_places=2)

    class Meta:
        verbose_name = "ligne de commande"
        constraints = [
            models.UniqueConstraint(fields=["commande", "medicament"], name="un_medicament_par_commande"),
            models.CheckConstraint(condition=Q(quantite_commandee__gt=0), name="quantite_commandee_positive"),
            models.CheckConstraint(condition=Q(prix_achat_unitaire__gt=0), name="prix_achat_ligne_positif"),
        ]

    def __str__(self):
        return f"{self.medicament} × {self.quantite_commandee}"

    def montant(self):
        return self.quantite_commandee * self.prix_achat_unitaire

    def quantite_recue(self):
        return self.receptions.filter(reception__statut=ReceptionAchat.Statut.VALIDEE).aggregate(
            t=Sum("quantite_recue"))["t"] or 0

    def reste_a_recevoir(self):
        return max(self.quantite_commandee - self.quantite_recue(), 0)


class ReceptionAchat(models.Model):
    class Statut(models.TextChoices):
        BROUILLON = "brouillon", "Brouillon"
        VALIDEE = "validee", "Validée"

    numero = models.CharField("numéro", max_length=20, unique=True, editable=False)
    commande = models.ForeignKey(CommandeAchat, on_delete=models.PROTECT, related_name="receptions")
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.BROUILLON)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                 related_name="receptions_creees")
    cree_le = models.DateTimeField(auto_now_add=True)
    recu_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                 null=True, blank=True, related_name="receptions_validees")
    recu_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "réception"
        permissions = [("valider_reception", "Valider une réception (entrée en stock)")]

    def __str__(self):
        return self.numero

    def get_absolute_url(self):
        return reverse("achats:reception", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.numero:
            with transaction.atomic():
                self.numero = prochain_numero(ReceptionAchat, "BR")
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    def total(self):
        return sum((l.quantite_recue * l.ligne_achat.prix_achat_unitaire for l in self.lignes.all()),
                   Decimal("0"))

    @transaction.atomic
    def valider(self, utilisateur):
        """Entrée en stock, une seule fois (RG04, RG05). Tout ou rien."""
        from stock import services

        rec = ReceptionAchat.objects.select_for_update().get(pk=self.pk)
        if rec.statut != self.Statut.BROUILLON:
            raise AchatError("Cette réception est déjà validée : le stock n'a pas été modifié.")
        commande = CommandeAchat.objects.select_for_update().get(pk=rec.commande_id)
        if not commande.peut_etre_receptionnee:
            raise AchatError("La commande n'est pas dans un état qui permet la réception.")
        lignes = list(rec.lignes.select_related("ligne_achat__medicament"))
        if not lignes:
            raise AchatError("La réception ne contient aucune ligne.")
        for lr in lignes:
            if lr.quantite_recue > lr.ligne_achat.reste_a_recevoir():
                raise AchatError(f"{lr.ligne_achat.medicament} : {lr.quantite_recue} reçu(s) pour "
                                 f"{lr.ligne_achat.reste_a_recevoir()} restant(s) à recevoir.")
            try:
                services.entrer(lr, utilisateur)
            except services.StockError as e:
                raise AchatError(str(e)) from e
        rec.statut, rec.recu_par, rec.recu_le = self.Statut.VALIDEE, utilisateur, timezone.now()
        rec.save(update_fields=["statut", "recu_par", "recu_le"])
        commande.mettre_a_jour_statut()
        JournalAudit.enregistrer(utilisateur, "RECEPTIONNER", rec, commande=commande.numero,
                                 lignes=len(lignes))
        self.refresh_from_db()


class LigneReception(models.Model):
    reception = models.ForeignKey(ReceptionAchat, on_delete=models.CASCADE, related_name="lignes")
    ligne_achat = models.ForeignKey(LigneAchat, on_delete=models.PROTECT, related_name="receptions")
    numero_lot = models.CharField("numéro de lot", max_length=50)
    date_peremption = models.DateField("date de péremption")
    quantite_recue = models.PositiveIntegerField("quantité reçue")
    lot = models.ForeignKey("stock.LotStock", on_delete=models.PROTECT, null=True, blank=True,
                            related_name="lignes_reception")

    class Meta:
        verbose_name = "ligne de réception"
        constraints = [
            models.CheckConstraint(condition=Q(quantite_recue__gt=0), name="quantite_recue_positive"),
        ]

    def __str__(self):
        return f"{self.ligne_achat.medicament} lot {self.numero_lot} × {self.quantite_recue}"

    def montant(self):
        return self.quantite_recue * self.ligne_achat.prix_achat_unitaire
