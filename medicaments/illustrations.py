"""Illustrations de produits pour les médicaments sans photo.

Chaque forme pharmaceutique a son conditionnement (boîte et plaquette, flacon, sachet,
tube, ampoule…) avec le nom, le dosage et la dénomination générique imprimés dessus.
Les illustrations sont génériques : elles ne reproduisent pas les emballages des fabricants.
Pour une vraie photo, il suffit de la téléverser dans la fiche du médicament.
"""
import hashlib
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFilter, ImageFont

TAILLE = 600          # taille finale en pixels
ECHELLE = 2           # dessin en double résolution puis réduction : bords lisses
POLICES = Path(__file__).resolve().parent / "polices"

FOND = (238, 243, 241)
ENCRE = (29, 43, 39)
GRIS = (91, 107, 102)
BLANC = (255, 255, 255)

# Teintes de marque, choisies de façon stable à partir du nom du médicament
TEINTES = [
    (15, 92, 74), (47, 111, 143), (122, 78, 156), (161, 92, 7),
    (78, 125, 46), (138, 59, 59), (31, 78, 121), (176, 74, 46),
]


def _teinte(texte):
    h = int(hashlib.md5(texte.encode()).hexdigest(), 16)
    return TEINTES[h % len(TEINTES)]


def _clair(c, f=0.82):
    return tuple(int(v + (255 - v) * f) for v in c)


def _sombre(c, f=0.25):
    return tuple(int(v * (1 - f)) for v in c)


def _police(taille, gras=False):
    fichier = POLICES / ("IBMPlexSans-600.ttf" if gras else "IBMPlexSans-400.ttf")
    try:
        return ImageFont.truetype(str(fichier), int(taille * ECHELLE))
    except OSError:
        return ImageFont.load_default(size=int(taille * ECHELLE))


def _s(*v):
    """Coordonnées exprimées pour 600 px, converties à l'échelle de dessin."""
    return [x * ECHELLE for x in v]


def _texte_ajuste(d, centre_x, y, texte, largeur_max, taille, gras=False, couleur=ENCRE, min_taille=12):
    """Écrit un texte centré, en réduisant la taille jusqu'à ce qu'il tienne."""
    t = taille
    while t > min_taille:
        f = _police(t, gras)
        if d.textlength(texte, font=f) <= largeur_max * ECHELLE:
            break
        t -= 1
    f = _police(t, gras)
    w = d.textlength(texte, font=f)
    d.text((centre_x * ECHELLE - w / 2, y * ECHELLE), texte, font=f, fill=couleur)
    return t


def _ombre(img, boite, flou=18, opacite=70):
    calque = Image.new("L", img.size, 0)
    ImageDraw.Draw(calque).ellipse(_s(*boite), fill=opacite)
    calque = calque.filter(ImageFilter.GaussianBlur(flou * ECHELLE))
    img.paste((40, 60, 55), mask=calque)


def _etiquette(d, cx, y0, largeur, med, couleur, sur_fond=BLANC, taille_nom=34):
    """Nom, dosage et générique, centrés."""
    _texte_ajuste(d, cx, y0, med.nom_commercial, largeur, taille_nom, gras=True, couleur=_sombre(couleur, .35))
    if med.dosage:
        _texte_ajuste(d, cx, y0 + taille_nom + 10, med.dosage, largeur, 26, gras=True, couleur=ENCRE)
    if med.denomination_generique:
        _texte_ajuste(d, cx, y0 + taille_nom + 46, med.denomination_generique, largeur, 17, couleur=GRIS)


