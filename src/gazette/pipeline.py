"""Passage complet hors Airflow : collecte -> nettoyage -> contrôles -> rapport."""

import argparse
import logging
import time
from pathlib import Path

from .collector import collect_once
from .controles import controler
from .nettoyage import ecrire_rapport, nettoyer


def passage(
    sources_file: Path = Path("sources.csv"),
    db_path: Path = Path("data/gazette.sqlite3"),
    raw_dir: Path = Path("articles_bruts"),
    rapports_dir: Path = Path("rapports"),
    migrations_dir: Path = Path("migrations"),
) -> list[dict]:
    collect_once(sources_file, db_path, raw_dir, migrations_dir=migrations_dir)
    bilan = nettoyer(db_path, raw_dir, migrations_dir)
    resultats = controler(db_path, db_path.parent / "metriques.prom", nettoyage=bilan)
    ecrire_rapport(db_path, rapports_dir, resultats)
    return resultats


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline complet de La Gazette")
    parser.add_argument("--sources-file", type=Path, default=Path("sources.csv"))
    parser.add_argument("--db", type=Path, default=Path("data/gazette.sqlite3"))
    parser.add_argument("--raw-dir", type=Path, default=Path("articles_bruts"))
    parser.add_argument("--rapports", type=Path, default=Path("rapports"))
    parser.add_argument("--interval", type=int, default=0,
                        help="Intervalle en secondes ; 0 exécute un seul passage")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    while True:
        passage(args.sources_file, args.db, args.raw_dir, args.rapports)
        if args.interval <= 0:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
