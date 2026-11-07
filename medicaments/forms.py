from django import forms

from .models import Categorie, Medicament


class CategorieForm(forms.ModelForm):
    class Meta:
        model = Categorie
        fields = ["nom", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class MedicamentForm(forms.ModelForm):
    class Meta:
        model = Medicament
        fields = ["nom_commercial", "denomination_generique", "categorie", "forme", "dosage",
                  "laboratoire", "code_barres", "photo", "prix_achat", "prix_vente",
                  "seuil_alerte", "statut"]

    def clean_code_barres(self):
        code = (self.cleaned_data.get("code_barres") or "").strip() or None
        if code and Medicament.objects.filter(code_barres=code).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ce code-barres est déjà utilisé par un autre médicament.")
        return code

    def clean(self):
        data = super().clean()
        for champ in ("prix_achat", "prix_vente"):
            v = data.get(champ)
            if v is not None and v <= 0:
                self.add_error(champ, "Le prix doit être supérieur à zéro.")
        pa, pv = data.get("prix_achat"), data.get("prix_vente")
        if pa and pv and pv < pa:
            self.add_error("prix_vente", "Le prix de vente est inférieur au prix d'achat.")
        return data
