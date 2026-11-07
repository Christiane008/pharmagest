from django.urls import path

from . import views

app_name = "ventes"
urlpatterns = [
    path("", views.VenteListe.as_view(), name="liste"),
    path("caisse/", views.NouvelleVente.as_view(), name="nouvelle"),
    path("caisse/<int:pk>/", views.CaisseVue.as_view(), name="caisse"),
    path("caisse/<int:pk>/abandonner/", views.AbandonnerVente.as_view(), name="abandonner"),
    path("<int:pk>/", views.VenteDetail.as_view(), name="detail"),
    path("<int:pk>/annuler/", views.VenteAnnuler.as_view(), name="annuler"),
    path("<int:pk>/retour/", views.RetourDemande.as_view(), name="retour_demander"),
    path("retours/", views.RetourListe.as_view(), name="retours"),
    path("retours/<int:pk>/traiter/", views.RetourTraiter.as_view(), name="retour_traiter"),
]
