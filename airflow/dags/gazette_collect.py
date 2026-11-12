from datetime import datetime, timedelta
from pathlib import Path

from airflow.exceptions import AirflowException, AirflowSkipException
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


def run_regroupement() -> dict:
    from datetime import timezone

    from gazette.regroupement import charger_config, doit_tourner, executer_run
    from gazette.storage import connect

    config = charger_config(RACINE / "config" / "clustering.yaml")
    config["embeddings"]["dossier_cache"] = str(RACINE / "data" / "modeles")
    database = connect(DB)
    a_faire = doit_tourner(database, datetime.now(timezone.utc),
                           config["planification"]["heures_utc"])
    database.close()
    if not a_faire:
        raise AirflowSkipException("Pas de créneau de regroupement depuis le dernier run")
    return executer_run(DB, config, dossier_runs=RACINE / "data" / "runs",
                        migrations_dir=MIGRATIONS, declencheur="airflow")


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
    description="Collecte, nettoyage, contrôles de qualité et thèmes de La Gazette",
    schedule=timedelta(minutes=30),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "gazette",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["gazette", "rss", "collecte", "qualite", "themes"],
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
    regroupement = PythonOperator(
        task_id="regroupement_themes", python_callable=run_regroupement, retries=1
    )
    collecte >> nettoyage >> [controles, regroupement]
