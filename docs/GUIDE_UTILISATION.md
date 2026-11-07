# Guide d'utilisation

Le menu de gauche n'affiche que les fonctions autorisées pour votre rôle.

## Approvisionner la pharmacie

1. **Fournisseurs → Ajouter un fournisseur** (une seule fois par fournisseur).
2. **Commandes d'achat → Nouvelle commande** : choisir le fournisseur, ajouter les médicaments, les
   quantités et, si besoin, le prix d'achat (vide = prix de la fiche). La commande est en *brouillon*.
3. Le pharmacien **valide la commande**. Le stock ne change pas encore.
4. À la livraison, **Réceptionner** : saisir pour chaque produit la quantité réellement reçue, le
   numéro de lot et la date de péremption. Une livraison incomplète est acceptée : la commande passe
   en « partiellement réceptionnée ».
5. Vérifier puis **Valider : faire entrer en stock**. C'est à ce moment, et une seule fois, que le stock
   augmente. Le bon de réception PDF est disponible sur la même page.

## Vendre à la caisse

1. **Ouvrir la caisse**.
2. Scanner le code-barres (ou le taper) et indiquer la quantité, ou **rechercher par nom**.
   Le système choisit les lots automatiquement, en commençant par la péremption la plus proche (FEFO).
   Les lots périmés ou bloqués ne sont jamais proposés.
3. Facultatif : choisir le client. Sans client, c'est une vente comptoir.
4. **Encaisser** : espèces (confirmé immédiatement) ou mobile money. Pour le mobile money, saisir la
   référence de la transaction, vérifier sur le téléphone que le paiement est bien reçu, puis **Confirmer**.
5. **Valider la vente** dès que le total est payé. La monnaie à rendre s'affiche ; imprimer le reçu.

Une vente commencée puis interrompue reste ouverte : **Ouvrir la caisse** la reprend.
**Abandonner la vente** vide le panier tant que rien n'a été encaissé.

## Retours et annulations

- **Retour** : sur la fiche de la vente, indiquer la quantité et le motif puis **Demander**.
  Le pharmacien valide ou refuse dans **Retours**, en cochant « Remettre en stock » seulement si le
  produit est intact et réintégrable. Le remboursement est calculé au prix payé par le client.
- **Annulation** (pharmacien) : sur la fiche de la vente, saisir le motif. La vente reste dans
  l'historique avec le statut « Annulée » et le stock est réintégré.

Une vente validée n'est jamais supprimée.

## Suivre le stock

- **État du stock** : quantités vendables, filtre « sous le seuil d'alerte » et « en rupture ».
- **Lots et péremptions** : lots proches de la péremption (barre ambre), périmés (barre rouge), bloqués.
- **Bloquer un lot** (rappel, contrôle qualité) depuis sa fiche : il n'est plus vendu.
- **Inventaire** : saisir les quantités comptées ; chaque écart crée une correction tracée.
- **Mouvements** : historique complet des entrées et sorties, avec leur auteur.

## Tableau de bord et rapports

Le tableau de bord affiche les indicateurs du jour et, selon votre rôle, les ventes et achats sur la
période choisie, les produits les plus vendus et les alertes. Le chiffre d'affaires, les encaissements et
la marge commerciale sont présentés séparément ; la marge n'est pas un bénéfice net.

**Rapports PDF** : rapport de stock, liste des péremptions, rapports des ventes et des achats sur une
période. Reçus, factures, bons de commande et de réception s'impriment depuis chaque fiche.

## Comptes

- **Changer mon mot de passe** : en bas du menu.
- **Mot de passe oublié** : lien sur la page de connexion.
- L'administrateur crée les comptes, attribue les rôles et désactive un compte (sans le supprimer)
  dans **Utilisateurs**. Toutes les opérations sensibles sont consultables dans **Journal d'audit**.
