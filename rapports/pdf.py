"""Documents PDF générés avec ReportLab (cahier 4.11)."""
from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, A6
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from utilisateurs.models import ParametrePharmacie

from .templatetags.pharmagest import format_ar

VERT = colors.HexColor("#0F5C4A")
GRIS = colors.HexColor("#5B6B66")
STYLES = getSampleStyleSheet()
NORMAL = ParagraphStyle("n", parent=STYLES["Normal"], fontName="Helvetica", fontSize=9, leading=12)
PETIT = ParagraphStyle("p", parent=NORMAL, fontSize=7.5, leading=10, textColor=GRIS)
TITRE = ParagraphStyle("t", parent=NORMAL, fontName="Helvetica-Bold", fontSize=15, leading=19,
                       textColor=VERT)
PHARMA = ParagraphStyle("ph", parent=NORMAL, fontName="Helvetica-Bold", fontSize=11, leading=14)
DROITE = ParagraphStyle("d", parent=NORMAL, alignment=TA_RIGHT)


def _entete(titre, numero=None, date=None, lignes_info=()):
    p = ParametrePharmacie.courant()
    blocs = [Paragraph(p.nom, PHARMA), Paragraph(p.adresse, NORMAL)]
    contact = " – ".join(x for x in [p.telephone, p.email] if x)
    if contact:
        blocs.append(Paragraph(contact, NORMAL))
    ids = " – ".join(x for x in [f"NIF {p.nif}" if p.nif else "", f"STAT {p.stat}" if p.stat else ""] if x)
    if ids:
        blocs.append(Paragraph(ids, PETIT))
    blocs += [Spacer(1, 4 * mm), Paragraph(titre, TITRE)]
    meta = []
    if numero:
        meta.append(f"N° {numero}")
    meta.append(f"Date : {timezone.localtime(date or timezone.now()):%d/%m/%Y %H:%M}")
    blocs.append(Paragraph(" – ".join(meta), NORMAL))
    for l in lignes_info:
        blocs.append(Paragraph(l, NORMAL))
    blocs.append(Spacer(1, 4 * mm))
    return blocs


def _tableau(entetes, lignes, largeurs, total_lignes=(), colonnes_texte=1):
    data = [entetes] + lignes + list(total_lignes)
    t = Table(data, colWidths=largeurs, repeatRows=1)
    style = [
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), VERT),
        ("ALIGN", (colonnes_texte, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, len(lignes)), 0.25, colors.HexColor("#D5DED9")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]
    if total_lignes:
        debut = len(lignes) + 1
        style += [("FONT", (0, debut), (-1, -1), "Helvetica-Bold", 9),
                  ("LINEABOVE", (0, debut), (-1, debut), 0.8, VERT)]
    t.setStyle(TableStyle(style))
    return t


