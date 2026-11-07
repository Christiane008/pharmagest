from django.urls import path

from . import views

app_name = "stock"
urlpatterns = [
    path("", views.StockVue.as_view(), name="etat"),
    path("lots/", views.LotListe.as_view(), name="lots"),
    path("lots/<int:pk>/", views.LotDetail.as_view(), name="lot"),
    path("lots/<int:pk>/bloquer/", views.LotBloquer.as_view(), name="bloquer"),
    path("lots/<int:pk>/corriger/", views.LotCorriger.as_view(), name="corriger"),
    path("inventaire/", views.InventaireVue.as_view(), name="inventaire"),
    path("mouvements/", views.MouvementListe.as_view(), name="mouvements"),
]
