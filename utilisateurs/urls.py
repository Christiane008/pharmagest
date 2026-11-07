from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

urlpatterns = [
    path("connexion/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
    path("mot-de-passe/", auth_views.PasswordChangeView.as_view(
        success_url=reverse_lazy("password_change_done")), name="password_change"),
    path("mot-de-passe/modifie/", auth_views.PasswordChangeDoneView.as_view(),
         name="password_change_done"),
    path("mot-de-passe/oublie/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("mot-de-passe/oublie/envoye/", auth_views.PasswordResetDoneView.as_view(),
         name="password_reset_done"),
    path("reinitialiser/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(),
         name="password_reset_confirm"),
    path("reinitialiser/termine/", auth_views.PasswordResetCompleteView.as_view(),
         name="password_reset_complete"),
]

app_patterns = [
    path("", views.UtilisateurListe.as_view(), name="liste"),
    path("nouveau/", views.UtilisateurCreation.as_view(), name="creer"),
    path("<int:pk>/modifier/", views.UtilisateurModification.as_view(), name="modifier"),
    path("<int:pk>/activer/", views.UtilisateurBasculerActif.as_view(), name="basculer"),
    path("journal/", views.JournalListe.as_view(), name="journal"),
    path("parametres/", views.ParametresModification.as_view(), name="parametres"),
]

from django.urls import include  # noqa: E402

urlpatterns += [path("utilisateurs/", include((app_patterns, "utilisateurs")))]
