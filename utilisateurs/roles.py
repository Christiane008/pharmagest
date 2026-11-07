"""Rôles du cahier des charges (section 3) traduits en groupes Django.

Chaque vue vérifie une permission, jamais le nom du groupe.
"""

ROLES = {
    "Administrateur": "__toutes__",
    "Pharmacien responsable": [
        "medicaments.view_categorie", "medicaments.add_categorie", "medicaments.change_categorie",
        "medicaments.delete_categorie",
        "medicaments.view_medicament", "medicaments.add_medicament", "medicaments.change_medicament",
        "medicaments.delete_medicament",
        "fournisseurs.view_fournisseur", "clients.view_client",
        "achats.view_commandeachat", "achats.valider_commande", "achats.view_receptionachat",
        "stock.view_lotstock", "stock.view_mouvementstock", "stock.corriger_stock", "stock.bloquer_lot",
        "ventes.view_vente", "ventes.add_vente", "ventes.valider_vente", "ventes.annuler_vente",
        "ventes.add_paiement",
        "ventes.view_retourvente", "ventes.valider_retour",
        "utilisateurs.voir_tableau_de_bord", "utilisateurs.voir_rapports",
    ],
    "Gestionnaire de stock": [
        "medicaments.view_categorie", "medicaments.view_medicament",
        "fournisseurs.view_fournisseur", "fournisseurs.add_fournisseur",
        "fournisseurs.change_fournisseur",
        "achats.view_commandeachat", "achats.add_commandeachat", "achats.change_commandeachat",
        "achats.view_receptionachat", "achats.add_receptionachat", "achats.valider_reception",
        "stock.view_lotstock", "stock.view_mouvementstock", "stock.corriger_stock",
        "utilisateurs.voir_tableau_de_bord", "utilisateurs.voir_rapports",
    ],
    "Caissier": [
        "medicaments.view_medicament",
        "clients.view_client", "clients.add_client", "clients.change_client",
        "ventes.view_vente", "ventes.add_vente", "ventes.valider_vente", "ventes.add_paiement",
        "ventes.view_retourvente", "ventes.add_retourvente",
        "utilisateurs.voir_tableau_de_bord",
    ],
    "Responsable de gestion": [
        "medicaments.view_categorie", "medicaments.view_medicament",
        "fournisseurs.view_fournisseur", "clients.view_client",
        "achats.view_commandeachat", "achats.view_receptionachat",
        "stock.view_lotstock", "stock.view_mouvementstock",
        "ventes.view_vente", "ventes.view_retourvente",
        "utilisateurs.voir_tableau_de_bord", "utilisateurs.voir_statistiques",
        "utilisateurs.voir_rapports", "utilisateurs.view_journalaudit",
    ],
}


def creer_groupes():
    from django.contrib.auth.models import Group, Permission

    for nom, perms in ROLES.items():
        groupe, _ = Group.objects.get_or_create(name=nom)
        if perms == "__toutes__":
            qs = Permission.objects.filter(
                content_type__app_label__in=[
                    "auth", "utilisateurs", "medicaments", "fournisseurs", "clients",
                    "stock", "achats", "ventes",
                ]
            )
        else:
            qs = Permission.objects.none()
            for p in perms:
                app, code = p.split(".")
                trouve = Permission.objects.filter(content_type__app_label=app, codename=code)
                if not trouve.exists():
                    raise ValueError(f"Permission inconnue : {p}")
                qs = qs | trouve
        groupe.permissions.set(qs)
    return list(ROLES)
