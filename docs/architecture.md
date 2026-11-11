# Schéma d'architecture - La Gazette

## Vue d'ensemble

```mermaid
flowchart LR
    A[Collecte des flux RSS<br/>connecteurs Python] -->|flux XML et métadonnées| B[Stockage brut<br/>JSONL + articles_bruts/]
    B -->|items bruts| C[Nettoyage et contrôle qualité<br/>validation, fraîcheur, doublons]
    C -->|items normalisés| D[Regroupement par thèmes<br/>taxonomie versionnée]
    D -->|items classés| E[Livraison de l'édition<br/>Markdown/JSON à 7 h]
    F[Supervision<br/>logs, métriques, alertes] -. observe .-> A
    F -. observe .-> B
    F -. observe .-> C
    F -. observe .-> D
    F -. observe .-> E

    G[Ordonnanceur<br/>Airflow / tâche planifiée] --> A
    H[Exécution locale ou conteneurisée<br/>Docker Compose] -. héberge .-> A
    H -. héberge .-> B
    H -. héberge .-> C
    H -. héberge .-> D
    H -. héberge .-> E
    H -. héberge .-> F
```

Le déclenchement planifié lance la collecte avant 7 h. Les données circulent sous
forme de flux RSS puis d'items normalisés ; seules les métadonnées autorisées
(titre, extrait, lien, date et source) sont transmises à l'édition.

## Contrats de données

- **Entrée RSS** : `source`, `source_type`, `title`, `summary`, `published_at`, `url`.
- **Item normalisé** : mêmes champs, plus `canonical_url`, `fetched_at`, `content_hash`, `topic`, `quality_status`.
- **Édition** : `edition_date`, `generated_at`, puis une liste de thèmes et d'items contenant seulement `source`, `title`, `excerpt`, `published_at`, `url`.

Le texte intégral ne traverse pas le pipeline et n'est pas stocké. Les flux bruts sont conservés pour permettre un audit et un rejeu, avec une durée de rétention à fixer avant la mise en production.

## Déclenchement et erreurs

Un déclenchement planifié démarre la collecte avant 7 h. Chaque source est isolée : un échec de connexion est journalisé et ne bloque pas les autres sources. L'édition est publiée avec un statut dégradé si le seuil minimal de sources valides est atteint ; sinon, la livraison échoue et une alerte est émise.
