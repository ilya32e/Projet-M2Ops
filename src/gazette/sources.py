import csv
from pathlib import Path

from .models import Source


def load_sources(path: Path) -> list[Source]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = csv.DictReader(stream)
        required = {"nom", "type", "region", "adresse", "format"}
        missing = required - set(rows.fieldnames or [])
        if missing:
            raise ValueError(f"Colonnes manquantes dans sources.csv: {sorted(missing)}")
        return [
            Source(
                name=row["nom"].strip(),
                source_type=row["type"].strip(),
                region=row["region"].strip(),
                address=row["adresse"].strip(),
                format=row["format"].strip(),
            )
            for row in rows
            if row.get("nom", "").strip()
        ]


def find_source(path: Path, name: str) -> Source:
    for source in load_sources(path):
        if source.name.casefold() == name.casefold():
            return source
    available = ", ".join(source.name for source in load_sources(path))
    raise ValueError(f"Source inconnue: {name}. Disponibles: {available}")
