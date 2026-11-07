from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from .forms import ParametrePharmacieForm, UtilisateurCreationForm, UtilisateurModificationForm
from .mixins import AccesMixin
from .models import JournalAudit, ParametrePharmacie


class UtilisateurListe(AccesMixin, ListView):
    permission_required = "auth.view_user"
    template_name = "utilisateurs/liste.html"
    paginate_by = 20

    def get_queryset(self):
        qs = User.objects.prefetch_related("groups").order_by("username")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(username__icontains=q) | Q(last_name__icontains=q)
                           | Q(first_name__icontains=q))
        return qs


class UtilisateurCreation(AccesMixin, CreateView):
    permission_required = "auth.add_user"
    form_class = UtilisateurCreationForm
    template_name = "form.html"
    success_url = reverse_lazy("utilisateurs:liste")
    extra_context = {"titre": "Nouveau compte"}

    def form_valid(self, form):
        reponse = super().form_valid(form)
        JournalAudit.enregistrer(self.request.user, "CREER_COMPTE", self.object)
        messages.success(self.request, f"Compte « {self.object} » créé.")
        return reponse


class UtilisateurModification(AccesMixin, UpdateView):
    permission_required = "auth.change_user"
    model = User
    form_class = UtilisateurModificationForm
    template_name = "form.html"
    success_url = reverse_lazy("utilisateurs:liste")
    extra_context = {"titre": "Modifier le compte"}

    def form_valid(self, form):
        if form.instance == self.request.user and not form.cleaned_data["is_active"]:
            form.add_error("is_active", "Vous ne pouvez pas désactiver votre propre compte.")
            return self.form_invalid(form)
        reponse = super().form_valid(form)
        JournalAudit.enregistrer(self.request.user, "MODIFIER_COMPTE", self.object,
                                 actif=self.object.is_active)
        messages.success(self.request, "Compte enregistré.")
        return reponse


class UtilisateurBasculerActif(AccesMixin, View):
    permission_required = "auth.change_user"

    def post(self, request, pk):
        u = get_object_or_404(User, pk=pk)
        if u == request.user:
            messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
        else:
            u.is_active = not u.is_active
            u.save(update_fields=["is_active"])
            JournalAudit.enregistrer(request.user, "ACTIVER" if u.is_active else "DESACTIVER", u)
            messages.success(request, f"Compte « {u} » {'activé' if u.is_active else 'désactivé'}.")
        return redirect("utilisateurs:liste")


class JournalListe(AccesMixin, ListView):
    permission_required = "utilisateurs.view_journalaudit"
    template_name = "utilisateurs/journal.html"
    paginate_by = 30

    def get_queryset(self):
        qs = JournalAudit.objects.select_related("utilisateur")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(action__icontains=q) | Q(objet_repr__icontains=q)
                           | Q(utilisateur__username__icontains=q))
        return qs


class ParametresModification(AccesMixin, UpdateView):
    permission_required = "utilisateurs.change_parametrepharmacie"
    form_class = ParametrePharmacieForm
    template_name = "form.html"
    success_url = reverse_lazy("utilisateurs:parametres")
    extra_context = {"titre": "Paramètres de la pharmacie"}

    def get_object(self, queryset=None):
        return ParametrePharmacie.courant()

    def form_valid(self, form):
        messages.success(self.request, "Paramètres enregistrés.")
        JournalAudit.enregistrer(self.request.user, "MODIFIER_PARAMETRES", form.instance)
        return super().form_valid(form)
