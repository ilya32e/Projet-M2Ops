from datetime import datetime, timedelta
from pathlib import Path

from airflow.operators.python import PythonOperator

from airflow import DAG


def run_collection() -> dict[str, int]:
    from gazette.collector import collect_once

    return collect_once(
        sources_file=Path("/opt/gazette/sources.csv"),
        db_path=Path("/opt/gazette/data/gazette.sqlite3"),
        raw_dir=Path("/opt/gazette/articles_bruts"),
    )


with DAG(
    dag_id="gazette_collecte",
    description="Collecte RSS/Atom de La Gazette",
    schedule=timedelta(minutes=30),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "gazette",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["gazette", "rss", "collecte"],
) as dag:
    collect = PythonOperator(
        task_id="collecte_multi_sources",
        python_callable=run_collection,
    )
