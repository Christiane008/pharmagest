from django.urls import path

from . import views

app_name = "achats"
urlpatterns = [
    path("", views.CommandeListe.as_view(), name="commandes"),
    path("nouvelle/", views.CommandeEdition.as_view(), name="commande_creer"),
    path("<int:pk>/", views.CommandeDetail.as_view(), name="commande"),
    path("<int:pk>/modifier/", views.CommandeEdition.as_view(), name="commande_modifier"),
    path("<int:pk>/<str:action>/", views.CommandeAction.as_view(), name="commande_action"),
    path("<int:pk>/receptionner/nouvelle/", views.ReceptionCreation.as_view(), name="reception_creer"),
    path("receptions/<int:pk>/", views.ReceptionDetail.as_view(), name="reception"),
    path("receptions/<int:pk>/valider/", views.ReceptionValider.as_view(), name="reception_valider"),
    path("receptions/<int:pk>/supprimer/", views.ReceptionSupprimer.as_view(), name="reception_supprimer"),
]
