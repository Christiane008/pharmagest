from django.utils import timezone


def prochain_numero(modele, prefixe, champ="numero", largeur=4):
    """Numéro lisible et séquentiel par année : CA-2026-0001.

    À appeler dans une transaction : il lit le dernier numéro de l'année.
    """
    annee = timezone.localdate().year
    debut = f"{prefixe}-{annee}-"
    dernier = (
        modele.objects.filter(**{f"{champ}__startswith": debut})
        .order_by(f"-{champ}")
        .values_list(champ, flat=True)
        .first()
    )
    suivant = int(dernier.rsplit("-", 1)[1]) + 1 if dernier else 1
    return f"{debut}{suivant:0{largeur}d}"
