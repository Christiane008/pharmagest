from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from utilisateurs.mixins import AccesMixin

from .forms import CommandeForm, LigneAchatFormSet, LigneReceptionForm
from .models import AchatError, CommandeAchat, LigneReception, ReceptionAchat


class CommandeListe(AccesMixin, ListView):
    permission_required = "achats.view_commandeachat"
    template_name = "achats/commandes.html"
    paginate_by = settings.PHARMAGEST_PAGINATION

    def get_queryset(self):
        qs = CommandeAchat.objects.select_related("fournisseur", "cree_par").prefetch_related("lignes")
        statut = self.request.GET.get("statut")
        if statut:
            qs = qs.filter(statut=statut)
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(numero__icontains=q) | qs.filter(fournisseur__raison_sociale__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["statuts"] = CommandeAchat.Statut.choices
        return ctx


class CommandeEdition(AccesMixin, View):
    """Création ou modification d'une commande en brouillon, avec ses lignes."""

    permission_required = "achats.add_commandeachat"
    template_name = "achats/commande_form.html"

    def get_commande(self, pk):
        if pk is None:
            return CommandeAchat()
        cmd = get_object_or_404(CommandeAchat, pk=pk)
        if not cmd.est_modifiable:
            raise AchatError("Seule une commande en brouillon peut être modifiée.")
        return cmd

    def get(self, request, pk=None):
        try:
            cmd = self.get_commande(pk)
        except AchatError as e:
            messages.error(request, str(e))
            return redirect("achats:commande", pk=pk)
        return render(request, self.template_name, {
            "form": CommandeForm(instance=cmd), "formset": LigneAchatFormSet(instance=cmd), "commande": cmd})

    def post(self, request, pk=None):
        try:
            cmd = self.get_commande(pk)
        except AchatError as e:
            messages.error(request, str(e))
            return redirect("achats:commande", pk=pk)
        form = CommandeForm(request.POST, instance=cmd)
        formset = LigneAchatFormSet(request.POST, instance=cmd)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                cmd = form.save(commit=False)
                if not cmd.pk:
                    cmd.cree_par = request.user
                cmd.save()
                formset.instance = cmd
                formset.save()
            messages.success(request, f"Commande {cmd.numero} enregistrée en brouillon. "
                                      "Le stock ne change qu'à la réception.")
            return redirect(cmd.get_absolute_url())
        return render(request, self.template_name, {"form": form, "formset": formset, "commande": cmd})


class CommandeDetail(AccesMixin, DetailView):
    permission_required = "achats.view_commandeachat"
    model = CommandeAchat
    template_name = "achats/commande.html"

    def get_queryset(self):
        return CommandeAchat.objects.select_related("fournisseur", "cree_par", "valide_par")


class CommandeAction(AccesMixin, View):
    permission_required = "achats.valider_commande"

    def post(self, request, pk, action):
        cmd = get_object_or_404(CommandeAchat, pk=pk)
        try:
            if action == "valider":
                cmd.valider(request.user)
                messages.success(request, f"Commande {cmd.numero} validée : elle peut être réceptionnée.")
            elif action == "annuler":
                cmd.annuler(request.user)
                messages.success(request, f"Commande {cmd.numero} annulée.")
        except AchatError as e:
            messages.error(request, str(e))
        return redirect(cmd.get_absolute_url())


class ReceptionCreation(AccesMixin, View):
    permission_required = "achats.add_receptionachat"
    template_name = "achats/reception_form.html"

    def lignes(self, cmd):
        return [l for l in cmd.lignes.select_related("medicament") if l.reste_a_recevoir() > 0]

    def get(self, request, pk):
        cmd = get_object_or_404(CommandeAchat, pk=pk)
        if not cmd.peut_etre_receptionnee:
            messages.error(request, "Validez la commande avant de la réceptionner.")
            return redirect(cmd.get_absolute_url())
        forms_ = [(l, LigneReceptionForm(prefix=f"l{l.pk}", ligne_achat=l,
                                         initial={"quantite": l.reste_a_recevoir()}))
                  for l in self.lignes(cmd)]
        return render(request, self.template_name, {"commande": cmd, "lignes": forms_})

    def post(self, request, pk):
        cmd = get_object_or_404(CommandeAchat, pk=pk)
        if not cmd.peut_etre_receptionnee:
            messages.error(request, "Cette commande ne peut pas être réceptionnée.")
            return redirect(cmd.get_absolute_url())
        forms_ = [(l, LigneReceptionForm(request.POST, prefix=f"l{l.pk}", ligne_achat=l))
                  for l in self.lignes(cmd)]
        if all(f.is_valid() for _, f in forms_):
            saisies = [(l, f.cleaned_data) for l, f in forms_ if f.cleaned_data.get("quantite")]
            if not saisies:
                messages.error(request, "Indiquez au moins une quantité reçue.")
            else:
                with transaction.atomic():
                    rec = ReceptionAchat.objects.create(commande=cmd, cree_par=request.user)
                    for l, d in saisies:
                        LigneReception.objects.create(
                            reception=rec, ligne_achat=l, numero_lot=d["numero_lot"].strip(),
                            date_peremption=d["date_peremption"], quantite_recue=d["quantite"])
                messages.success(request, f"Réception {rec.numero} enregistrée. Vérifiez-la puis "
                                          "validez-la pour faire entrer les produits en stock.")
                return redirect(rec.get_absolute_url())
        return render(request, self.template_name, {"commande": cmd, "lignes": forms_})


class ReceptionDetail(AccesMixin, DetailView):
    permission_required = "achats.view_receptionachat"
    model = ReceptionAchat
    template_name = "achats/reception.html"


class ReceptionValider(AccesMixin, View):
    permission_required = "achats.valider_reception"

    def post(self, request, pk):
        rec = get_object_or_404(ReceptionAchat, pk=pk)
        try:
            rec.valider(request.user)
        except AchatError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, f"Réception {rec.numero} validée : le stock a été mis à jour.")
        return redirect(rec.get_absolute_url())


class ReceptionSupprimer(AccesMixin, View):
    """Un brouillon de réception n'a pas touché le stock : il peut être supprimé."""

    permission_required = "achats.add_receptionachat"

    def post(self, request, pk):
        rec = get_object_or_404(ReceptionAchat, pk=pk)
        cmd = rec.commande
        if rec.statut != ReceptionAchat.Statut.BROUILLON:
            messages.error(request, "Une réception validée ne se supprime pas.")
            return redirect(rec.get_absolute_url())
        rec.delete()
        messages.success(request, "Brouillon de réception supprimé.")
        return redirect(cmd.get_absolute_url())
