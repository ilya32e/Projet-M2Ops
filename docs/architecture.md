# Schéma d'architecture - La Gazette

**Responsable du dépôt :** Iliasse Mouradi (`ilya32e`)

```mermaid
flowchart LR
    S[8 sources RSS\n4 PQR + 4 PQN] --> C[1. Collecte des flux\nConnecteurs HTTP/RSS]
    C -->|réponses brutes\n+ horodatage| B[2. Stockage brut\nJSON Lines / fichiers immuables]
    B -->|items candidats| Q[3. Nettoyage & contrôle qualité\nSchéma, dates, URL, doublons]
    Q -->|items valides| T[4. Regroupement par thèmes\nTaxonomie versionnée]
    T -->|titres + extraits courts\nliens + dates| E[5. Livraison de l'édition\nMarkdown + JSON, 07:00]
    C -. métriques .-> O[6. Supervision\nLogs, compteurs, alertes]
    Q -. erreurs .-> O
    T -. volumes .-> O
    E -. statut SLA .-> O

    subgraph Runtime[Exécution locale puis conteneurisée]
      C
      B
      Q
      T
      E
      O
    end
```

## Contrats de données

- **Entrée RSS** : `source`, `source_type`, `title`, `summary`, `published_at`, `url`.
- **Item normalisé** : mêmes champs, plus `canonical_url`, `fetched_at`, `content_hash`, `topic`, `quality_status`.
- **Édition** : `edition_date`, `generated_at`, puis une liste de thèmes et d'items contenant seulement `source`, `title`, `excerpt`, `published_at`, `url`.

Le texte intégral ne traverse pas le pipeline et n'est pas stocké. Les flux bruts sont conservés pour permettre un audit et un rejeu, avec une durée de rétention à fixer avant la mise en production.

## Déclenchement et erreurs

Un déclenchement planifié démarre la collecte avant 7 h. Chaque source est isolée : un échec de connexion est journalisé et ne bloque pas les autres sources. L'édition est publiée avec un statut dégradé si le seuil minimal de sources valides est atteint ; sinon, la livraison échoue et une alerte est émise.
