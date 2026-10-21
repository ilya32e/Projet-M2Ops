# La Gazette

## Prérequis

- Python 3.10 ou plus récent ;
- Docker et Docker Compose pour l'environnement conteneurisé.

Le projet n'a pas de dépendance Python runtime externe : il utilise la bibliothèque standard pour garder le premier incrément facile à reproduire.

## Lancer localement

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
bin\dev.ps1
```

La commande lit la source `Le Monde` dans `sources.csv`. Elle produit `data/items.jsonl` et ne conserve que le titre, un extrait court, le lien, la date et les métadonnées de source.

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

## Docker Compose

```powershell
docker compose up --build
```

Le service `app` exécute la collecte ; `postgres` est déjà déclaré pour le stockage indexé du TD3. Le premier incrément écrit les données dans le volume `gazette-data` et n'utilise pas encore PostgreSQL.

## Collecte du TD3

La collecte multi-sources se lance en continu toutes les 30 minutes :

```powershell
bin\collect.ps1
```

Elle utilise SQLite dans `data/gazette.sqlite3` et écrit les items bruts dans `articles_bruts/`.
Les sources en échec trois fois de suite sont automatiquement mises en sommeil. Les détails des champs sont décrits dans [`docs/donnees.md`](docs/donnees.md).

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
