from django import forms


class CorrectionForm(forms.Form):
    quantite_comptee = forms.IntegerField(label="Quantité comptée", min_value=0)
    motif = forms.CharField(label="Motif", max_length=255,
                            help_text="Par exemple : inventaire du mois, casse, destruction de périmés")


class BlocageForm(forms.Form):
    motif = forms.CharField(label="Motif du blocage", max_length=255, required=False)
