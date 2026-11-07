import gzip
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from medicaments.models import Medicament
from stock.models import LotStock
from ventes.models import Vente

from .fabrique import approvisionner, medicament, utilisateur, vente_payee


class PermissionsTests(TestCase):
    def setUp(self):
        self.caisse = utilisateur("caisse", "Caissier")
        self.stock = utilisateur("stock", "Gestionnaire de stock")

    def test_acces_sans_permission_interdit_RG11(self):
        """Section 9 : tenter un accès sans permission → accès interdit."""
        self.client.force_login(self.caisse)
        for url in ("/achats/", "/stock/inventaire/", "/utilisateurs/", "/fournisseurs/nouveau/"):
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_anonyme_redirige_vers_connexion(self):
        r = self.client.get("/ventes/")
        self.assertRedirects(r, "/connexion/?next=/ventes/")

    def test_action_post_interdite_meme_en_connaissant_l_url(self):
        med = medicament()
        lot = approvisionner(med, 10, self.stock)
        self.client.force_login(self.caisse)
        r = self.client.post(reverse("stock:corriger", args=[lot.pk]), {"quantite_comptee": 0, "motif": "x"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(LotStock.objects.get(pk=lot.pk).quantite_disponible, 10)

    def test_gestionnaire_ne_peut_pas_vendre(self):
        self.client.force_login(self.stock)
        self.assertEqual(self.client.get(reverse("ventes:nouvelle")).status_code, 403)

    def test_compte_desactive_ne_peut_pas_se_connecter(self):
        self.caisse.is_active = False
        self.caisse.save()
        self.assertFalse(self.client.login(username="caisse", password="Mot-de-passe-1"))

    def test_mot_de_passe_hache(self):
        self.assertNotIn("Mot-de-passe-1", self.caisse.password)
        self.assertTrue(self.caisse.check_password("Mot-de-passe-1"))


class DocumentsEtSauvegardeTests(TestCase):
    def setUp(self):
        self.stock = utilisateur("stock", "Gestionnaire de stock")
        self.caisse = utilisateur("caisse", "Caissier")
        self.admin = utilisateur("admin", "Administrateur")
        self.med = medicament()
        approvisionner(self.med, 10, self.stock)
        self.vente = vente_payee(self.med, 3, self.caisse)
        self.vente.valider(self.caisse)

    def test_recu_pdf(self):
        """Section 9 : générer un reçu PDF lisible."""
        self.client.force_login(self.caisse)
        r = self.client.get(reverse("pdf_recu", args=[self.vente.pk]))
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))

    def test_totaux_du_recu(self):
        from rapports.templatetags.pharmagest import format_ar
        self.assertEqual(format_ar(self.vente.total), "7 800 Ar")

    def test_tous_les_pdf(self):
        self.client.force_login(self.admin)
        cmd = self.med.lignes_achat.first().commande
        for url in [reverse("pdf_facture", args=[self.vente.pk]), reverse("pdf_bon_commande", args=[cmd.pk]),
                    reverse("pdf_bon_reception", args=[cmd.receptions.first().pk]), reverse("pdf_rapport_stock"),
                    reverse("pdf_peremptions"), reverse("pdf_rapport_ventes"), reverse("pdf_rapport_achats")]:
            r = self.client.get(url)
            self.assertTrue(r.content.startswith(b"%PDF"), url)

    def test_tableau_de_bord_calcule_depuis_les_donnees(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("tableau_de_bord"))
        self.assertEqual(r.context["kpi"]["ca_jour"], self.vente.total)
        self.assertEqual(r.context["kpi"]["medicaments_actifs"], 1)

    def test_restaurer_une_sauvegarde(self):
        """Section 9 : restaurer une sauvegarde → données récupérées correctement."""
        dossier = Path(tempfile.mkdtemp())
        with override_settings(PHARMAGEST_DOSSIER_SAUVEGARDES=dossier):
            call_command("sauvegarder", stdout=open("/dev/null", "w"))
        fichier = next(dossier.glob("*.json.gz"))
        avant = (Medicament.objects.count(), LotStock.objects.get().quantite_disponible, Vente.objects.get().total)
        call_command("flush", interactive=False, verbosity=0)
        self.assertEqual(Medicament.objects.count(), 0)
        call_command("loaddata", str(fichier), verbosity=0)
        apres = (Medicament.objects.count(), LotStock.objects.get().quantite_disponible, Vente.objects.get().total)
        self.assertEqual(avant, apres)
