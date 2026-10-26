# Plateforme e-commerce de coques de téléphone

Projet réalisé dans le cadre du cours de **Bases de données NoSQL / Architecture Microservices** avec M. Charroux.

## 📝 Présentation du projet
Ce projet consiste en la conception et le découpage en microservices d'une plateforme e-commerce spécialisée dans la vente de coques et d'accessoires pour smartphones.

Le système permet aux clients de :
* Consulter un catalogue de coques personnalisées selon le modèle et la couleur du téléphone.
* Gérer un panier et passer des commandes de manière autonome.
* Suivre la livraison de leurs colis en temps réel.
* Interagir avec le service après-vente (SAV) pour créer des réclamations ou effectuer des retours.
* Recevoir des recommandations de coques personnalisées adaptées à leur modèle de téléphone.
  
 ## Architecture des microservices

L'application est découpée en plusieurs microservices indépendants. Chaque service possède ses propres données et assure une responsabilité métier spécifique.

## 1. Service Produit

Responsabilité : gérer le catalogue des produits disponibles sur la plateforme.

Ce service permet de :

* Ajouter, modifier et supprimer des produits.

* Consulter les informations des produits : nom, prix et stock disponible.

* Gérer les quantités disponibles en stock.

* Publier des événements lorsqu'un prix ou un stock change.

* Données possédées : produits (nom, prix, stock).

## 2. Service Commandes

Responsabilité : gérer le processus de commande, depuis la création jusqu'au suivi de son statut.

Ce service permet de :

* Créer une commande à partir des produits sélectionnés par le client.

* Gérer les lignes de commande et les quantités demandées.

* Calculer le montant total de la commande.

* Suivre l'évolution du statut de la commande.

* Utiliser une copie locale des informations nécessaires sur les produits afin de limiter les dépendances directes au service Produit.

Données possédées : commandes (lignes, statut, total).

Données répliquées : informations utiles sur les produits (nom, prix, stock).

## 3. Service Après-vente (SAV)

Responsabilité : gérer les demandes d'assistance des clients après une commande.

Ce service permet de :

* Créer et suivre des tickets de réclamation.

* Gérer les demandes de retour et les problèmes liés aux commandes.

* Conserver les messages échangés dans le cadre d'un ticket.

* Vérifier les informations nécessaires sur une commande pour déterminer si une demande peut être traitée.

* Utiliser une copie locale des informations de commande pour réduire la dépendance directe au service Commandes.

Données possédées : tickets (motif, statut, messages).

Données répliquées : informations utiles sur les commandes (lignes, statut).
