from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from stock import services
from stock.models import LotStock, MouvementStock
from utilisateurs.fabrique import approvisionner, medicament, utilisateur, vente_payee

from .models import Paiement, RetourVente, Vente, VenteError


class VenteTests(TestCase):
    def setUp(self):
        self.stock = utilisateur("stock", "Gestionnaire de stock")
        self.caisse = utilisateur("caisse", "Caissier")
        self.pharmacien = utilisateur("pharmacien", "Pharmacien responsable")
        self.med = medicament()
        self.lot = approvisionner(self.med, 20, self.stock)

    # ----- Section 9 du cahier des charges -----
    def test_vendre_3_unites_diminue_le_stock_de_3_une_seule_fois_RG06(self):
        v = vente_payee(self.med, 3, self.caisse)
        v.valider(self.caisse)
        self.assertEqual(self.med.stock_disponible(), 17)
        with self.assertRaises(VenteError):
            v.valider(self.caisse)
        self.assertEqual(self.med.stock_disponible(), 17)
        self.assertEqual(MouvementStock.objects.filter(type="sortie").count(), 1)

    def test_vendre_plus_que_le_stock_refuse_RG07(self):
        v = Vente.objects.create(caissier=self.caisse)
        with self.assertRaises(VenteError):
            v.ajouter(self.med, 21)
        self.assertFalse(v.lignes.exists())

    def test_vendre_un_lot_perime_refuse_RG08(self):
        LotStock.objects.filter(pk=self.lot.pk).update(date_peremption=timezone.localdate() - timedelta(days=1))
        v = Vente.objects.create(caissier=self.caisse)
        with self.assertRaises(VenteError):
            v.ajouter(self.med, 1)
        self.lot.refresh_from_db()
        with self.assertRaises(services.StockError):
            services.sortir(self.lot, 1, None, self.caisse)

    def test_lot_bloque_exclu_RG08(self):
        LotStock.objects.filter(pk=self.lot.pk).update(bloque=True)
        with self.assertRaises(VenteError):
            Vente.objects.create(caissier=self.caisse).ajouter(self.med, 1)

    def test_lot_devenu_indisponible_entre_ajout_et_validation(self):
        v = vente_payee(self.med, 5, self.caisse)
        LotStock.objects.filter(pk=self.lot.pk).update(bloque=True)
        with self.assertRaises(VenteError):
            v.valider(self.caisse)
        v.refresh_from_db()
        self.assertEqual(v.statut, Vente.Statut.BROUILLON)
        self.assertEqual(LotStock.objects.get(pk=self.lot.pk).quantite_disponible, 20)

    def test_deux_validations_simultanees_aucune_double_sortie(self):
        """Section 9 : la base elle-même refuse une seconde sortie et un stock négatif."""
        v = vente_payee(self.med, 3, self.caisse)
        v.valider(self.caisse)
        ligne = v.lignes.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            MouvementStock.objects.create(lot=self.lot, type="sortie", quantite=-3, ligne_vente=ligne,
                                          utilisateur=self.caisse)
        with self.assertRaises(IntegrityError), transaction.atomic():
            LotStock.objects.filter(pk=self.lot.pk).update(quantite_disponible=-1)

    def test_quantite_nulle_ou_negative_refusee_RG03(self):
        v = Vente.objects.create(caissier=self.caisse)
        for q in (0, -2):
            with self.assertRaises(VenteError):
                v.ajouter(self.med, q)
        self.client.force_login(self.caisse)
        self.client.post(reverse("ventes:caisse", args=[v.pk]),
                         {"action": "ajouter", "medicament_id": self.med.pk, "quantite": "-5"})
        self.assertFalse(v.lignes.exists())

    def test_prix_historique_conserve_RG12(self):
        v = vente_payee(self.med, 2, self.caisse)
        v.valider(self.caisse)
        self.med.prix_vente = Decimal("9999")
        self.med.save()
        ligne = v.lignes.get()
        self.assertEqual(ligne.prix_unitaire, Decimal("2600"))
        self.assertEqual(Vente.objects.get(pk=v.pk).total, Decimal("5200"))

    def test_paiement_insuffisant_refuse(self):
        v = Vente.objects.create(caissier=self.caisse)
        v.ajouter(self.med, 2)
        Paiement.objects.create(vente=v, montant=1000, encaisse_par=self.caisse).confirmer()
        with self.assertRaises(VenteError):
            v.valider(self.caisse)

    def test_mobile_money_confirme_seulement_avec_reference(self):
        v = Vente.objects.create(caissier=self.caisse)
        v.ajouter(self.med, 1)
        p = Paiement.objects.create(vente=v, mode="mobile_money", montant=v.total, encaisse_par=self.caisse)
        self.assertEqual(v.montant_paye(), 0)
        with self.assertRaises(VenteError):
            p.confirmer()
        p.reference = "MVOLA-123456"
        p.confirmer()
        self.assertEqual(v.montant_paye(), v.total)

    def test_fefo_peremption_la_plus_proche_d_abord(self):
        proche = approvisionner(self.med, 4, self.stock, lot="PROCHE", jours=40)
        v = vente_payee(self.med, 6, self.caisse)
        lignes = list(v.lignes.order_by("id"))
        self.assertEqual([(l.lot.numero_lot, l.quantite) for l in lignes], [("PROCHE", 4), ("LOT-A", 2)])
        v.valider(self.caisse)
        proche.refresh_from_db()
        self.assertEqual(proche.quantite_disponible, 0)

    def test_caissier_et_date_enregistres_RG09(self):
        v = vente_payee(self.med, 1, self.caisse)
        v.valider(self.caisse)
        self.assertEqual(v.caissier, self.caisse)
        self.assertIsNotNone(v.valide_le)
        self.assertTrue(v.numero.startswith(f"V-{timezone.localdate().year}-"))
        from utilisateurs.models import JournalAudit
        self.assertTrue(JournalAudit.objects.filter(action="VALIDER", objet_id=v.pk, utilisateur=self.caisse).exists())

    def test_vente_par_la_caisse_de_bout_en_bout(self):
        self.client.force_login(self.caisse)
        r = self.client.get(reverse("ventes:nouvelle"))
        v = Vente.objects.get()
        url = reverse("ventes:caisse", args=[v.pk])
        self.client.post(url, {"action": "ajouter", "medicament_id": self.med.pk, "quantite": "3"})
        self.client.post(url, {"action": "payer", "mode": "especes", "montant": "10000", "reference": ""})
        r = self.client.post(url, {"action": "valider"})
        v.refresh_from_db()
        self.assertRedirects(r, reverse("ventes:detail", args=[v.pk]))
        self.assertEqual(v.statut, Vente.Statut.VALIDEE)
        self.assertEqual(v.monnaie_a_rendre(), Decimal("2200"))
        self.assertEqual(self.med.stock_disponible(), 17)
        r = self.client.post(url, {"action": "valider"})   # double clic
        self.assertEqual(self.med.stock_disponible(), 17)

    # ----- Annulations et retours (RG10) -----
    def test_annulation_compensatoire(self):
        v = vente_payee(self.med, 5, self.caisse)
        v.valider(self.caisse)
        v.annuler(self.pharmacien, "Erreur de saisie")
        self.assertEqual(self.med.stock_disponible(), 20)
        self.assertTrue(Vente.objects.filter(pk=v.pk, statut="annulee").exists())
        self.assertEqual(MouvementStock.objects.filter(type="annulation").count(), 1)
        with self.assertRaises(VenteError):
            v.annuler(self.pharmacien, "encore")

    def test_vente_validee_jamais_supprimee(self):
        from django.db.models import ProtectedError
        v = vente_payee(self.med, 1, self.caisse)
        v.valider(self.caisse)
        with self.assertRaises(ProtectedError):
            v.delete()

    def test_retour_avec_remise_en_stock(self):
        v = vente_payee(self.med, 4, self.caisse)
        v.valider(self.caisse)
        r = RetourVente.demander(v.lignes.get(), 2, "Boîte abîmée", self.caisse)
        self.assertEqual(self.med.stock_disponible(), 16)
        r.valider(self.pharmacien, remise_en_stock=True)
        self.assertEqual(self.med.stock_disponible(), 18)
        self.assertEqual(r.montant_rembourse, Decimal("5200"))
        with self.assertRaises(VenteError):
            r.valider(self.pharmacien, remise_en_stock=True)
        self.assertEqual(self.med.stock_disponible(), 18)

    def test_retour_sans_remise_et_quantite_limitee(self):
        v = vente_payee(self.med, 2, self.caisse)
        v.valider(self.caisse)
        ligne = v.lignes.get()
        with self.assertRaises(VenteError):
            RetourVente.demander(ligne, 3, "trop", self.caisse)
        r = RetourVente.demander(ligne, 2, "Produit ouvert", self.caisse)
        r.valider(self.pharmacien, remise_en_stock=False)
        self.assertEqual(self.med.stock_disponible(), 18)
        with self.assertRaises(VenteError):
            RetourVente.demander(ligne, 1, "encore", self.caisse)

    def test_annulation_apres_retour_remis_en_stock_sans_double_compte(self):
        v = vente_payee(self.med, 5, self.caisse)
        v.valider(self.caisse)
        RetourVente.demander(v.lignes.get(), 2, "x", self.caisse).valider(self.pharmacien, True)
        v.annuler(self.pharmacien, "Annulation après retour")
        self.assertEqual(self.med.stock_disponible(), 20)

    def test_somme_des_mouvements_egale_au_stock(self):
        v = vente_payee(self.med, 7, self.caisse)
        v.valider(self.caisse)
        services.corriger(self.lot, 12, "Inventaire", self.stock)
        lot = LotStock.objects.get(pk=self.lot.pk)
        from django.db.models import Sum
        self.assertEqual(lot.mouvements.aggregate(t=Sum("quantite"))["t"], lot.quantite_disponible)
