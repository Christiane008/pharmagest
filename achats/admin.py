from django.contrib import admin

from .models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat


class LigneAchatInline(admin.TabularInline):
    model = LigneAchat
    extra = 0


@admin.register(CommandeAchat)
class CommandeAchatAdmin(admin.ModelAdmin):
    list_display = ("numero", "fournisseur", "statut", "cree_le")
    list_filter = ("statut",)
    inlines = [LigneAchatInline]
    readonly_fields = ("statut", "valide_par", "valide_le")


class LigneReceptionInline(admin.TabularInline):
    model = LigneReception
    extra = 0
    readonly_fields = ("lot",)


@admin.register(ReceptionAchat)
class ReceptionAchatAdmin(admin.ModelAdmin):
    list_display = ("numero", "commande", "statut", "recu_le")
    inlines = [LigneReceptionInline]
    readonly_fields = ("statut", "recu_par", "recu_le")
