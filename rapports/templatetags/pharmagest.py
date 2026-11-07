from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


def format_ar(valeur):
    try:
        v = Decimal(valeur or 0).quantize(Decimal("1"))
    except (InvalidOperation, TypeError):
        return valeur
    signe = "-" if v < 0 else ""
    return f"{signe}{abs(int(v)):,}".replace(",", " ") + " Ar"


@register.filter
def ar(valeur):
    """85000 → « 85 000 Ar »."""
    return format_ar(valeur)


@register.simple_tag(takes_context=True)
def url_page(context, numero):
    params = context["request"].GET.copy()
    params["page"] = numero
    return "?" + params.urlencode()
