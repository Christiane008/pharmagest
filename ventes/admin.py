from django.contrib import admin

from .models import LigneVente, Paiement, RetourVente, Vente


class LigneVenteInline(admin.TabularInline):
    model = LigneVente
    extra = 0
    can_delete = False
    readonly_fields = ("medicament", "lot", "quantite", "prix_unitaire", "sous_total")

    def has_add_permission(self, request, obj=None):
        return False


class PaiementInline(admin.TabularInline):
    model = Paiement
    extra = 0
    can_delete = False
    readonly_fields = ("mode", "montant", "reference", "statut", "encaisse_par", "confirme_le")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Vente)
class VenteAdmin(admin.ModelAdmin):
    """Consultation seule : une vente se crée à la caisse et s'annule par opération compensatoire."""

    list_display = ("numero", "statut", "total", "caissier", "valide_le")
    list_filter = ("statut",)
    search_fields = ("numero",)
    inlines = [LigneVenteInline, PaiementInline]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RetourVente)
class RetourVenteAdmin(admin.ModelAdmin):
    list_display = ("id", "ligne_vente", "quantite", "statut", "montant_rembourse")
    list_filter = ("statut",)

    def has_change_permission(self, request, obj=None):
        return False