def _reponse(nom, construire, taille=A4, marge=15 * mm):
    tampon = BytesIO()
    doc = SimpleDocTemplate(tampon, pagesize=taille, leftMargin=marge, rightMargin=marge,
                            topMargin=marge, bottomMargin=marge, title=nom, author="PharmaGest")
    elements = construire(doc.width)
    p = ParametrePharmacie.courant()

    def pied(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GRIS)
        canvas.drawString(marge, 8 * mm, p.pied_de_page)
        canvas.drawRightString(taille[0] - marge, 8 * mm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(elements, onFirstPage=pied, onLaterPages=pied)
    reponse = HttpResponse(tampon.getvalue(), content_type="application/pdf")
    reponse["Content-Disposition"] = f'inline; filename="{nom}.pdf"'
    return reponse


# ---------- Ventes ----------
def document_vente(vente, facture=False):
    lignes = list(vente.lignes.select_related("medicament", "lot"))
    info = [f"Caissier : {vente.caissier.get_full_name() or vente.caissier.username}"]
    if vente.client:
        info.append(f"Client : {vente.client}" + (f" – {vente.client.telephone}" if vente.client.telephone else ""))
    if vente.statut == vente.Statut.ANNULEE:
        info.append(f"<font color='#B42318'><b>VENTE ANNULÉE</b> le {timezone.localtime(vente.annule_le):%d/%m/%Y}"
                    f" : {vente.motif_annulation}</font>")

    def construire(largeur):
        el = _entete("Facture" if facture else "Reçu de vente", vente.numero, vente.valide_le, info)
        data = [[Paragraph(f"{l.medicament}<br/><font size=7 color='#5B6B66'>Lot {l.lot.numero_lot} – "
                           f"exp. {l.lot.date_peremption:%m/%Y}</font>", NORMAL),
                 str(l.quantite), format_ar(l.prix_unitaire), format_ar(l.sous_total)] for l in lignes]
        totaux = [["", "", "Total", format_ar(vente.total)]]
        for p in vente.paiements.filter(statut="confirme"):
            totaux.append(["", "", p.get_mode_display(), format_ar(p.montant)])
        if vente.monnaie_a_rendre():
            totaux.append(["", "", "Monnaie rendue", format_ar(vente.monnaie_a_rendre())])
        el.append(_tableau(["Désignation", "Qté", "P.U.", "Montant"], data,
                           [largeur * 0.46, largeur * 0.1, largeur * 0.2, largeur * 0.24], totaux))
        if facture:
            el += [Spacer(1, 6 * mm), Paragraph(
                "Montants en ariary (Ar). Les mentions fiscales applicables (TVA, références légales) "
                "sont à compléter selon le régime de la pharmacie.", PETIT)]
        return el

    nom = f"{'facture' if facture else 'recu'}-{vente.numero}"
    return _reponse(nom, construire, taille=A4 if facture else (105 * mm, 200 * mm), marge=8 * mm if not facture else 15 * mm)


# ---------- Achats ----------
def bon_commande(cmd):
    lignes = list(cmd.lignes.select_related("medicament"))
    info = [f"Fournisseur : <b>{cmd.fournisseur}</b>",
            f"{cmd.fournisseur.adresse} {cmd.fournisseur.telephone}".strip(),
            f"Statut : {cmd.get_statut_display()}"]

    def construire(largeur):
        el = _entete("Bon de commande", cmd.numero, cmd.valide_le or cmd.cree_le, info)
        data = [[str(l.medicament), str(l.quantite_commandee), format_ar(l.prix_achat_unitaire),
                 format_ar(l.montant())] for l in lignes]
        el.append(_tableau(["Médicament", "Qté", "P.U. achat", "Montant"], data,
                           [largeur * 0.46, largeur * 0.12, largeur * 0.2, largeur * 0.22],
                           [["", "", "Total", format_ar(cmd.total())]]))
        if cmd.notes:
            el += [Spacer(1, 4 * mm), Paragraph(f"Notes : {cmd.notes}", NORMAL)]
        return el

    return _reponse(f"bon-commande-{cmd.numero}", construire)


def bon_reception(rec):
    lignes = list(rec.lignes.select_related("ligne_achat__medicament"))
    info = [f"Commande : {rec.commande.numero} – Fournisseur : <b>{rec.commande.fournisseur}</b>",
            f"Statut : {rec.get_statut_display()}"
            + (f" par {rec.recu_par}" if rec.recu_par else "")]

    def construire(largeur):
        el = _entete("Bon de réception", rec.numero, rec.recu_le or rec.cree_le, info)
        data = [[str(l.ligne_achat.medicament), l.numero_lot, f"{l.date_peremption:%d/%m/%Y}",
                 str(l.quantite_recue), format_ar(l.quantite_recue * l.ligne_achat.prix_achat_unitaire)]
                for l in lignes]
        el.append(_tableau(["Médicament", "Lot", "Péremption", "Qté", "Montant"], data, colonnes_texte=3, largeurs=
                           [largeur * 0.34, largeur * 0.17, largeur * 0.17, largeur * 0.1, largeur * 0.22],
                           total_lignes=[["", "", "", "Total", format_ar(rec.total())]]))
        return el

    return _reponse(f"bon-reception-{rec.numero}", construire)


# ---------- Rapports ----------
def rapport_stock(medicaments):
    def construire(largeur):
        el = _entete("Rapport de stock")
        data, valeur = [], 0
        for m in medicaments:
            v = m.stock_total * m.prix_achat
            valeur += v
            alerte = "Rupture" if m.stock_vendable == 0 else ("Faible" if m.stock_vendable <= m.seuil_alerte else "")
            data.append([str(m), m.categorie.nom, str(m.stock_vendable), str(m.seuil_alerte), alerte,
                         format_ar(v)])
        el.append(_tableau(["Médicament", "Catégorie", "Vendable", "Seuil", "Alerte", "Valeur (achat)"],
                           data, [largeur * x for x in (0.3, 0.18, 0.1, 0.08, 0.12, 0.22)],
                           [["", "", "", "", "Total", format_ar(valeur)]], colonnes_texte=2))
        el += [Spacer(1, 3 * mm), Paragraph("Valeur au prix d'achat de la fiche médicament.", PETIT)]
        return el

    return _reponse("rapport-stock", construire)


def rapport_ventes(debut, fin, ventes, ca, rembourse, marge, par_mode):
    def construire(largeur):
        el = _entete("Rapport des ventes", lignes_info=[f"Période : du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}"])
        resume = [["Chiffre d'affaires (ventes validées)", format_ar(ca)],
                  ["Remboursements (retours validés)", format_ar(rembourse)],
                  ["Chiffre d'affaires net", format_ar(ca - rembourse)],
                  ["Marge commerciale estimée", format_ar(marge)]]
        resume += [[f"Encaissé – {mode}", format_ar(v)] for mode, v in par_mode.items() if v]
        el.append(_tableau(["Indicateur", "Montant"], resume, [largeur * 0.65, largeur * 0.35]))
        el += [Spacer(1, 2 * mm), Paragraph(
            "La marge commerciale (prix de vente – coût d'achat des lots vendus) n'est pas un bénéfice "
            "net : elle ne tient pas compte des charges de la pharmacie.", PETIT), Spacer(1, 5 * mm)]
        data = [[v.numero, f"{timezone.localtime(v.valide_le):%d/%m/%Y %H:%M}", str(v.client or "Comptoir"),
                 v.caissier.username, format_ar(v.total)] for v in ventes]
        el.append(_tableau(["N°", "Date", "Client", "Caissier", "Total"], data,
                           [largeur * x for x in (0.2, 0.22, 0.24, 0.14, 0.2)],
                           [["", "", "", "Total", format_ar(ca)]], colonnes_texte=4))
        return el

    return _reponse(f"rapport-ventes-{debut:%Y%m%d}-{fin:%Y%m%d}", construire)


def rapport_achats(debut, fin, receptions, total):
    def construire(largeur):
        el = _entete("Rapport des achats", lignes_info=[f"Période : du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}"])
        data = [[r.numero, r.commande.numero, str(r.commande.fournisseur),
                 f"{timezone.localtime(r.recu_le):%d/%m/%Y}", format_ar(r.total())] for r in receptions]
        el.append(_tableau(["Réception", "Commande", "Fournisseur", "Date", "Montant"], data,
                           [largeur * x for x in (0.18, 0.18, 0.28, 0.14, 0.22)],
                           [["", "", "", "Total", format_ar(total)]], colonnes_texte=4))
        return el

    return _reponse(f"rapport-achats-{debut:%Y%m%d}-{fin:%Y%m%d}", construire)


def rapport_peremptions(lots):
    def construire(largeur):
        el = _entete("Produits périmés ou proches de la péremption",
                     lignes_info=[f"Seuil d'alerte : {lots['jours']} jours"])
        data = []
        for titre, qs in (("Périmé", lots["perimes"]), ("Proche", lots["proches"])):
            for l in qs:
                data.append([str(l.medicament), l.numero_lot, f"{l.date_peremption:%d/%m/%Y}",
                             str(l.jours_avant_peremption()), str(l.quantite_disponible), titre])
        el.append(_tableau(["Médicament", "Lot", "Péremption", "Jours", "Qté", "État"], data,
                           [largeur * x for x in (0.34, 0.16, 0.16, 0.1, 0.1, 0.14)], colonnes_texte=3))
        return el

    return _reponse("peremptions", construire)
