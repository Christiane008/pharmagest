from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("utilisateurs.urls")),
    path("", include("rapports.urls")),
    path("medicaments/", include("medicaments.urls")),
    path("fournisseurs/", include("fournisseurs.urls")),
    path("clients/", include("clients.urls")),
    path("stock/", include("stock.urls")),
    path("achats/", include("achats.urls")),
    path("ventes/", include("ventes.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
