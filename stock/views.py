from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView

from medicaments.models import Medicament
from utilisateurs.mixins import AccesMixin
from utilisateurs.models import JournalAudit, ParametrePharmacie

from . import services
from .forms import BlocageForm, CorrectionForm
from .models import LotStock, MouvementStock


def medicaments_avec_stock():
    aujourdhui = timezone.localdate()
    vendable = Q(lots__bloque=False, lots__date_peremption__gte=aujourdhui)
    return (Medicament.objects.filter(statut="actif").select_related("categorie")
            .annotate(stock_total=Coalesce(Sum("lots__quantite_disponible"), 0),
                      stock_vendable=Coalesce(Sum("lots__quantite_disponible", filter=vendable), 0)))


class StockVue(AccesMixin, ListView):
    permission_required = "stock.view_lotstock"
    template_name = "stock/etat.html"
    paginate_by = settings.PHARMAGEST_PAGINATION

    def get_queryset(self):
        qs = medicaments_avec_stock()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(nom_commercial__icontains=q) | Q(code_barres=q))
        filtre = self.request.GET.get("filtre")
        if filtre == "rupture":
            qs = qs.filter(stock_vendable=0)
        elif filtre == "faible":
            qs = qs.filter(stock_vendable__lte=F("seuil_alerte"))
        return qs.order_by("nom_commercial")


class LotListe(AccesMixin, ListView):
    permission_required = "stock.view_lotstock"
    template_name = "stock/lots.html"
    paginate_by = settings.PHARMAGEST_PAGINATION

    def get_queryset(self):
        aujourdhui = timezone.localdate()
        jours = ParametrePharmacie.courant().jours_alerte_peremption
        qs = LotStock.objects.select_related("medicament")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(medicament__nom_commercial__icontains=q) | Q(numero_lot__icontains=q))
        etat = self.request.GET.get("etat", "en_stock")
        if etat == "en_stock":
            qs = qs.filter(quantite_disponible__gt=0)
        elif etat == "perimes":
            qs = qs.filter(date_peremption__lt=aujourdhui, quantite_disponible__gt=0)
        elif etat == "proches":
            qs = qs.filter(date_peremption__gte=aujourdhui,
                           date_peremption__lte=aujourdhui + timedelta(days=jours),
                           quantite_disponible__gt=0)
        elif etat == "bloques":
            qs = qs.filter(bloque=True)
        return qs.order_by("date_peremption")


class LotDetail(AccesMixin, DetailView):
    permission_required = "stock.view_lotstock"
    model = LotStock
    template_name = "stock/lot.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["mouvements"] = self.object.mouvements.select_related("utilisateur")
        ctx["correction_form"] = CorrectionForm(initial={"quantite_comptee": self.object.quantite_disponible})
        ctx["blocage_form"] = BlocageForm()
        ctx["somme_mouvements"] = self.object.mouvements.aggregate(t=Sum("quantite"))["t"] or 0
        return ctx


class LotBloquer(AccesMixin, View):
    permission_required = "stock.bloquer_lot"

    def post(self, request, pk):
        lot = get_object_or_404(LotStock, pk=pk)
        form = BlocageForm(request.POST)
        form.is_valid()
        lot.bloque = not lot.bloque
        lot.motif_blocage = form.cleaned_data.get("motif", "") if lot.bloque else ""
        lot.save(update_fields=["bloque", "motif_blocage"])
        JournalAudit.enregistrer(request.user, "BLOQUER_LOT" if lot.bloque else "DEBLOQUER_LOT",
                                 lot, motif=lot.motif_blocage)
        messages.success(request, f"Lot {'bloqué : il ne sera plus proposé à la vente' if lot.bloque else 'débloqué'}.")
        return redirect(lot.get_absolute_url())


class LotCorriger(AccesMixin, View):
    permission_required = "stock.corriger_stock"

    def post(self, request, pk):
        lot = get_object_or_404(LotStock, pk=pk)
        form = CorrectionForm(request.POST)
        if form.is_valid():
            try:
                mvt = services.corriger(lot, form.cleaned_data["quantite_comptee"],
                                        form.cleaned_data["motif"], request.user)
            except services.StockError as e:
                messages.error(request, str(e))
            else:
                if mvt:
                    JournalAudit.enregistrer(request.user, "CORRIGER_STOCK", lot, ecart=mvt.quantite,
                                             motif=mvt.motif)
                    messages.success(request, f"Stock corrigé ({mvt.quantite:+d}).")
                else:
                    messages.info(request, "Aucun écart : le stock est déjà juste.")
        else:
            messages.error(request, "Correction refusée : " + "; ".join(
                e for errs in form.errors.values() for e in errs))
        return redirect(lot.get_absolute_url())


class InventaireVue(AccesMixin, View):
    """Inventaire physique : saisie des quantités comptées pour tous les lots en stock."""

    permission_required = "stock.corriger_stock"
    template_name = "stock/inventaire.html"

    def lots(self):
        return LotStock.objects.select_related("medicament").filter(
            Q(quantite_disponible__gt=0) | Q(mouvements__isnull=False)).distinct().order_by(
            "medicament__nom_commercial", "date_peremption")

    def get(self, request):
        return render(request, self.template_name, {"lots": self.lots()})

    def post(self, request):
        motif = request.POST.get("motif", "").strip() or "Inventaire physique"
        nb, erreurs = 0, []
        for lot in self.lots():
            valeur = request.POST.get(f"lot_{lot.pk}", "").strip()
            if valeur == "":
                continue
            try:
                mvt = services.corriger(lot, int(valeur), motif, request.user)
                nb += 1 if mvt else 0
            except (ValueError, services.StockError) as e:
                erreurs.append(f"{lot} : {e}")
        if nb:
            JournalAudit.enregistrer(request.user, "INVENTAIRE", None, lots_corriges=nb, motif=motif)
        for e in erreurs:
            messages.error(request, e)
        messages.success(request, f"Inventaire enregistré : {nb} lot(s) corrigé(s).")
        return redirect("stock:mouvements")


class MouvementListe(AccesMixin, ListView):
    permission_required = "stock.view_mouvementstock"
    template_name = "stock/mouvements.html"
    paginate_by = 30

    def get_queryset(self):
        qs = MouvementStock.objects.select_related("lot__medicament", "utilisateur")
        t = self.request.GET.get("type")
        if t:
            qs = qs.filter(type=t)
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(lot__medicament__nom_commercial__icontains=q) | Q(lot__numero_lot__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["types"] = MouvementStock.Type.choices
        return ctx
