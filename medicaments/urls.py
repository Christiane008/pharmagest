from django.urls import path

from . import views

app_name = "medicaments"
urlpatterns = [
    path("", views.MedicamentListe.as_view(), name="liste"),
    path("nouveau/", views.MedicamentCreation.as_view(), name="creer"),
    path("<int:pk>/", views.MedicamentDetail.as_view(), name="detail"),
    path("<int:pk>/modifier/", views.MedicamentModification.as_view(), name="modifier"),
    path("<int:pk>/supprimer/", views.MedicamentSuppression.as_view(), name="supprimer"),
    path("categories/", views.CategorieListe.as_view(), name="categories"),
    path("categories/nouvelle/", views.CategorieCreation.as_view(), name="categorie_creer"),
    path("categories/<int:pk>/modifier/", views.CategorieModification.as_view(),
         name="categorie_modifier"),
    path("categories/<int:pk>/supprimer/", views.CategorieSuppression.as_view(),
         name="categorie_supprimer"),
]
