import gzip
from datetime import datetime

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Sauvegarde toutes les données dans sauvegardes/pharmagest-AAAAMMJJ-HHMM.json.gz"

    def handle(self, *args, **options):
        dossier = settings.PHARMAGEST_DOSSIER_SAUVEGARDES
        dossier.mkdir(parents=True, exist_ok=True)
        chemin = dossier / f"pharmagest-{datetime.now():%Y%m%d-%H%M%S}.json.gz"
        with gzip.open(chemin, "wt", encoding="utf-8") as f:
            call_command(
                "dumpdata", "--natural-foreign", "--natural-primary",
                "--exclude=contenttypes", "--exclude=auth.permission",
                "--exclude=admin.logentry", "--exclude=sessions",
                "--indent=1", stdout=f,
            )
        self.stdout.write(self.style.SUCCESS(f"Sauvegarde écrite : {chemin}"))
        self.stdout.write("Restauration : python manage.py loaddata " + str(chemin))
