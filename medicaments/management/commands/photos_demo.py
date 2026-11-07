from django.core.management.base import BaseCommand

from medicaments.models import Medicament
from medicaments.photos import photo_demo


class Command(BaseCommand):
    help = "Remplace la photo des médicaments de démonstration par la vraie photo du produit."

    def handle(self, *args, **opts):
        n = 0
        for med in Medicament.objects.all():
            image = photo_demo(med)
            if image is None:
                continue
            if med.photo:
                med.photo.delete(save=False)
            med.photo.save(image.name, image, save=True)
            n += 1
            self.stdout.write(f"  {med}")
        self.stdout.write(self.style.SUCCESS(f"{n} photo(s) installée(s)."))
