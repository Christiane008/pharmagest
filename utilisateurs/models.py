from django.conf import settings
from django.db import models


class Profil(models.Model):
    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profil"
    )
    telephone = models.CharField("téléphone", max_length=30, blank=True)
    fonction = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Profil de {self.utilisateur}"


class ParametrePharmacie(models.Model):
    """Une seule ligne : informations imprimées sur les documents PDF."""

    nom = models.CharField(max_length=150, default="Pharmacie PharmaGest")
    adresse = models.CharField(max_length=255, default="Antananarivo, Madagascar")
    telephone = models.CharField("téléphone", max_length=50, blank=True)
    email = models.EmailField(blank=True)
    nif = models.CharField("NIF", max_length=50, blank=True)
    stat = models.CharField("STAT", max_length=50, blank=True)
    jours_alerte_peremption = models.PositiveIntegerField(
        "alerte de péremption (jours)", default=90
    )
    pied_de_page = models.CharField(
        "mention en pied de document", max_length=255,
        default="Merci de votre confiance. Conservez ce document.",
    )

    class Meta:
        verbose_name = "paramètres de la pharmacie"
        verbose_name_plural = "paramètres de la pharmacie"
        permissions = [
            ("voir_tableau_de_bord", "Voir le tableau de bord"),
            ("voir_statistiques", "Voir les statistiques financières"),
            ("voir_rapports", "Générer les rapports PDF"),
            ("sauvegarder_base", "Sauvegarder la base de données"),
        ]

    def __str__(self):
        return self.nom

    @classmethod
    def courant(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class JournalAudit(models.Model):
    """Traçabilité des opérations sensibles (RG09). Écriture seule."""

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="journal"
    )
    action = models.CharField(max_length=50)
    objet_type = models.CharField("type d'objet", max_length=50)
    objet_id = models.PositiveBigIntegerField(null=True, blank=True)
    objet_repr = models.CharField("objet", max_length=200, blank=True)
    details = models.JSONField(default=dict, blank=True)
    date = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "entrée du journal d'audit"
        verbose_name_plural = "journal d'audit"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date:%d/%m/%Y %H:%M} {self.utilisateur} {self.action} {self.objet_repr}"

    @classmethod
    def enregistrer(cls, utilisateur, action, objet=None, **details):
        return cls.objects.create(
            utilisateur=utilisateur,
            action=action,
            objet_type=type(objet).__name__ if objet is not None else "",
            objet_id=getattr(objet, "pk", None),
            objet_repr=str(objet)[:200] if objet is not None else "",
            details={k: str(v) for k, v in details.items()},
        )
