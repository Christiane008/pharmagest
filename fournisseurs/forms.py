from django import forms

from .models import Fournisseur


class FournisseurForm(forms.ModelForm):
    class Meta:
        model = Fournisseur
        fields = ["raison_sociale", "adresse", "telephone", "email", "identifiant_fiscal",
                  "contact_principal", "actif"]
