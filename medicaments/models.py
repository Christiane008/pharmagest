from django.db import models
from django.db.models import Q, Sum
from django.urls import reverse
from django.utils import timezone

from .validators import valider_extension_image, valider_taille_image


class Categorie(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "catégorie"

    def __str__(self):
        return self.nom

    def peut_etre_supprimee(self):
        return not self.medicaments.exists()


class Medicament(models.Model):
    class Forme(models.TextChoices):
        COMPRIME = "comprime", "Comprimé"
        GELULE = "gelule", "Gélule"
        SIROP = "sirop", "Sirop"
        INJECTABLE = "injectable", "Injectable"
        POMMADE = "pommade", "Pommade / crème"
        SACHET = "sachet", "Sachet"
        GOUTTES = "gouttes", "Gouttes"
        AUTRE = "autre", "Autre"

    class Statut(models.TextChoices):
        ACTIF = "actif", "Actif"
        ARCHIVE = "archive", "Archivé"

    nom_commercial = models.CharField("nom commercial", max_length=150)
    denomination_generique = models.CharField("dénomination générique", max_length=150, blank=True)
    categorie = models.ForeignKey(Categorie, on_delete=models.PROTECT, related_name="medicaments",
                                  verbose_name="catégorie")
    forme = models.CharField("forme pharmaceutique", max_length=20, choices=Forme.choices,
                             default=Forme.COMPRIME)
    dosage = models.CharField(max_length=50, blank=True, help_text="Par exemple : 500 mg")
    laboratoire = models.CharField(max_length=150, blank=True)
    code_barres = models.CharField("code-barres", max_length=50, blank=True, null=True)
    photo = models.ImageField(upload_to="medicaments/", blank=True, null=True,
                              validators=[valider_extension_image, valider_taille_image],
                              help_text="JPG ou PNG, 2 Mo maximum")
    prix_achat = models.DecimalField("prix d'achat (Ar)", max_digits=10, decimal_places=2)
    prix_vente = models.DecimalField("prix de vente (Ar)", max_digits=10, decimal_places=2)
    seuil_alerte = models.PositiveIntegerField("seuil d'alerte", default=10)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.ACTIF)
    cree_le = models.DateTimeField("créé le", auto_now_add=True)

    class Meta:
        ordering = ["nom_commercial"]
        verbose_name = "médicament"
        constraints = [
            models.UniqueConstraint(fields=["code_barres"], condition=Q(code_barres__isnull=False),
                                    name="code_barres_unique"),
            models.CheckConstraint(condition=Q(prix_achat__gt=0), name="prix_achat_positif"),
            models.CheckConstraint(condition=Q(prix_vente__gt=0), name="prix_vente_positif"),
        ]

    def __str__(self):
        return f"{self.nom_commercial} {self.dosage}".strip()

    def get_absolute_url(self):
        return reverse("medicaments:detail", args=[self.pk])

    def save(self, *args, **kwargs):
        # Un code-barres vide est enregistré NULL pour que la contrainte d'unicité l'ignore.
        if not self.code_barres:
            self.code_barres = None
        super().save(*args, **kwargs)

    @property
    def est_actif(self):
        return self.statut == self.Statut.ACTIF

    def stock_disponible(self):
        return self.lots.aggregate(t=Sum("quantite_disponible"))["t"] or 0

    def lots_vendables(self):
        aujourdhui = timezone.localdate()
        return self.lots.filter(bloque=False, quantite_disponible__gt=0,
                                date_peremption__gte=aujourdhui).order_by("date_peremption", "id")

    def stock_vendable(self):
        return self.lots_vendables().aggregate(t=Sum("quantite_disponible"))["t"] or 0

    def est_en_alerte(self):
        return self.stock_vendable() <= self.seuil_alerte

    def a_un_historique(self):
        return (self.lots.exists() or self.lignes_achat.exists() or self.lignes_vente.exists())