# ---------------------------------------------------------------- conditionnements
def _boite(img, d, med, couleur, pilule):
    """Boîte en carton vue de trois quarts + plaquette posée devant."""
    _ombre(img, (95, 455, 520, 535))
    x0, y0, x1, y1, p = 120, 120, 430, 470, 46      # face avant + profondeur
    # dessus et côté (perspective)
    d.polygon(_s(x0, y0, x0 + p, y0 - p * .6, x1 + p, y0 - p * .6, x1, y0), fill=_clair(couleur, .55))
    d.polygon(_s(x1, y0, x1 + p, y0 - p * .6, x1 + p, y1 - p * .6, x1, y1), fill=_sombre(couleur, .1))
    # face
    d.rectangle(_s(x0, y0, x1, y1), fill=BLANC)
    d.rectangle(_s(x0, y0, x1, y0 + 62), fill=couleur)
    d.rectangle(_s(x0, y1 - 26, x1, y1), fill=couleur)
    _texte_ajuste(d, (x0 + x1) / 2, y0 + 14, med.get_forme_display().upper(), x1 - x0 - 30, 20,
                  gras=True, couleur=BLANC)
    _etiquette(d, (x0 + x1) / 2, y0 + 92, x1 - x0 - 36, med, couleur)
    # pastille de couleur décorative
    d.ellipse(_s(x0 + 24, y1 - 92, x0 + 64, y1 - 52), fill=_clair(couleur, .4))
    d.ellipse(_s(x0 + 52, y1 - 92, x0 + 92, y1 - 52), fill=_clair(couleur, .7))
    # plaquette (blister) posée devant, légèrement décalée
    bx0, by0, bx1, by1 = 300, 400, 530, 520
    _ombre(img, (290, 500, 545, 545), flou=10, opacite=60)
    d.rounded_rectangle(_s(bx0, by0, bx1, by1), radius=14 * ECHELLE, fill=(214, 222, 226),
                        outline=(176, 188, 194), width=2 * ECHELLE)
    for i in range(4):
        for j in range(2):
            cx, cy = bx0 + 32 + i * 56, by0 + 32 + j * 56
            d.ellipse(_s(cx - 22, cy - 22, cx + 22, cy + 22), fill=(236, 241, 243), outline=(196, 206, 210),
                      width=2 * ECHELLE)
            if pilule == "gelule":
                d.rounded_rectangle(_s(cx - 17, cy - 9, cx, cy + 9), radius=9 * ECHELLE, fill=couleur)
                d.rounded_rectangle(_s(cx - 2, cy - 9, cx + 17, cy + 9), radius=9 * ECHELLE, fill=BLANC,
                                    outline=(210, 214, 216), width=ECHELLE)
            else:
                d.ellipse(_s(cx - 14, cy - 14, cx + 14, cy + 14), fill=BLANC, outline=(206, 212, 214),
                          width=ECHELLE)
                d.line(_s(cx - 9, cy, cx + 9, cy), fill=(206, 212, 214), width=2 * ECHELLE)


def _flacon(img, d, med, couleur, verre=(150, 82, 22), compte_gouttes=False):
    """Flacon en verre ambré avec bouchon et étiquette."""
    _ombre(img, (170, 500, 430, 560))
    cx = 300
    # bouchon
    if compte_gouttes:
        d.rounded_rectangle(_s(cx - 26, 70, cx + 26, 150), radius=22 * ECHELLE, fill=_sombre(couleur, .1))
    d.rounded_rectangle(_s(cx - 58, 130, cx + 58, 190), radius=8 * ECHELLE, fill=_sombre(couleur, .15))
    for k in range(6):
        x = cx - 50 + k * 20
        d.line(_s(x, 136, x, 184), fill=_sombre(couleur, .3), width=2 * ECHELLE)
    # col et corps
    d.rectangle(_s(cx - 44, 186, cx + 44, 220), fill=verre)
    d.rounded_rectangle(_s(cx - 120, 210, cx + 120, 540), radius=44 * ECHELLE, fill=verre)
    d.rounded_rectangle(_s(cx - 100, 236, cx - 82, 500), radius=9 * ECHELLE, fill=_clair(verre, .35))
    # étiquette
    d.rectangle(_s(cx - 120, 280, cx + 120, 480), fill=BLANC)
    d.rectangle(_s(cx - 120, 280, cx + 120, 314), fill=couleur)
    if med.forme != "autre":
        _texte_ajuste(d, cx, 285, med.get_forme_display().upper(), 210, 18, gras=True, couleur=BLANC)
    _etiquette(d, cx, 326, 210, med, couleur, taille_nom=30)


