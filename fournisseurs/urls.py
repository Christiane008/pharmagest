from django.urls import path

from . import views

app_name = "fournisseurs"
urlpatterns = [
    path("", views.FournisseurListe.as_view(), name="liste"),
    path("nouveau/", views.FournisseurCreation.as_view(), name="creer"),
    path("<int:pk>/", views.FournisseurDetail.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.FournisseurModification.as_view(), name="modifier"),
    path("<int:pk>/activer/", views.FournisseurBasculerActif.as_view(), name="basculer"),
]
