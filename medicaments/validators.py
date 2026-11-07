from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

valider_extension_image = FileExtensionValidator(["jpg", "jpeg", "png"])


def valider_taille_image(fichier):
    limite = settings.PHARMAGEST_TAILLE_MAX_PHOTO
    if fichier and fichier.size > limite:
        raise ValidationError(f"La photo dépasse {limite // (1024 * 1024)} Mo.")
