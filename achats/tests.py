from django.test import TestCase
from django.urls import reverse

from utilisateurs.fabrique import commande, medicament, receptionner, utilisateur

from .models import AchatError, CommandeAchat


class AchatTests(TestCase):
    def setUp(self):
        self.stock = utilisateur("stock", "Gestionnaire de stock")
        self.pharmacien = utilisateur("pharmacien", "Pharmacien responsable")
        self.med = medicament()

    def test_commande_ne_modifie_pas_le_stock_RG04(self):
        cmd = commande(self.med, 20, self.stock)
        cmd.valider(self.pharmacien)
        self.assertEqual(self.med.stock_disponible(), 0)

    def test_reception_de_20_augmente_le_stock_une_seule_fois_RG05(self):
        """Section 9 : réceptionner un achat de 20 unités → stock +20 une seule fois."""
        cmd = commande(self.med, 20, self.stock)
        cmd.valider(self.pharmacien)
        rec = receptionner(cmd, self.stock)
        self.assertEqual(self.med.stock_disponible(), 20)
        with self.assertRaises(AchatError):
            rec.valider(self.stock)
        self.assertEqual(self.med.stock_disponible(), 20)
        self.assertEqual(self.med.lots.get().mouvements.count(), 1)
        cmd.refresh_from_db()
        self.assertEqual(cmd.statut, CommandeAchat.Statut.COMPLETE)

    def test_double_validation_par_la_vue(self):
        cmd = commande(self.med, 20, self.stock)
        cmd.valider(self.pharmacien)
        rec = receptionner(cmd, self.stock, valider=False)
        self.client.force_login(self.stock)
        url = reverse("achats:reception_valider", args=[rec.pk])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(self.med.stock_disponible(), 20)

    def test_reception_partielle_puis_complete(self):
        cmd = commande(self.med, 20, self.stock)
        cmd.valider(self.pharmacien)
        receptionner(cmd, self.stock, quantite=8, lot="L1")
        cmd.refresh_from_db()
        self.assertEqual(cmd.statut, CommandeAchat.Statut.PARTIELLE)
        self.assertEqual(cmd.lignes.get().reste_a_recevoir(), 12)
        receptionner(cmd, self.stock, quantite=12, lot="L2")
        cmd.refresh_from_db()
        self.assertEqual(cmd.statut, CommandeAchat.Statut.COMPLETE)
        self.assertEqual(self.med.stock_disponible(), 20)

    def test_reception_superieure_au_reste_refusee(self):
        cmd = commande(self.med, 10, self.stock)
        cmd.valider(self.pharmacien)
        rec = receptionner(cmd, self.stock, quantite=15, valider=False)
        with self.assertRaises(AchatError):
            rec.valider(self.stock)
        self.assertEqual(self.med.stock_disponible(), 0)

    def test_reception_impossible_avant_validation(self):
        cmd = commande(self.med, 10, self.stock)
        rec = receptionner(cmd, self.stock, valider=False)
        with self.assertRaises(AchatError):
            rec.valider(self.stock)

    def test_annulation(self):
        cmd = commande(self.med, 10, self.stock)
        cmd.valider(self.pharmacien)
        cmd.annuler(self.pharmacien)
        self.assertEqual(cmd.statut, CommandeAchat.Statut.ANNULEE)
        cmd2 = commande(self.med, 10, self.stock)
        cmd2.valider(self.pharmacien)
        receptionner(cmd2, self.stock, quantite=5)
        with self.assertRaises(AchatError):
            cmd2.annuler(self.pharmacien)

    def test_creation_par_formulaire(self):
        self.client.force_login(self.stock)
        from fournisseurs.models import Fournisseur
        f = Fournisseur.objects.create(raison_sociale="SOPHAMA")
        data = {"fournisseur": f.pk, "notes": "", "lignes-TOTAL_FORMS": "4", "lignes-INITIAL_FORMS": "0",
                "lignes-MIN_NUM_FORMS": "0", "lignes-MAX_NUM_FORMS": "1000",
                "lignes-0-medicament": self.med.pk, "lignes-0-quantite_commandee": "30",
                "lignes-0-prix_achat_unitaire": ""}
        r = self.client.post(reverse("achats:commande_creer"), data)
        cmd = CommandeAchat.objects.get()
        self.assertRedirects(r, cmd.get_absolute_url())
        self.assertEqual(cmd.lignes.get().prix_achat_unitaire, self.med.prix_achat)
        self.assertEqual(cmd.statut, CommandeAchat.Statut.BROUILLON)
