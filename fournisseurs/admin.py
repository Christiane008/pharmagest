from django.contrib import admin

from .models import Fournisseur


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ("raison_sociale", "telephone", "contact_principal", "actif")
    search_fields = ("raison_sociale", "telephone")
    list_filter = ("actif",)
