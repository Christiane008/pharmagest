from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from medicaments.models import Medicament
from rapports.templatetags.pharmagest import format_ar
from stock.views import medicaments_avec_stock
from utilisateurs.mixins import AccesMixin

from .forms import AjoutForm, AnnulationForm, ClientVenteForm, PaiementForm, RetourForm
from .models import LigneVente, Paiement, RetourVente, Vente, VenteError


class NouvelleVente(AccesMixin, View):
    """Reprend la vente en cours du caissier ou en ouvre une nouvelle."""

    permission_required = "ventes.add_vente"

    def get(self, request):
        vente = Vente.objects.filter(caissier=request.user, statut=Vente.Statut.BROUILLON).first()
        if vente is None or request.GET.get("nouvelle"):
            vente = Vente.objects.create(caissier=request.user)
        return redirect("ventes:caisse", pk=vente.pk)


class CaisseVue(AccesMixin, View):
    permission_required = "ventes.add_vente"
    template_name = "ventes/caisse.html"

    def get_vente(self, request, pk):
        vente = get_object_or_404(Vente, pk=pk)
        if vente.caissier != request.user and not request.user.has_perm("ventes.annuler_vente"):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Cette vente appartient à un autre caissier.")
        return vente

    def contexte(self, vente, **extra):
        q = self.request.GET.get("q", "").strip()
        resultats = []
        if q:
            resultats = (medicaments_avec_stock()
                         .filter(Q(nom_commercial__icontains=q) | Q(denomination_generique__icontains=q)
                                 | Q(code_barres=q)).order_by("nom_commercial")[:12])
        ctx = {
            "vente": vente, "q": q, "resultats": resultats,
            "lignes": vente.lignes.select_related("medicament", "lot"),
            "paiements": vente.paiements.all(),
            "ajout_form": AjoutForm(), "paiement_form": PaiementForm(initial={"montant": vente.reste_a_payer() or None}),
            "client_form": ClientVenteForm(initial={"client": vente.client_id}),
        }
        ctx.update(extra)
        return ctx

    def get(self, request, pk):
        vente = self.get_vente(request, pk)
        if vente.statut != Vente.Statut.BROUILLON:
            return redirect("ventes:detail", pk=vente.pk)
        return render(request, self.template_name, self.contexte(vente))

    def post(self, request, pk):
        vente = self.get_vente(request, pk)
        action = request.POST.get("action")
        if vente.statut != Vente.Statut.BROUILLON:
            messages.info(request, "Cette vente est déjà validée.")
            return redirect("ventes:detail", pk=vente.pk)
        try:
            if action == "ajouter":
                self.ajouter(request, vente)
            elif action == "retirer":
                med = get_object_or_404(Medicament, pk=request.POST.get("medicament_id"))
                vente.retirer(med)
            elif action == "client":
                form = ClientVenteForm(request.POST)
                if form.is_valid():
                    vente.client = form.cleaned_data["client"]
                    vente.save(update_fields=["client"])
            elif action == "payer":
                form = PaiementForm(request.POST)
                if not form.is_valid():
                    return render(request, self.template_name, self.contexte(vente, paiement_form=form))
                p = form.save(commit=False)
                p.vente, p.encaisse_par = vente, request.user
                p.save()
                if p.mode == Paiement.Mode.ESPECES:
                    p.confirmer()
                else:
                    messages.info(request, "Paiement en attente : vérifiez la transaction puis confirmez-la.")
            elif action in ("confirmer", "echouer"):
                p = get_object_or_404(Paiement, pk=request.POST.get("paiement_id"), vente=vente)
                if action == "confirmer":
                    p.confirmer()
                else:
                    p.statut = Paiement.Statut.ECHOUE
                    p.save(update_fields=["statut"])
            elif action == "valider":
                if not request.user.has_perm("ventes.valider_vente"):
                    from django.core.exceptions import PermissionDenied
                    raise PermissionDenied
                vente.valider(request.user)
                messages.success(request, f"Vente {vente.numero} validée. Monnaie à rendre : "
                                          f"{format_ar(vente.monnaie_a_rendre())}.")
                return redirect("ventes:detail", pk=vente.pk)
        except VenteError as e:
            messages.error(request, str(e))
        return redirect("ventes:caisse", pk=vente.pk)

    def ajouter(self, request, vente):
        form = AjoutForm(request.POST)
        if not form.is_valid():
            raise VenteError("Quantité invalide : saisissez un nombre entier supérieur à zéro.")
        d = form.cleaned_data
        if d.get("medicament_id"):
            med = Medicament.objects.filter(pk=d["medicament_id"]).first()
        elif d.get("code_barres"):
            med = Medicament.objects.filter(code_barres=d["code_barres"].strip()).first()
        else:
            med = None
        if med is None:
            raise VenteError("Médicament introuvable : vérifiez le code-barres ou recherchez-le par nom.")
        vente.ajouter(med, d["quantite"])
        messages.success(request, f"{med} × {d['quantite']} ajouté.")


