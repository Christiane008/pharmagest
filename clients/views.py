from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from utilisateurs.mixins import AccesMixin

from .forms import ClientForm
from .models import Client


class ClientListe(AccesMixin, ListView):
    permission_required = "clients.view_client"
    template_name = "clients/liste.html"
    paginate_by = settings.PHARMAGEST_PAGINATION

    def get_queryset(self):
        qs = Client.objects.all()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(nom__icontains=q) | Q(telephone__icontains=q))
        return qs


class ClientDetail(AccesMixin, DetailView):
    permission_required = "clients.view_client"
    model = Client
    template_name = "clients/detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.user.has_perm("ventes.view_vente"):
            ctx["ventes"] = self.object.ventes.exclude(statut="brouillon").order_by("-cree_le")[:50]
        return ctx


class ClientCreation(AccesMixin, CreateView):
    permission_required = "clients.add_client"
    form_class = ClientForm
    template_name = "form.html"
    extra_context = {"titre": "Nouveau client"}

    def form_valid(self, form):
        messages.success(self.request, "Client ajouté.")
        return super().form_valid(form)


class ClientModification(AccesMixin, UpdateView):
    permission_required = "clients.change_client"
    model = Client
    form_class = ClientForm
    template_name = "form.html"
    extra_context = {"titre": "Modifier le client"}

    def form_valid(self, form):
        messages.success(self.request, "Client enregistré.")
        return super().form_valid(form)
