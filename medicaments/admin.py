from django.contrib import admin

from .models import Categorie, Medicament


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    search_fields = ("nom",)


@admin.register(Medicament)
class MedicamentAdmin(admin.ModelAdmin):
    list_display = ("nom_commercial", "dosage", "categorie", "prix_vente", "statut")
    list_filter = ("categorie", "statut", "forme")
    search_fields = ("nom_commercial", "denomination_generique", "code_barres")
