from django import forms

from clients.models import Client

from .models import Paiement


class AjoutForm(forms.Form):
    code_barres = forms.CharField(label="Code-barres", required=False)
    medicament_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    quantite = forms.IntegerField(label="Quantité", min_value=1, initial=1)


class PaiementForm(forms.ModelForm):
    class Meta:
        model = Paiement
        fields = ["mode", "montant", "reference"]

    def clean_montant(self):
        m = self.cleaned_data["montant"]
        if m <= 0:
            raise forms.ValidationError("Le montant doit être positif.")
        return m

    def clean(self):
        data = super().clean()
        if data.get("mode") == Paiement.Mode.MOBILE_MONEY and not data.get("reference", "").strip():
            self.add_error("reference", "La référence de la transaction mobile money est obligatoire.")
        return data


class ClientVenteForm(forms.Form):
    client = forms.ModelChoiceField(queryset=Client.objects.filter(actif=True), required=False,
                                    empty_label="Vente comptoir (client non identifié)")


class AnnulationForm(forms.Form):
    motif = forms.CharField(max_length=255, label="Motif de l'annulation")


class RetourForm(forms.Form):
    ligne = forms.IntegerField(widget=forms.HiddenInput)
    quantite = forms.IntegerField(min_value=1, label="Quantité")
    motif = forms.CharField(max_length=255, label="Motif")
