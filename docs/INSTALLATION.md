# Manuel d'installation et de configuration

## 1. Prérequis

- Python 3.12 ou plus récent (testé avec Python 3.12 et Django 6.1).
- Aucune connexion Internet n'est nécessaire après l'installation des paquets.

## 2. Installation en développement

```bash
cd PharmaGest
python -m venv venv
source venv/bin/activate          # Windows : venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate          # crée db.sqlite3
python manage.py init_pharmagest  # crée les 5 rôles et leurs permissions
python manage.py createsuperuser  # premier administrateur
python manage.py runserver
```

Pour tester avec des données réalistes, remplacer les deux commandes précédant `runserver` par
`python manage.py donnees_demo` (sur une base vide).

> **macOS** : si le projet est dans le dossier Téléchargements et que le Terminal affiche
> « Operation not permitted », déplacez le dossier dans votre dossier personnel ou autorisez le
> Terminal dans Réglages Système → Confidentialité et sécurité → Fichiers et dossiers.

## 3. Paramètres de la pharmacie

Menu **Paramètres** (administrateur) : nom, adresse, téléphone, NIF, STAT, mention de pied de page et
nombre de jours d'alerte avant péremption (90 par défaut). Ces informations apparaissent sur tous les PDF.

## 4. Variables d'environnement

| Variable | Rôle | Défaut (développement) |
|---|---|---|
| `PHARMAGEST_SECRET_KEY` | clé secrète Django | clé de développement — **à changer** |
| `PHARMAGEST_DEBUG` | `1` développement, `0` production | `1` |
| `PHARMAGEST_ALLOWED_HOSTS` | noms de domaine, séparés par des virgules | `127.0.0.1,localhost` |
| `PHARMAGEST_EMAIL_BACKEND` | envoi des e-mails de réinitialisation | affichage dans le terminal |

Voir `.env.example`. Avec `PHARMAGEST_DEBUG=0`, Django active automatiquement HTTPS obligatoire,
cookies sécurisés et HSTS.

## 5. Mise en production (résumé)

1. Base PostgreSQL : remplacer `DATABASES` dans `config/settings.py` (paquet `psycopg`).
2. `python manage.py collectstatic` puis servir `staticfiles/` et `media/` par Nginx ou Apache.
3. Lancer Django avec Gunicorn derrière Nginx, en HTTPS.
4. Définir les variables d'environnement ci-dessus, avec une clé secrète unique.
5. Planifier la sauvegarde quotidienne (section 6) et tester une restauration.

## 6. Sauvegarde et restauration

```bash
python manage.py sauvegarder
# → sauvegardes/pharmagest-AAAAMMJJ-HHMMSS.json.gz
```

Restauration sur une base vierge :

```bash
python manage.py migrate
python manage.py loaddata sauvegardes/pharmagest-AAAAMMJJ-HHMMSS.json.gz
```

Les photos sont dans `media/` : sauvegardez ce dossier en même temps que le fichier JSON.
Le test `test_restaurer_une_sauvegarde` vérifie ce cycle automatiquement.

Planification quotidienne (Linux, 22 h) : `0 22 * * * cd /chemin/PharmaGest && venv/bin/python manage.py sauvegarder`

## 7. Rôles et permissions

`python manage.py init_pharmagest` peut être relancée à tout moment : elle remet les cinq rôles à jour
selon `utilisateurs/roles.py`. Un utilisateur peut cumuler plusieurs rôles (menu **Utilisateurs**).
Chaque vue vérifie une permission précise, jamais le nom du rôle.
