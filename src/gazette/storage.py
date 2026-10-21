import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .models import NewsItem, Source


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(db_path)
    database.row_factory = sqlite3.Row
    return database


def apply_migrations(database: sqlite3.Connection, migrations_dir: Path) -> None:
    database.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)")
    for migration in sorted(migrations_dir.glob("*.sql")):
        version = migration.name.split("_", 1)[0]
        applied = database.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
        ).fetchone()
        if applied:
            continue
        database.executescript(migration.read_text(encoding="utf-8"))
        database.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
    database.commit()


def initialize(
    database: sqlite3.Connection, sources: Iterable[Source], migrations_dir: Path
) -> None:
    apply_migrations(database, migrations_dir)
    source_list = list(sources)
    for source in source_list:
        database.execute(
            """INSERT INTO sources(nom, type, url_flux, actif) VALUES (?, ?, ?, ?)
               ON CONFLICT(nom) DO UPDATE SET type=excluded.type, url_flux=excluded.url_flux""",
            (source.name, source.source_type, source.address, int(source.active)),
        )
        if not source.active:
            database.execute("UPDATE sources SET actif=0 WHERE nom=?", (source.name,))
    if source_list:
        placeholders = ",".join("?" for _ in source_list)
        database.execute(
            f"UPDATE sources SET actif=0 WHERE nom NOT IN ({placeholders})",
            tuple(source.name for source in source_list),
        )
    database.commit()


def active_sources(database: sqlite3.Connection) -> list[sqlite3.Row]:
    database.execute(
        """UPDATE sources SET actif=1, echecs_consecutifs=0, derniere_erreur=NULL,
           sommeil_jusqu_a=NULL
           WHERE actif=0 AND sommeil_jusqu_a IS NOT NULL AND sommeil_jusqu_a <= ?""",
        (utc_now(),),
    )
    database.commit()
    return list(database.execute("SELECT * FROM sources WHERE actif = 1 ORDER BY nom"))


def mark_success(
    database: sqlite3.Connection,
    name: str,
    etag: str | None,
    last_modified: str | None,
) -> None:
    database.execute(
        """UPDATE sources SET derniere_reussite=?, echecs_consecutifs=0, actif=1,
           etag=?, last_modified=?, derniere_erreur=NULL WHERE nom=?""",
        (utc_now(), etag, last_modified, name),
    )
    database.commit()


def mark_failure(database: sqlite3.Connection, name: str, error: str) -> int:
    database.execute(
        """UPDATE sources SET echecs_consecutifs=echecs_consecutifs+1,
           actif=CASE WHEN echecs_consecutifs + 1 >= 3 THEN 0 ELSE actif END,
           derniere_erreur=?, sommeil_jusqu_a=CASE
             WHEN echecs_consecutifs + 1 >= 3
             THEN ? ELSE sommeil_jusqu_a END WHERE nom=?""",
        (error[:1000], (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(), name),
    )
    database.commit()
    row = database.execute(
        "SELECT echecs_consecutifs FROM sources WHERE nom=?", (name,)
    ).fetchone()
    return int(row[0])


def store_item(database: sqlite3.Connection, raw_dir: Path, item: NewsItem) -> bool:
    recovered_at = utc_now()
    natural_key = f"{item.source}\n{item.url}".encode()
    item_id = hashlib.sha256(natural_key).hexdigest()
    file_name = item_id + ".json"
    inserted = database.execute(
        """INSERT OR IGNORE INTO articles(id, source, lien, fichier, recupere_le)
           VALUES (?, ?, ?, ?, ?)""",
        (item_id, item.source, item.url, file_name, recovered_at),
    ).rowcount
    if not inserted:
        return False
    raw_dir.mkdir(parents=True, exist_ok=True)
    document = {
        "id": item_id,
        "source": item.source,
        "lien": item.url,
        "titre": item.title,
        "resume": item.excerpt,
        "publie_le": item.published_at,
        "recupere_le": recovered_at,
        "rubrique": item.category,
        "payload": {
            "entry": item.payload,
            "feed_xml": item.raw_payload,
        },
    }
    (raw_dir / file_name).write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    database.commit()
    return True
