"""Jeu de données fictives (livrable 9 du cahier des charges).

Toutes les opérations passent par les méthodes métier (réceptions, ventes, retours),
donc les données de démonstration respectent les mêmes règles que l'application.
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

MOT_DE_PASSE = "Pharma2026!"

COMPTES = [
    ("admin", "Hery", "Rakoto", "Administrateur"),
    ("pharmacien", "Fanja", "Randria", "Pharmacien responsable"),
    ("stock", "Toky", "Andriana", "Gestionnaire de stock"),
    ("caisse", "Mialy", "Rasoa", "Caissier"),
    ("gestion", "Naina", "Rabe", "Responsable de gestion"),
]

CATALOGUE = [
    # nom, générique, catégorie, forme, dosage, labo, prix achat, prix vente, seuil
    ("Doliprane", "Paracétamol", "Antalgiques", "comprime", "500 mg", "Sanofi", 1800, 2600, 40),
    ("Efferalgan", "Paracétamol", "Antalgiques", "comprime", "1 g", "UPSA", 2600, 3800, 30),
    ("Advil", "Ibuprofène", "Anti-inflammatoires", "comprime", "400 mg", "Pfizer", 3200, 4800, 20),
    ("Spasfon", "Phloroglucinol", "Antispasmodiques", "comprime", "80 mg", "Teva", 4200, 6200, 15),
    ("Amoxicilline Biogaran", "Amoxicilline", "Antibiotiques", "gelule", "500 mg", "Biogaran", 5200, 7800, 20),
    ("Augmentin", "Amoxicilline / acide clavulanique", "Antibiotiques", "comprime", "1 g", "GSK", 14500, 21000, 10),
    ("Coartem", "Artéméther / luméfantrine", "Antipaludiques", "comprime", "20/120 mg", "Novartis", 9800, 14500, 25),
    ("Vitamine C Upsa", "Acide ascorbique", "Vitamines", "comprime", "1 g", "UPSA", 3500, 5200, 15),
    ("Smecta", "Diosmectite", "Gastro-entérologie", "sachet", "3 g", "Ipsen", 6800, 9900, 12),
    ("SRO Oralyte", "Sels de réhydratation orale", "Gastro-entérologie", "sachet", "20,5 g", "Pharmalagasy", 450, 800, 50),
    ("Bétadine", "Povidone iodée", "Antiseptiques", "autre", "10 %", "Meda", 5500, 8200, 10),
    ("Toplexil", "Oxomémazine", "ORL et toux", "sirop", "150 ml", "Sanofi", 7200, 10500, 8),
]

FOURNISSEURS = [
    ("Pharmalagasy", "Ankorondrano, Antananarivo", "020 22 000 01", "M. Ravelo"),
    ("Distripharm Madagascar", "Tanjombato, Antananarivo", "020 22 000 02", "Mme Rakotomalala"),
    ("SOPHAMA", "Andraharo, Antananarivo", "020 22 000 03", "M. Randrianarisoa"),
]


class Command(BaseCommand):
    help = "Remplit la base avec des données fictives cohérentes (comptes, catalogue, achats, ventes)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Ajouter même si des médicaments existent déjà.")

    def handle(self, *args, **opts):
        from medicaments.models import Medicament
        if Medicament.objects.exists() and not opts["force"]:
            raise CommandError("La base contient déjà des médicaments. Utilisez --force pour compléter quand même.")
        call_command("init_pharmagest", stdout=self.stdout)
        random.seed(42)
        with transaction.atomic():
            comptes = self.creer_comptes()
            meds = self.creer_catalogue()
            self.creer_achats(meds, comptes)
            self.creer_ventes(meds, comptes)
        self.stdout.write(self.style.SUCCESS("Données de démonstration créées."))
        self.stdout.write(f"Comptes (mot de passe « {MOT_DE_PASSE} ») : " + ", ".join(c[0] for c in COMPTES))

    def creer_comptes(self):
        from utilisateurs.models import ParametrePharmacie
        p = ParametrePharmacie.courant()
        p.nom, p.adresse, p.telephone = "Pharmacie de l'Avenue", "Lot II A 12, Analakely, Antananarivo", "034 00 000 00"
        p.nif, p.stat = "3000000000", "47730 11 2026 0 00001"
        p.save()
        comptes = {}
        for username, prenom, nom, role in COMPTES:
            u, _ = User.objects.get_or_create(username=username, defaults={"first_name": prenom, "last_name": nom,
                                                                           "email": f"{username}@pharmagest.mg"})
            u.set_password(MOT_DE_PASSE)
            u.is_staff = role == "Administrateur"
            u.save()
            u.groups.set([Group.objects.get(name=role)])
            comptes[username] = u
        return comptes

    def creer_catalogue(self):
        from medicaments.models import Categorie, Medicament
        from medicaments.photos import photo_ou_illustration
        meds = []
        for i, (nom, gen, cat, forme, dosage, labo, pa, pv, seuil) in enumerate(CATALOGUE):
            c, _ = Categorie.objects.get_or_create(nom=cat)
            m = Medicament(nom_commercial=nom, denomination_generique=gen, categorie=c, forme=forme, dosage=dosage,
                           laboratoire=labo, code_barres=f"350{i:010d}", prix_achat=Decimal(pa),
                           prix_vente=Decimal(pv), seuil_alerte=seuil)
            image = photo_ou_illustration(m)
            m.photo.save(image.name, image, save=False)
            m.save()
            meds.append(m)
        return meds

    def creer_achats(self, meds, comptes):
        from achats.models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat
        from fournisseurs.models import Fournisseur

        fournisseurs = [Fournisseur.objects.create(raison_sociale=n, adresse=a, telephone=t, contact_principal=c,
                                                   email=f"contact@{n.split()[0].lower()}.mg")
                        for n, a, t, c in FOURNISSEURS]
        aujourdhui = timezone.localdate()
        stock, pharmacien = comptes["stock"], comptes["pharmacien"]

        def commande(fournisseur, lignes, recevoir=True, peremption=None, partiel=False):
            cmd = CommandeAchat.objects.create(fournisseur=fournisseur, cree_par=stock)
            for med, q in lignes:
                LigneAchat.objects.create(commande=cmd, medicament=med, quantite_commandee=q,
                                          prix_achat_unitaire=med.prix_achat)
            cmd.valider(pharmacien)
            if recevoir:
                rec = ReceptionAchat.objects.create(commande=cmd, cree_par=stock)
                for la in cmd.lignes.all():
                    q = la.quantite_commandee // 2 if partiel else la.quantite_commandee
                    d = peremption or aujourdhui + timedelta(days=random.randint(240, 720))
                    LigneReception.objects.create(reception=rec, ligne_achat=la, quantite_recue=q, date_peremption=d,
                                                  numero_lot=f"L{la.medicament_id:02d}{cmd.pk:03d}{random.randint(10, 99)}")
                rec.valider(stock)
            return cmd

        # Approvisionnement principal : tous les produits
        commande(fournisseurs[0], [(m, random.choice([60, 80, 100, 120])) for m in meds[:6]])
        commande(fournisseurs[1], [(m, random.choice([40, 60, 80])) for m in meds[6:]])
        # Un lot qui périme bientôt (alerte) et un lot déjà périmé (exclu de la vente)
        commande(fournisseurs[2], [(meds[7], 20)], peremption=aujourdhui + timedelta(days=25))
        commande(fournisseurs[2], [(meds[9], 30)], peremption=aujourdhui - timedelta(days=10))
        # Une commande partiellement reçue, une commande en attente, un brouillon
        commande(fournisseurs[0], [(meds[2], 40), (meds[3], 30)], partiel=True)
        commande(fournisseurs[1], [(meds[5], 15)], recevoir=False)
        brouillon = CommandeAchat.objects.create(fournisseur=fournisseurs[2], cree_par=stock, notes="À compléter")
        LigneAchat.objects.create(commande=brouillon, medicament=meds[10], quantite_commandee=12,
                                  prix_achat_unitaire=meds[10].prix_achat)

    def creer_ventes(self, meds, comptes):
        from clients.models import Client
        from ventes.models import Paiement, RetourVente, Vente, VenteError

        clients = [Client.objects.create(nom=n, telephone=t) for n, t in
                   [("Rasoanaivo Lalao", "034 11 222 33"), ("Andrianjaka Tiana", "032 44 555 66"),
                    ("Razafy Hanta", "033 77 888 99")]]
        caissier, pharmacien = comptes["caisse"], comptes["pharmacien"]
        ouverture = timezone.localtime().replace(hour=8, minute=0, second=0, microsecond=0)
        ventes = []
        for jour in range(29, -1, -1):
            for _ in range(random.randint(1, 4)):
                v = Vente.objects.create(caissier=caissier, client=random.choice([None, None] + clients))
                try:
                    for med in random.sample(meds, random.randint(1, 3)):
                        v.ajouter(med, random.randint(1, 4))
                except VenteError:
                    v.delete()
                    continue
                mode = random.choice([Paiement.Mode.ESPECES, Paiement.Mode.ESPECES, Paiement.Mode.MOBILE_MONEY])
                montant = v.total if mode != Paiement.Mode.ESPECES else (v.total // 1000 + 1) * 1000
                p = Paiement.objects.create(vente=v, mode=mode, montant=montant, encaisse_par=caissier,
                                            reference=f"MVOLA-{random.randint(100000, 999999)}" if mode != "especes" else "")
                p.confirmer()
                v.valider(caissier)
                moment = min(ouverture - timedelta(days=jour) + timedelta(minutes=random.randint(0, 600)),
                             timezone.now())
                Vente.objects.filter(pk=v.pk).update(valide_le=moment, cree_le=moment)
                ventes.append(v)
        # Un retour validé avec remise en stock, et un retour en attente
        ligne = ventes[-3].lignes.first()
        r = RetourVente.demander(ligne, 1, "Boîte abîmée à la livraison", caissier)
        r.valider(pharmacien, remise_en_stock=True)
        RetourVente.demander(ventes[-1].lignes.first(), 1, "Erreur de produit", caissier)
        # Une vente annulée
        ventes[-5].annuler(pharmacien, "Double saisie par le caissier")
