from django.db import models
from django.urls import reverse


class Client(models.Model):
    """Données limitées au strict nécessaire (cahier 4.5)."""

    nom = models.CharField(max_length=150, blank=True)
    telephone = models.CharField("téléphone", max_length=30, blank=True, db_index=True)
    actif = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom or self.telephone or f"Client n° {self.pk}"

    def get_absolute_url(self):
        return reverse("clients:detail", args=[self.pk])
