from django.db import models
from django.urls import reverse


class Fournisseur(models.Model):
    raison_sociale = models.CharField("nom ou raison sociale", max_length=150)
    adresse = models.CharField(max_length=255, blank=True)
    telephone = models.CharField("téléphone", max_length=30, blank=True, db_index=True)
    email = models.EmailField("e-mail", blank=True)
    identifiant_fiscal = models.CharField("NIF / identifiant fiscal", max_length=50, blank=True)
    contact_principal = models.CharField(max_length=100, blank=True)
    actif = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["raison_sociale"]

    def __str__(self):
        return self.raison_sociale

    def get_absolute_url(self):
        return reverse("fournisseurs:detail", args=[self.pk])
