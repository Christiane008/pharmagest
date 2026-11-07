from .models import ParametrePharmacie


def pharmacie(request):
    if not request.user.is_authenticated:
        return {}
    return {"pharmacie": ParametrePharmacie.courant()}
