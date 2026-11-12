from datetime import datetime, timedelta
from pathlib import Path

from airflow.exceptions import AirflowException
from airflow.operators.python import PythonOperator

from airflow import DAG

RACINE = Path("/opt/gazette")
DB = RACINE / "data" / "gazette.sqlite3"
BRUTS = RACINE / "articles_bruts"
MIGRATIONS = RACINE / "migrations"


def run_collection() -> dict[str, int]:
    from gazette.collector import collect_once

    return collect_once(
        sources_file=RACINE / "sources.csv",
        db_path=DB,
        raw_dir=BRUTS,
        migrations_dir=MIGRATIONS,
    )


def run_nettoyage() -> dict:
    from gazette.nettoyage import nettoyer

    return nettoyer(DB, BRUTS, MIGRATIONS)


def run_controles(ti) -> list[dict]:
    from gazette.controles import controler
    from gazette.nettoyage import ecrire_rapport

    bilan = ti.xcom_pull(task_ids="nettoyage")
    resultats = controler(DB, RACINE / "data" / "metriques.prom", nettoyage=bilan)
    ecrire_rapport(DB, RACINE / "rapports", resultats)
    echecs = [r["controle"] for r in resultats if not r["ok"]]
    if echecs:
        # Tâche en rouge dans Airflow ; l'alerte Discord est déjà partie.
        raise AirflowException("Contrôles en échec : " + ", ".join(echecs))
    return resultats


with DAG(
    dag_id="gazette_collecte",
    description="Collecte RSS/Atom, nettoyage et contrôles de qualité de La Gazette",
    schedule=timedelta(minutes=30),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "gazette",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["gazette", "rss", "collecte", "qualite"],
) as dag:
    collecte = PythonOperator(task_id="collecte_multi_sources", python_callable=run_collection)
    nettoyage = PythonOperator(
        task_id="nettoyage", python_callable=run_nettoyage, trigger_rule="all_done"
    )
    controles = PythonOperator(
        task_id="controles_qualite",
        python_callable=run_controles,
        retries=0,
        trigger_rule="all_done",  # on contrôle même si la collecte a échoué
    )
    collecte >> nettoyage >> controles
