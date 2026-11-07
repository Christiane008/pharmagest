from django.urls import path

from . import views

app_name = "clients"
urlpatterns = [
    path("", views.ClientListe.as_view(), name="liste"),
    path("nouveau/", views.ClientCreation.as_view(), name="creer"),
    path("<int:pk>/", views.ClientDetail.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.ClientModification.as_view(), name="modifier"),
]
