"""Petites fabriques pour les tests : créent des objets valides en une ligne."""
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from .roles import creer_groupes


def utilisateur(nom="caisse", role="Caissier"):
    if not Group.objects.exists():
        creer_groupes()
    u = User.objects.create_user(nom, password="Mot-de-passe-1")
    u.groups.add(Group.objects.get(name=role))
    return User.objects.get(pk=u.pk)  # recharge le cache des permissions


def image_png(nom="photo.png", taille=(40, 40)):
    from PIL import Image
    tampon = BytesIO()
    Image.new("RGB", taille, "green").save(tampon, "PNG")
    return SimpleUploadedFile(nom, tampon.getvalue(), content_type="image/png")


def medicament(nom="Doliprane", prix_vente=2600, prix_achat=1800, code=None, seuil=5):
    from medicaments.models import Categorie, Medicament
    cat, _ = Categorie.objects.get_or_create(nom="Antalgiques")
    return Medicament.objects.create(nom_commercial=nom, categorie=cat, dosage="500 mg",
                                     prix_achat=Decimal(prix_achat), prix_vente=Decimal(prix_vente),
                                     code_barres=code, seuil_alerte=seuil)


def commande(med, quantite, auteur, prix=None):
    from achats.models import CommandeAchat, LigneAchat
    from fournisseurs.models import Fournisseur
    f, _ = Fournisseur.objects.get_or_create(raison_sociale="Pharmalagasy")
    cmd = CommandeAchat.objects.create(fournisseur=f, cree_par=auteur)
    LigneAchat.objects.create(commande=cmd, medicament=med, quantite_commandee=quantite,
                              prix_achat_unitaire=prix or med.prix_achat)
    return cmd


def receptionner(cmd, auteur, quantite=None, lot="LOT-A", jours=365, valider=True):
    from achats.models import LigneReception, ReceptionAchat
    rec = ReceptionAchat.objects.create(commande=cmd, cree_par=auteur)
    for la in cmd.lignes.all():
        LigneReception.objects.create(reception=rec, ligne_achat=la, numero_lot=lot,
                                      date_peremption=timezone.localdate() + timedelta(days=jours),
                                      quantite_recue=quantite or la.quantite_commandee)
    if valider:
        rec.valider(auteur)
    return rec


def approvisionner(med, quantite, auteur, lot="LOT-A", jours=365):
    """Commande validée + réception validée : le chemin normal d'une entrée en stock."""
    cmd = commande(med, quantite, auteur)
    cmd.valider(auteur)
    receptionner(cmd, auteur, lot=lot, jours=jours)
    return med.lots.get(numero_lot=lot)


def vente_payee(med, quantite, caissier):
    from ventes.models import Paiement, Vente
    v = Vente.objects.create(caissier=caissier)
    v.ajouter(med, quantite)
    Paiement.objects.create(vente=v, montant=v.total, encaisse_par=caissier).confirmer()
    return v
