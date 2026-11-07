from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from fournisseurs.models import Fournisseur
from medicaments.models import Medicament

from .models import CommandeAchat, LigneAchat


class CommandeForm(forms.ModelForm):
    class Meta:
        model = CommandeAchat
        fields = ["fournisseur", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fournisseur"].queryset = Fournisseur.objects.filter(actif=True)


class LigneAchatForm(forms.ModelForm):
    class Meta:
        model = LigneAchat
        fields = ["medicament", "quantite_commandee", "prix_achat_unitaire"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["medicament"].queryset = Medicament.objects.filter(statut="actif")
        self.fields["prix_achat_unitaire"].required = False
        self.fields["prix_achat_unitaire"].help_text = "Vide = prix d'achat de la fiche"

    def clean(self):
        data = super().clean()
        med, prix = data.get("medicament"), data.get("prix_achat_unitaire")
        if med and prix is None:
            data["prix_achat_unitaire"] = med.prix_achat
            self.instance.prix_achat_unitaire = med.prix_achat
        if prix is not None and prix <= 0:
            self.add_error("prix_achat_unitaire", "Le prix doit être supérieur à zéro.")
        q = data.get("quantite_commandee")
        if q is not None and q <= 0:
            self.add_error("quantite_commandee", "La quantité doit être supérieure à zéro.")
        return data


class BaseLigneFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        vus, nb = set(), 0
        for f in self.forms:
            if not hasattr(f, "cleaned_data") or f.cleaned_data.get("DELETE"):
                continue
            med = f.cleaned_data.get("medicament")
            if not med:
                continue
            if med in vus:
                raise forms.ValidationError(f"{med} apparaît deux fois : regroupez les quantités.")
            vus.add(med)
            nb += 1
        if nb == 0:
            raise forms.ValidationError("Ajoutez au moins un médicament à la commande.")


LigneAchatFormSet = inlineformset_factory(
    CommandeAchat, LigneAchat, form=LigneAchatForm, formset=BaseLigneFormSet,
    extra=4, can_delete=True,
)


class LigneReceptionForm(forms.Form):
    """Une ligne de saisie par ligne de commande restant à recevoir."""

    quantite = forms.IntegerField(label="Quantité reçue", min_value=0, required=False)
    numero_lot = forms.CharField(label="N° de lot", max_length=50, required=False)
    date_peremption = forms.DateField(label="Péremption", required=False,
                                      widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, ligne_achat=None, **kwargs):
        self.ligne_achat = ligne_achat
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        q = data.get("quantite") or 0
        if q == 0:
            return data
        reste = self.ligne_achat.reste_a_recevoir()
        if q > reste:
            self.add_error("quantite", f"Il ne reste que {reste} unité(s) à recevoir.")
        if not data.get("numero_lot"):
            self.add_error("numero_lot", "Le numéro de lot est obligatoire.")
        d = data.get("date_peremption")
        if not d:
            self.add_error("date_peremption", "La date de péremption est obligatoire.")
        elif d <= timezone.localdate():
            self.add_error("date_peremption", "Ce lot est déjà périmé : refusez la livraison.")
        return data
