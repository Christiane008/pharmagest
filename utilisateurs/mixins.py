from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin


class AccesMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Connexion obligatoire + permission précise (RG11).

    Un utilisateur connecté sans la permission reçoit une page 403.
    """

    raise_exception = False

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Vous n'avez pas l'autorisation d'accéder à cette page.")
        return super().handle_no_permission()
