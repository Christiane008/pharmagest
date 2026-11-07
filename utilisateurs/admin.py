from django.contrib import admin

from .models import JournalAudit, ParametrePharmacie, Profil


@admin.register(JournalAudit)
class JournalAuditAdmin(admin.ModelAdmin):
    list_display = ("date", "utilisateur", "action", "objet_type", "objet_repr")
    list_filter = ("action", "objet_type")
    search_fields = ("objet_repr", "utilisateur__username")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(ParametrePharmacie)
admin.site.register(Profil)
