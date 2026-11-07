from django import forms

from .models import Client


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["nom", "telephone", "actif"]

    def clean(self):
        data = super().clean()
        if not data.get("nom") and not data.get("telephone"):
            raise forms.ValidationError("Indiquez au moins un nom ou un téléphone.")
        return data
