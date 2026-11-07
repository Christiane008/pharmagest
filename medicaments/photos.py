"""Photos réelles fournies pour le jeu de démonstration (dossier photos_demo/)."""
from pathlib import Path

from django.core.files.base import ContentFile

DOSSIER = Path(__file__).resolve().parent / "photos_demo"

# nom commercial → fichier
PHOTOS_DEMO = {
    "Doliprane": "doliprane.jpg",
    "Efferalgan": "efferalgan.jpg",
    "Advil": "advil.jpg",
    "Spasfon": "spasfon.jpg",
    "Amoxicilline Biogaran": "amoxicilline.jpg",
    "Augmentin": "augmentin.jpg",
    "Coartem": "coartem.jpg",
    "Vitamine C Upsa": "vitamine-c.jpg",
    "Smecta": "smecta.jpg",
    "SRO Oralyte": "sro.jpg",
    "Bétadine": "betadine.jpg",
    "Toplexil": "toplexil.jpg",
}


def photo_demo(medicament):
    """Renvoie la photo réelle du médicament (ContentFile), ou None s'il n'y en a pas."""
    fichier = PHOTOS_DEMO.get(medicament.nom_commercial)
    if not fichier or not (DOSSIER / fichier).exists():
        return None
    return ContentFile((DOSSIER / fichier).read_bytes(), name=fichier)


def photo_ou_illustration(medicament):
    from .illustrations import dessiner
    return photo_demo(medicament) or dessiner(medicament)
