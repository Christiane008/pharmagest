from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from utilisateurs.mixins import AccesMixin
from utilisateurs.models import JournalAudit

from .forms import FournisseurForm
from .models import Fournisseur


class FournisseurListe(AccesMixin, ListView):
    permission_required = "fournisseurs.view_fournisseur"
    template_name = "fournisseurs/liste.html"
    paginate_by = settings.PHARMAGEST_PAGINATION

    def get_queryset(self):
        qs = Fournisseur.objects.all()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(raison_sociale__icontains=q) | Q(telephone__icontains=q))
        if self.request.GET.get("inactifs") != "1":
            qs = qs.filter(actif=True)
        return qs


class FournisseurDetail(AccesMixin, DetailView):
    permission_required = "fournisseurs.view_fournisseur"
    model = Fournisseur
    template_name = "fournisseurs/detail.html"

    def get_context_data(self, **kwargs):
        from achats.models import CommandeAchat
        ctx = super().get_context_data(**kwargs)
        commandes = (CommandeAchat.objects.filter(fournisseur=self.object)
                     .prefetch_related("lignes", "receptions__lignes__ligne_achat")
                     .order_by("-cree_le"))
        ctx["commandes"] = commandes
        actives = [c for c in commandes if c.statut != CommandeAchat.Statut.ANNULEE]
        ctx["total_commande"] = sum((c.total() for c in actives), 0)
        ctx["total_recu"] = sum((c.montant_recu() for c in actives), 0)
        return ctx


class FournisseurCreation(AccesMixin, CreateView):
    permission_required = "fournisseurs.add_fournisseur"
    form_class = FournisseurForm
    template_name = "form.html"
    extra_context = {"titre": "Nouveau fournisseur"}

    def form_valid(self, form):
        messages.success(self.request, "Fournisseur ajouté.")
        return super().form_valid(form)


class FournisseurModification(AccesMixin, UpdateView):
    permission_required = "fournisseurs.change_fournisseur"
    model = Fournisseur
    form_class = FournisseurForm
    template_name = "form.html"
    extra_context = {"titre": "Modifier le fournisseur"}

    def form_valid(self, form):
        messages.success(self.request, "Fournisseur enregistré.")
        return super().form_valid(form)


class FournisseurBasculerActif(AccesMixin, View):
    """Désactive sans effacer les anciennes opérations (cahier 4.4)."""

    permission_required = "fournisseurs.change_fournisseur"

    def post(self, request, pk):
        f = get_object_or_404(Fournisseur, pk=pk)
        f.actif = not f.actif
        f.save(update_fields=["actif"])
        JournalAudit.enregistrer(request.user, "ACTIVER" if f.actif else "DESACTIVER", f)
        messages.success(request, f"Fournisseur {'réactivé' if f.actif else 'désactivé'}.")
        return redirect(f.get_absolute_url())
