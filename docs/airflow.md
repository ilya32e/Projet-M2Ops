# Orchestration Airflow

Le DAG [`airflow/dags/gazette_collect.py`](../airflow/dags/gazette_collect.py) lance `collect_once` toutes les 30 minutes. Le service `app` du profil local est désactivé dans ce mode afin d'éviter une double collecte.

Pour démarrer l'orchestrateur en local :

```powershell
docker compose --profile airflow up --build
```

Puis ouvrir <http://localhost:8080> avec `admin` / `admin`. Le DAG est configuré avec `catchup=False` et `max_active_runs=1` : une exécution manquée n'est pas rejouée automatiquement et deux collectes ne se chevauchent pas.

Les volumes partagés conservent la base SQLite dans `data/` et les items bruts dans `articles_bruts/`. Les identifiants fournis sont uniquement destinés au développement local et doivent être remplacés avant toute mise en production.
