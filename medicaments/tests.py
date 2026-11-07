import shutil
import tempfile
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from utilisateurs.fabrique import approvisionner, image_png, medicament, utilisateur

from .models import Categorie, Medicament

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class MedicamentTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.pharmacien = utilisateur("pharmacien", "Pharmacien responsable")
        self.client.force_login(self.pharmacien)
        self.cat = Categorie.objects.create(nom="Vitamines")

    def donnees(self, **extra):
        d = {"nom_commercial": "Vitamine C", "categorie": self.cat.pk, "forme": "comprime", "dosage": "1 g",
             "prix_achat": "3500", "prix_vente": "5200", "seuil_alerte": "10", "statut": "actif"}
        d.update(extra)
        return d

    def test_ajouter_avec_photo_et_affichage(self):
        """Section 9 : médicament enregistré et photo affichée."""
        r = self.client.post(reverse("medicaments:creer"), self.donnees(photo=image_png()))
        m = Medicament.objects.get()
        self.assertRedirects(r, m.get_absolute_url())
        self.assertTrue(m.photo.name.startswith("medicaments/"))
        self.assertContains(self.client.get(m.get_absolute_url()), m.photo.url)

    def test_illustration_si_pas_de_photo(self):
        self.client.post(reverse("medicaments:creer"), self.donnees(forme="sirop"))
        m = Medicament.objects.get()
        self.assertTrue(m.photo.name.endswith(".png"))
        from PIL import Image
        self.assertEqual(Image.open(m.photo.path).size, (600, 600))

    def test_generer_photos_ne_remplace_pas_une_vraie_photo(self):
        from django.core.management import call_command
        sans = medicament(nom="Sans photo")
        avec = medicament(nom="Avec photo")
        avec.photo.save("vraie.png", image_png(), save=True)
        call_command("generer_photos", stdout=open("/dev/null", "w"))
        sans.refresh_from_db(); avec.refresh_from_db()
        self.assertTrue(sans.photo)
        self.assertIn("vraie", avec.photo.name)

    def test_photos_demo_installees(self):
        from django.core.management import call_command
        m = medicament(nom="Smecta")
        call_command("photos_demo", stdout=open("/dev/null", "w"))
        m.refresh_from_db()
        self.assertTrue(m.photo.name.startswith("medicaments/smecta"))
        self.assertLess(m.photo.size, 2 * 1024 * 1024)

    def test_modifier(self):
        m = medicament()
        self.client.post(reverse("medicaments:modifier", args=[m.pk]),
                         self.donnees(nom_commercial="Doliprane", prix_vente="2900", prix_achat="1800"))
        m.refresh_from_db()
        self.assertEqual(m.prix_vente, Decimal("2900"))

    def test_code_barres_unique_RG02(self):
        medicament(code="3400000000001")
        r = self.client.post(reverse("medicaments:creer"), self.donnees(code_barres="3400000000001"))
        self.assertContains(r, "déjà utilisé")
        with self.assertRaises(IntegrityError), transaction.atomic():
            medicament(nom="Autre", code="3400000000001")

    def test_code_barres_vide_plusieurs_fois(self):
        medicament(nom="A")
        medicament(nom="B")
        self.assertEqual(Medicament.objects.filter(code_barres__isnull=True).count(), 2)

    def test_prix_negatif_refuse_RG03(self):
        r = self.client.post(reverse("medicaments:creer"), self.donnees(prix_vente="-10"))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Medicament.objects.exists())

    def test_photo_trop_lourde_ou_mauvais_format(self):
        import os
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        tampon = BytesIO()
        Image.frombytes("RGB", (1000, 1000), os.urandom(3_000_000)).save(tampon, "PNG")
        self.assertGreater(tampon.tell(), 2 * 1024 * 1024)
        grosse = SimpleUploadedFile("grosse.png", tampon.getvalue(), content_type="image/png")
        r = self.client.post(reverse("medicaments:creer"), self.donnees(photo=grosse))
        self.assertContains(r, "dépasse 2 Mo")
        faux = SimpleUploadedFile("virus.png", b"pas une image", content_type="image/png")
        r = self.client.post(reverse("medicaments:creer"), self.donnees(photo=faux))
        self.assertFalse(Medicament.objects.exists())

    def test_supprimer_sans_historique(self):
        m = medicament()
        self.client.post(reverse("medicaments:supprimer", args=[m.pk]))
        self.assertFalse(Medicament.objects.exists())

    def test_archiver_si_historique(self):
        """Section 9 : supprimer ou archiver un médicament → historique protégé."""
        m = medicament()
        approvisionner(m, 10, utilisateur("stock", "Gestionnaire de stock"))
        self.client.post(reverse("medicaments:supprimer", args=[m.pk]))
        m.refresh_from_db()
        self.assertEqual(m.statut, Medicament.Statut.ARCHIVE)
        self.assertEqual(m.lots.count(), 1)

    def test_categorie_utilisee_non_supprimable(self):
        m = medicament()
        self.client.post(reverse("medicaments:categorie_supprimer", args=[m.categorie.pk]))
        self.assertTrue(Categorie.objects.filter(pk=m.categorie.pk).exists())
        self.client.post(reverse("medicaments:categorie_supprimer", args=[self.cat.pk]))
        self.assertFalse(Categorie.objects.filter(pk=self.cat.pk).exists())

    def test_recherche_filtre_tri_pagination(self):
        for i in range(20):
            medicament(nom=f"Produit {i:02d}", code=f"C{i}")
        r = self.client.get(reverse("medicaments:liste"), {"q": "C7"})
        self.assertEqual(list(r.context["object_list"]), [Medicament.objects.get(code_barres="C7")])
        r = self.client.get(reverse("medicaments:liste"), {"tri": "-nom"})
        self.assertEqual(r.context["object_list"][0].nom_commercial, "Produit 19")
        self.assertTrue(r.context["is_paginated"])
        r = self.client.get(reverse("medicaments:liste"), {"categorie": self.cat.pk})
        self.assertEqual(len(r.context["object_list"]), 0)