class AbandonnerVente(AccesMixin, View):
    """Un brouillon n'a touché ni le stock ni la caisse confirmée : il peut être supprimé."""

    permission_required = "ventes.add_vente"

    def post(self, request, pk):
        vente = get_object_or_404(Vente, pk=pk, caissier=request.user, statut=Vente.Statut.BROUILLON)
        if vente.paiements.filter(statut=Paiement.Statut.CONFIRME).exists():
            messages.error(request, "Des paiements ont été encaissés : finalisez la vente ou "
                                    "remboursez le client avant de l'abandonner.")
            return redirect("ventes:caisse", pk=vente.pk)
        vente.delete()
        messages.info(request, "Vente abandonnée.")
        return redirect("ventes:nouvelle")


class VenteListe(AccesMixin, ListView):
    permission_required = "ventes.view_vente"
    template_name = "ventes/liste.html"
    paginate_by = settings.PHARMAGEST_PAGINATION

    def get_queryset(self):
        qs = Vente.objects.exclude(statut=Vente.Statut.BROUILLON).select_related("client", "caissier")
        g = self.request.GET
        if g.get("q"):
            qs = qs.filter(Q(numero__icontains=g["q"]) | Q(client__nom__icontains=g["q"]))
        if g.get("statut"):
            qs = qs.filter(statut=g["statut"])
        if g.get("jour") == "aujourdhui":
            qs = qs.filter(valide_le__date=timezone.localdate())
        return qs.order_by("-valide_le")


class VenteDetail(AccesMixin, View):
    permission_required = "ventes.view_vente"
    template_name = "ventes/detail.html"

    def get(self, request, pk):
        vente = get_object_or_404(Vente.objects.select_related("client", "caissier", "annule_par"), pk=pk)
        if vente.statut == Vente.Statut.BROUILLON:
            return redirect("ventes:caisse", pk=pk)
        lignes = vente.lignes.select_related("medicament", "lot").prefetch_related("retours")
        return render(request, self.template_name, {
            "vente": vente, "lignes": lignes, "paiements": vente.paiements.all(),
            "annulation_form": AnnulationForm(),
            "retours": RetourVente.objects.filter(ligne_vente__vente=vente).select_related(
                "ligne_vente__medicament", "demande_par", "valide_par"),
        })


class VenteAnnuler(AccesMixin, View):
    permission_required = "ventes.annuler_vente"

    def post(self, request, pk):
        vente = get_object_or_404(Vente, pk=pk)
        form = AnnulationForm(request.POST)
        try:
            if not form.is_valid():
                raise VenteError("Le motif d'annulation est obligatoire.")
            vente.annuler(request.user, form.cleaned_data["motif"])
            messages.success(request, f"Vente {vente.numero} annulée : le stock a été réintégré.")
        except VenteError as e:
            messages.error(request, str(e))
        return redirect("ventes:detail", pk=pk)


class RetourDemande(AccesMixin, View):
    permission_required = "ventes.add_retourvente"

    def post(self, request, pk):
        vente = get_object_or_404(Vente, pk=pk)
        form = RetourForm(request.POST)
        try:
            if not form.is_valid():
                raise VenteError("Indiquez une quantité et un motif.")
            ligne = get_object_or_404(LigneVente, pk=form.cleaned_data["ligne"], vente=vente)
            RetourVente.demander(ligne, form.cleaned_data["quantite"], form.cleaned_data["motif"],
                                 request.user)
            messages.success(request, "Retour enregistré : il attend la validation d'un pharmacien.")
        except VenteError as e:
            messages.error(request, str(e))
        return redirect("ventes:detail", pk=pk)


class RetourListe(AccesMixin, ListView):
    permission_required = "ventes.view_retourvente"
    template_name = "ventes/retours.html"
    paginate_by = settings.PHARMAGEST_PAGINATION

    def get_queryset(self):
        qs = RetourVente.objects.select_related("ligne_vente__vente", "ligne_vente__medicament",
                                                "demande_par", "valide_par")
        statut = self.request.GET.get("statut", "demande")
        return qs.filter(statut=statut) if statut else qs


class RetourTraiter(AccesMixin, View):
    permission_required = "ventes.valider_retour"

    def post(self, request, pk):
        retour = get_object_or_404(RetourVente, pk=pk)
        try:
            if request.POST.get("decision") == "refuser":
                retour.refuser(request.user)
                messages.success(request, "Retour refusé.")
            else:
                retour.valider(request.user, remise_en_stock=request.POST.get("remise_en_stock") == "1")
                messages.success(request, f"Retour validé : {format_ar(retour.montant_rembourse)} à rembourser.")
        except VenteError as e:
            messages.error(request, str(e))
        return redirect(request.POST.get("suivant") or "ventes:retours")
