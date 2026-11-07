from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, User

from .models import ParametrePharmacie


class UtilisateurCreationForm(UserCreationForm):
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.order_by("name"), required=False,
        widget=forms.CheckboxSelectMultiple, label="Rôles",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "groups")


class UtilisateurModificationForm(forms.ModelForm):
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.order_by("name"), required=False,
        widget=forms.CheckboxSelectMultiple, label="Rôles",
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "is_active", "groups")
        labels = {"is_active": "Compte actif"}


class ParametrePharmacieForm(forms.ModelForm):
    class Meta:
        model = ParametrePharmacie
        fields = "__all__"
