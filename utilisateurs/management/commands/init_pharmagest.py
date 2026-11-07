from django.core.management.base import BaseCommand

from utilisateurs.models import ParametrePharmacie
from utilisateurs.roles import creer_groupes


class Command(BaseCommand):
    help = "Crée les cinq rôles (groupes et permissions) et les paramètres de la pharmacie."

    def handle(self, *args, **options):
        roles = creer_groupes()
        ParametrePharmacie.courant()
        for r in roles:
            self.stdout.write(f"  rôle prêt : {r}")
        self.stdout.write(self.style.SUCCESS("PharmaGest initialisé."))
