from django.contrib import admin

from .models import LotStock, MouvementStock


@admin.register(LotStock)
class LotStockAdmin(admin.ModelAdmin):
    list_display = ("medicament", "numero_lot", "date_peremption", "quantite_disponible", "bloque")
    list_filter = ("bloque",)
    search_fields = ("numero_lot", "medicament__nom_commercial")
    readonly_fields = ("quantite_recue", "quantite_disponible")


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    """Lecture seule : un mouvement ne se modifie jamais (RG09)."""

    list_display = ("date", "type", "lot", "quantite", "utilisateur")
    list_filter = ("type",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
