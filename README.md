# La Gazette

## Prérequis

- Python 3.10 ou plus récent ;
- Docker et Docker Compose pour l'environnement conteneurisé.

Le projet n'a pas de dépendance Python runtime externe : il utilise la bibliothèque standard pour garder le premier incrément facile à reproduire.

## Démarrage rapide (deux commandes)

```powershell
git clone https://github.com/ilya32e/Projet-M2Ops.git; cd Projet-M2Ops
docker compose --profile local up --build
```

Seul Docker est nécessaire. La collecte tourne toutes les 30 minutes ; les items arrivent dans `articles_bruts/` et l'état des sources dans `data/gazette.sqlite3`.

## Lancer sans Docker

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
bin\dev.ps1
```

Si Windows refuse d'exécuter le script (politique d'exécution), lancer `powershell -ExecutionPolicy Bypass -File bin\dev.ps1`.

La commande lit une seule source (`Ouest-France` par défaut, modifiable avec la variable `GAZETTE_SOURCE`). Une source marquée `actif=0` dans `sources.csv` est refusée. Elle produit `data/items.jsonl` et ne conserve que le titre, un extrait court, le lien, la date et les métadonnées de source.

Pour choisir une autre source :

```powershell
python -m gazette.cli --source "Ouest-France" --output data/items.jsonl
```

## Tester

```powershell
bin\test.ps1
```

Ou directement :

```powershell
python -m unittest discover -s tests -v
```

## Contribuer

`main` est protégée : chaque changement passe par une branche, une pull request, la CI verte et une approbation. Les conventions (nommage des branches, format des commits, qui fusionne) sont dans [CONTRIBUTING.md](CONTRIBUTING.md).

## Docker Compose

```powershell
docker compose --profile local up --build
```

Le service `app` exécute la collecte de toutes les sources actives ; `postgres` est déclaré pour la mise en production mais n'est pas encore utilisé : les données sont écrites dans `data/` et `articles_bruts/`, montés depuis le dépôt.

## Collecte du TD3

La collecte multi-sources se lance en continu toutes les 30 minutes :

```powershell
bin\collect.ps1
```

Elle utilise SQLite dans `data/gazette.sqlite3` et écrit les items bruts dans `articles_bruts/`.
Les sources en échec trois fois de suite sont automatiquement mises en sommeil (nouvel essai 6 h plus tard).
Pour voir l'état de chaque source (dernière réussite, échecs, sommeil, nombre d'articles) :

```powershell
bin\status.ps1
```

La commande renvoie le code 2 si au moins une source est en sommeil, ce qui permet de l'utiliser dans un script d'alerte. Les détails des champs sont décrits dans [`docs/donnees.md`](docs/donnees.md).

## Qualité des données (TD 4)

Après chaque collecte, le DAG nettoie les items (`articles_propres` / `rejets`), vérifie six contrôles de qualité et écrit le rapport du jour dans `rapports/qualite-AAAA-MM-JJ.md`. Une alerte part sur Discord quand un contrôle passe en échec : copier `.env.example` en `.env` et y mettre l'adresse du webhook. Détails dans [`docs/qualite.md`](docs/qualite.md).

## Orchestration Airflow

Airflow exécute le DAG `gazette_collecte` toutes les 30 minutes. Pour lancer le scheduler et l'interface :

```powershell
docker compose --profile airflow up --build
```

Les services redémarrent automatiquement avec Docker (`restart: unless-stopped`) : la collecte reprend seule après un redémarrage du PC, tant que Docker Desktop se lance au démarrage. Si le port 8080 est déjà pris, choisir un autre port avec la variable `AIRFLOW_PORT` (par exemple `$env:AIRFLOW_PORT=8081`).

L'interface est disponible sur `http://localhost:8080` avec `admin` / `admin`. Le DAG réutilise le collecteur Python et conserve la base SQLite ainsi que les fichiers JSON dans `data/` et `articles_bruts/`. Les détails sont dans [`docs/airflow.md`](docs/airflow.md).

## Structure

```text
src/gazette/       code applicatif
tests/fixtures/    flux RSS de test figé
docs/              cadrage et architecture
infra/             configuration complémentaire
bin/               commandes développeur
```

## Données et conformité

Les sources et leurs conditions sont décrites dans [`sources.csv`](sources.csv). Le parseur ne télécharge que les flux déclarés et n'enregistre jamais le texte intégral d'un article. Les limites de débit, les CGU et `robots.txt` doivent être vérifiés avant toute mise en production.

Certaines sources du registre, notamment `Le Monde`, indiquent un usage RSS limité au cadre personnel et non collectif. Elles restent présentes pour le cadrage, mais ne doivent pas être activées pour une édition diffusée sans autorisation de l'éditeur.
