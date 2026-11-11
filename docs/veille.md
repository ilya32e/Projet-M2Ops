# Veille éclair - TD1

Six sujets, chacun traité en une demi-page : deux options, leurs limites, notre recommandation.
Ce qu'on écarte compte autant que ce qu'on garde ; les décisions sont reprises dans [cadrage.md](cadrage.md).

## 1. Récupérer ce que la presse publie

| Option | Avantages | Limites |
|---|---|---|
| **Flux RSS / Atom publics** | Format standard, prévu pour les machines, titre + extrait + lien + date déjà structurés, léger (ETag / Last-Modified) | Flux parfois supprimés ou bloqués (La Voix du Nord), extraits tronqués, conditions variables (Le Monde : usage personnel uniquement) |
| Scraping HTML des pages d'accueil | Couvre les sites sans flux | Fragile au moindre changement de gabarit, risque juridique (CGU, robots.txt), tentation de récupérer le texte intégral, paywalls |

**Pièges repérés** : flux morts ou redirigés, encodages et dates non normalisés (RFC 822 vs ISO 8601), doublons entre rubriques d'un même titre, conditions d'utilisation à lire flux par flux.

**Reco** : RSS/Atom uniquement, une adresse vérifiée à la main par source dans [sources.csv](../sources.csv), User-Agent identifiable, requêtes conditionnelles, connecteur désactivé (`actif=0`) si les conditions l'interdisent. Scraping écarté.

## 2. Faire tourner quelque chose tous les matins

| Option | Avantages | Limites |
|---|---|---|
| Cron / Planificateur de tâches Windows | Zéro dépendance, trivial à mettre en place | Pas d'historique des exécutions, pas de reprise, pas de vue d'ensemble, différent selon l'OS |
| **Orchestrateur (Apache Airflow)** | DAG versionné dans le dépôt, retries, historique et logs par tâche, interface web, standard du métier | Lourd (scheduler + webserver + base), courbe d'apprentissage |

Alternatives regardées : Prefect, Dagster (plus légers mais moins répandus) ; GitHub Actions planifié (gratuit mais pas fait pour stocker un état local).

**Reco** : script CLI simple (`bin/collect`) pour le développement, puis Airflow en Docker Compose pour l'exécution planifiée (`catchup=False`, `max_active_runs=1`). Collecte régulière dans la nuit, édition générée avant 7 h.

## 3. Où et sous quelle forme stocker

| Option | Avantages | Limites |
|---|---|---|
| **Fichiers JSON / JSONL pour le brut + SQLite pour l'index** | Aucun serveur, lisible, rejouable, versionnable en fixtures | Pas de concurrence d'écriture, peu adapté au multi-machines |
| PostgreSQL (ou stockage objet type S3 / MinIO) | Robuste, concurrent, requêtes riches, prêt pour la production | Service à opérer, sauvegardes, surdimensionné au départ |

**Reco** : deux couches séparées. **Brut** : un fichier JSON par item, immuable, clé naturelle `(source, lien)`, pour l'audit et le rejeu. **Propre** : SQLite pour l'état des sources et l'index dédoublonné. Migration vers PostgreSQL (déjà présent dans `docker-compose.yml`) lors de la mise en production. Dans les deux cas : titre, extrait, lien, date, jamais l'article entier.

## 4. Regrouper des textes par thèmes

| Option | Avantages | Limites |
|---|---|---|
| **Règles déterministes : taxonomie + mots-clés + rubrique du flux** | Explicable, testable, reproductible, aucun coût | Maintenance manuelle de la taxonomie, rate les sujets émergents |
| Clustering non supervisé (TF-IDF + k-means / HDBSCAN, ou embeddings) | Découvre les sujets du jour sans liste préétablie | Résultats instables d'un jour à l'autre, nommage des groupes difficile, plus dur à tester ; textes très courts (titre + extrait) |

Écarté : LLM pour résumer ou étiqueter (hors sujet du module, coût, non reproductible).

**Reco** : règles déterministes avec une taxonomie versionnée pour le premier incrément ; clustering TF-IDF en complément si le temps le permet, pour détecter les sujets non couverts.

## 5. Surveiller un pipeline

| Option | Avantages | Limites |
|---|---|---|
| **Logs structurés (JSON) + compteurs en base + alertes simples** | Léger, suffisant pour une exécution quotidienne, lisible dans Airflow | Pas de tableau de bord, historique limité |
| Stack Prometheus + Grafana (+ Loki pour les logs) | Métriques dans le temps, tableaux de bord, alerting riche | Trois services de plus à opérer, configuration conséquente |

**Ce qu'on mesure** : nombre d'items par source et par run, échecs consécutifs, durée de collecte, fraîcheur du dernier succès, heure de sortie de l'édition par rapport au SLA de 7 h.

**Reco** : logs structurés, état par source en base (`derniere_reussite`, `echecs_consecutifs`, mise en sommeil avec backoff) et historique Airflow d'abord ; Prometheus/Grafana lorsque l'infrastructure de production sera fournie.

## 6. Décrire une infrastructure en code

| Option | Avantages | Limites |
|---|---|---|
| **Docker + Docker Compose** | Environnement identique sur chaque poste, un fichier versionné, démarrage en une commande | Une seule machine, ne provisionne pas de serveurs |
| Terraform (+ Ansible pour la configuration) | Provisionne et configure des machines distantes de façon déclarative et reproductible | Nécessite un fournisseur cible et des accès, inutile tant qu'on reste en local |

Écarté pour l'instant : Kubernetes, surdimensionné pour un traitement quotidien.

**Reco** : Docker Compose dès le TD2 (application, PostgreSQL, Airflow), CI GitHub Actions pour lint, tests et build d'image. Terraform / Ansible dans `infra/` quand l'infrastructure de production sera fournie (TD4 ou TD6).
