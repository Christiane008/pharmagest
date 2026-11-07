# PharmaGest — Application web de gestion de pharmacie (Django)

Gestion des médicaments (avec photos), fournisseurs, clients, achats et réceptions, stock par lots
avec péremptions (FEFO), caisse et ventes, retours, utilisateurs et rôles, tableau de bord et documents PDF.

Python · Django · SQLite (PostgreSQL en production) · Bootstrap 5 · Pillow · ReportLab

## Démarrage rapide

```bash
cd PharmaGest
python -m venv venv                 # ou : conda create -n pharmagest python=3.12
source venv/bin/activate            # Windows : venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py donnees_demo       # rôles + jeu de données fictives (avec photos)
python manage.py runserver
```

Ouvrir http://127.0.0.1:8000/ et se connecter avec un des comptes de démonstration
(mot de passe **Pharma2026!**) :

| Identifiant | Rôle |
|---|---|
| `admin` | Administrateur (accès à tout, y compris /admin/) |
| `pharmacien` | Pharmacien responsable |
| `stock` | Gestionnaire de stock |
| `caisse` | Caissier |
| `gestion` | Responsable de gestion |

Sans données de démonstration : `python manage.py init_pharmagest` crée les cinq rôles, puis
`python manage.py createsuperuser` crée le premier administrateur.

Photos : les 12 médicaments de démonstration ont une vraie photo (`medicaments/photos_demo/`).
Sur une base existante, `python manage.py photos_demo` les installe. Tout médicament ajouté sans photo
reçoit une illustration de son conditionnement ; `python manage.py generer_photos` en crée pour ceux
qui n'en ont pas. Une vraie photo se téléverse depuis « Modifier » (JPG ou PNG, 2 Mo maximum).

L'application fonctionne **sans connexion Internet** : Bootstrap, Chart.js et la police IBM Plex Sans
sont fournis dans `static/vendor/`.

## Documentation

- [Manuel d'installation et de configuration](docs/INSTALLATION.md)
- [Guide d'utilisation](docs/GUIDE_UTILISATION.md)
- Dossier de conception (MCD, MLD, UML) : document « PharmaGest — Dossier de conception »

## Organisation du code

| Application | Contenu |
|---|---|
| `config/` | paramètres, URL principales |
| `utilisateurs/` | rôles et permissions, journal d'audit, paramètres de la pharmacie, commandes `init_pharmagest`, `donnees_demo`, `sauvegarder` |
| `medicaments/` | catégories, médicaments, photos |
| `fournisseurs/`, `clients/` | partenaires |
| `stock/` | lots, mouvements, **services** (seul code qui modifie les quantités), inventaire |
| `achats/` | commandes, réceptions partielles |
| `ventes/` | caisse, paiements, validation atomique, annulations, retours |
| `rapports/` | tableau de bord, PDF ReportLab |

## Règles de gestion et tests

```bash
python manage.py test
```

48 tests automatisés couvrent les scénarios de validation du cahier des charges (section 9) et les règles
RG01 à RG12 : réception de 20 unités comptée une seule fois, vente de 3 unités, vente supérieure au stock
refusée, lot périmé refusé, accès sans permission interdit, reçu PDF, double validation, restauration
d'une sauvegarde, prix historiques conservés, FEFO, retours et annulations compensatoires.
