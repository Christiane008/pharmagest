from django.urls import path

from . import views

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("tableau-de-bord/", views.tableau_de_bord, name="tableau_de_bord"),
    path("rapports/", views.rapports, name="rapports"),
    path("pdf/recu/<int:pk>/", views.recu_pdf, name="pdf_recu"),
    path("pdf/facture/<int:pk>/", views.facture_pdf, name="pdf_facture"),
    path("pdf/bon-commande/<int:pk>/", views.bon_commande_pdf, name="pdf_bon_commande"),
    path("pdf/bon-reception/<int:pk>/", views.bon_reception_pdf, name="pdf_bon_reception"),
    path("pdf/rapport-stock/", views.rapport_stock_pdf, name="pdf_rapport_stock"),
    path("pdf/peremptions/", views.rapport_peremptions_pdf, name="pdf_peremptions"),
    path("pdf/rapport-ventes/", views.rapport_ventes_pdf, name="pdf_rapport_ventes"),
    path("pdf/rapport-achats/", views.rapport_achats_pdf, name="pdf_rapport_achats"),
]
