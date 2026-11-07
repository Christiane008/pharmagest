from django.core.management.base import BaseCommand

from medicaments.illustrations import dessiner
from medicaments.models import Medicament


class Command(BaseCommand):
    help = ("Crée une illustration de produit pour chaque médicament sans photo. "
            "Les photos téléversées par les utilisateurs ne sont jamais remplacées, sauf avec --toutes.")

    def add_arguments(self, parser):
        parser.add_argument("--toutes", action="store_true",
                            help="Remplacer aussi les photos existantes (y compris les vraies photos).")

    def handle(self, *args, **opts):
        qs = Medicament.objects.all()
        if not opts["toutes"]:
            qs = qs.filter(photo__isnull=True) | qs.filter(photo="")
        n = 0
        for med in qs:
            if med.photo:
                med.photo.delete(save=False)
            image = dessiner(med)
            med.photo.save(image.name, image, save=True)
            n += 1
        self.stdout.write(self.style.SUCCESS(f"{n} illustration(s) créée(s)."))
