from django.conf import settings
from django.contrib import messages
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from utilisateurs.mixins import AccesMixin
from utilisateurs.models import JournalAudit

from .forms import CategorieForm, MedicamentForm
from .models import Categorie, Medicament

TRIS = {
    "nom": "nom_commercial", "-nom": "-nom_commercial",
    "prix": "prix_vente", "-prix": "-prix_vente",
    "stock": "stock_total", "-stock": "-stock_total",
    "recent": "-cree_le",
}


# ---------- Catégories ----------
class CategorieListe(AccesMixin, ListView):
    permission_required = "medicaments.view_categorie"
    template_name = "medicaments/categories.html"
    paginate_by = settings.PHARMAGEST_PAGINATION

    def get_queryset(self):
        from django.db.models import Count
        qs = Categorie.objects.annotate(nb=Count("medicaments")).order_by("nom")
        q = self.request.GET.get("q", "").strip()
        return qs.filter(nom__icontains=q) if q else qs


class CategorieCreation(AccesMixin, CreateView):
    permission_required = "medicaments.add_categorie"
    form_class = CategorieForm
    template_name = "form.html"
    success_url = reverse_lazy("medicaments:categories")
    extra_context = {"titre": "Nouvelle catégorie"}

    def form_valid(self, form):
        messages.success(self.request, "Catégorie ajoutée.")
        return super().form_valid(form)


class CategorieModification(AccesMixin, UpdateView):
    permission_required = "medicaments.change_categorie"
    model = Categorie
    form_class = CategorieForm
    template_name = "form.html"
    success_url = reverse_lazy("medicaments:categories")
    extra_context = {"titre": "Modifier la catégorie"}

    def form_valid(self, form):
        messages.success(self.request, "Catégorie enregistrée.")
        return super().form_valid(form)


class CategorieSuppression(AccesMixin, View):
    permission_required = "medicaments.delete_categorie"

    def post(self, request, pk):
        cat = get_object_or_404(Categorie, pk=pk)
        if not cat.peut_etre_supprimee():
            messages.error(request, f"« {cat} » est utilisée par des médicaments : "
                                    "elle ne peut pas être supprimée.")
        else:
            JournalAudit.enregistrer(request.user, "SUPPRIMER", cat)
            cat.delete()
            messages.success(request, "Catégorie supprimée.")
        return redirect("medicaments:categories")


# ---------- Médicaments ----------
class MedicamentListe(AccesMixin, ListView):
    permission_required = "medicaments.view_medicament"
    template_name = "medicaments/liste.html"
    paginate_by = settings.PHARMAGEST_PAGINATION

    def get_queryset(self):
        g = self.request.GET
        from django.utils import timezone
        vendable = Q(lots__bloque=False, lots__date_peremption__gte=timezone.localdate())
        qs = Medicament.objects.select_related("categorie").annotate(
            stock_total=Coalesce(Sum("lots__quantite_disponible", filter=vendable), 0))
        q = g.get("q", "").strip()
        if q:
            qs = qs.filter(Q(nom_commercial__icontains=q) | Q(denomination_generique__icontains=q)
                           | Q(code_barres=q))
        if g.get("categorie"):
            qs = qs.filter(categorie_id=g["categorie"])
        statut = g.get("statut", "actif")
        if statut in ("actif", "archive"):
            qs = qs.filter(statut=statut)
        return qs.order_by(TRIS.get(g.get("tri"), "nom_commercial"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = Categorie.objects.all()
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["params"] = params.urlencode()
        return ctx


class MedicamentDetail(AccesMixin, DetailView):
    permission_required = "medicaments.view_medicament"
    model = Medicament
    template_name = "medicaments/detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["lots"] = self.object.lots.order_by("date_peremption")
        return ctx


class MedicamentCreation(AccesMixin, CreateView):
    permission_required = "medicaments.add_medicament"
    form_class = MedicamentForm
    template_name = "form.html"
    extra_context = {"titre": "Nouveau médicament", "multipart": True}

    def form_valid(self, form):
        reponse = super().form_valid(form)
        if not self.object.photo:
            from .illustrations import dessiner
            image = dessiner(self.object)
            self.object.photo.save(image.name, image, save=True)
        JournalAudit.enregistrer(self.request.user, "CREER", self.object)
        messages.success(self.request, "Médicament ajouté.")
        return reponse


class MedicamentModification(AccesMixin, UpdateView):
    permission_required = "medicaments.change_medicament"
    model = Medicament
    form_class = MedicamentForm
    template_name = "form.html"
    extra_context = {"titre": "Modifier le médicament", "multipart": True}

    def form_valid(self, form):
        avant = Medicament.objects.get(pk=self.object.pk)
        reponse = super().form_valid(form)
        changes = {c: f"{getattr(avant, c)} → {getattr(self.object, c)}"
                   for c in ("prix_achat", "prix_vente", "statut")
                   if getattr(avant, c) != getattr(self.object, c)}
        JournalAudit.enregistrer(self.request.user, "MODIFIER", self.object, **changes)
        messages.success(self.request, "Médicament enregistré.")
        return reponse


class MedicamentSuppression(AccesMixin, View):
    """Supprime seulement sans historique ; sinon archive (cahier 4.2)."""

    permission_required = "medicaments.delete_medicament"

    def post(self, request, pk):
        med = get_object_or_404(Medicament, pk=pk)
        if med.a_un_historique():
            med.statut = Medicament.Statut.ARCHIVE
            med.save(update_fields=["statut"])
            JournalAudit.enregistrer(request.user, "ARCHIVER", med)
            messages.warning(request, f"« {med} » a un historique de stock ou de ventes : "
                                      "il a été archivé au lieu d'être supprimé.")
            return redirect(med.get_absolute_url())
        JournalAudit.enregistrer(request.user, "SUPPRIMER", med)
        med.delete()
        messages.success(request, "Médicament supprimé.")
        return redirect("medicaments:liste")