def _sachet(img, d, med, couleur):
    """Sachet souple aux bords dentelés."""
    _ombre(img, (120, 505, 480, 560))
    x0, y0, x1, y1 = 140, 90, 460, 520
    d.rectangle(_s(x0, y0, x1, y1), fill=couleur)
    # dentelure haut et bas
    for x in range(x0, x1, 16):
        d.polygon(_s(x, y0, x + 8, y0 - 10, x + 16, y0), fill=couleur)
        d.polygon(_s(x, y1, x + 8, y1 + 10, x + 16, y1), fill=couleur)
    d.rectangle(_s(x0 + 4, y0 + 4, x1 - 4, y0 + 24), fill=_sombre(couleur, .12))
    d.rounded_rectangle(_s(x0 + 26, 170, x1 - 26, 440), radius=16 * ECHELLE, fill=BLANC)
    _texte_ajuste(d, (x0 + x1) / 2, 120, "SACHET", 260, 22, gras=True, couleur=BLANC)
    _etiquette(d, (x0 + x1) / 2, 240, 240, med, couleur)
    d.line(_s(x0 + 20, 476, x1 - 20, 476), fill=_clair(couleur, .4), width=3 * ECHELLE)


def _tube(img, d, med, couleur):
    """Tube de pommade couché, bouchon à droite."""
    _ombre(img, (70, 400, 540, 450))
    y0, y1 = 210, 390
    d.polygon(_s(70, y0 + 20, 90, y0, 90, y1, 70, y1 - 20), fill=_sombre(couleur, .2))     # sertissage
    d.rounded_rectangle(_s(88, y0, 430, y1), radius=26 * ECHELLE, fill=BLANC)
    d.polygon(_s(430, y0, 470, y0 + 40, 470, y1 - 40, 430, y1), fill=(232, 236, 238))
    d.rounded_rectangle(_s(466, y0 + 48, 540, y1 - 48), radius=10 * ECHELLE, fill=couleur)
    d.rectangle(_s(88, y0, 140, y1), fill=couleur)
    cx = 285
    _texte_ajuste(d, cx, y0 + 26, med.nom_commercial, 270, 34, gras=True, couleur=_sombre(couleur, .35))
    if med.dosage:
        _texte_ajuste(d, cx, y0 + 74, med.dosage, 270, 24, gras=True)
    if med.denomination_generique:
        _texte_ajuste(d, cx, y0 + 112, med.denomination_generique, 270, 17, couleur=GRIS)


def _ampoule(img, d, med, couleur):
    """Flacon d'injectable avec capsule."""
    _ombre(img, (190, 500, 410, 550))
    cx = 300
    d.rounded_rectangle(_s(cx - 54, 120, cx + 54, 170), radius=10 * ECHELLE, fill=couleur)
    d.rectangle(_s(cx - 38, 168, cx + 38, 210), fill=(200, 208, 212))
    d.rounded_rectangle(_s(cx - 90, 200, cx + 90, 530), radius=30 * ECHELLE, fill=(224, 236, 240),
                        outline=(184, 198, 204), width=2 * ECHELLE)
    d.rectangle(_s(cx - 90, 300, cx + 90, 470), fill=BLANC)
    d.rectangle(_s(cx - 90, 300, cx + 90, 318), fill=couleur)
    _etiquette(d, cx, 326, 160, med, couleur, taille_nom=26)


def dessiner(medicament):
    """Renvoie une illustration PNG (ContentFile) adaptée à la forme du médicament."""
    couleur = _teinte(medicament.nom_commercial)
    img = Image.new("RGB", (TAILLE * ECHELLE, TAILLE * ECHELLE), FOND)
    d = ImageDraw.Draw(img)
    forme = medicament.forme
    if forme in ("comprime", "gelule"):
        _boite(img, d, medicament, couleur, forme)
    elif forme == "sirop":
        _flacon(img, d, medicament, couleur)
    elif forme == "gouttes":
        _flacon(img, d, medicament, couleur, compte_gouttes=True)
    elif forme == "sachet":
        _sachet(img, d, medicament, couleur)
    elif forme == "pommade":
        _tube(img, d, medicament, couleur)
    elif forme == "injectable":
        _ampoule(img, d, medicament, couleur)
    else:
        _flacon(img, d, medicament, couleur, verre=(70, 110, 120))
    img = img.resize((TAILLE, TAILLE), Image.LANCZOS)
    tampon = BytesIO()
    img.save(tampon, "PNG", optimize=True)
    nom = "".join(c if c.isalnum() else "-" for c in medicament.nom_commercial.lower()).strip("-")
    return ContentFile(tampon.getvalue(), name=f"{nom or 'medicament'}.png")
