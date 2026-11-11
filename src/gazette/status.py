import argparse
import sqlite3
from pathlib import Path


def source_states(db_path: Path) -> list[dict[str, object]]:
    database = sqlite3.connect(db_path)
    database.row_factory = sqlite3.Row
    try:
        rows = database.execute(
            """SELECT s.nom, s.type, s.actif, s.derniere_reussite, s.echecs_consecutifs,
                      s.derniere_erreur, s.sommeil_jusqu_a,
                      (SELECT COUNT(*) FROM articles a WHERE a.source = s.nom) AS articles
               FROM sources s ORDER BY s.type, s.nom"""
        ).fetchall()
    finally:
        database.close()
    states = []
    for row in rows:
        if row["actif"]:
            state = "active"
        elif row["sommeil_jusqu_a"]:
            state = "en sommeil"
        else:
            state = "desactivee"
        states.append({**dict(row), "etat": state})
    return states


def render(states: list[dict[str, object]]) -> str:
    header = (
        f"{'Source':<22} {'Type':<4} {'Etat':<11} {'Echecs':>6} {'Articles':>8}"
        "  Derniere reussite"
    )
    lines = [header, "-" * len(header)]
    for state in states:
        success = str(state["derniere_reussite"] or "jamais")[:19]
        lines.append(
            f"{str(state['nom'])[:22]:<22} {state['type']:<4} {state['etat']:<11} "
            f"{state['echecs_consecutifs']:>6} {state['articles']:>8}  {success}"
        )
        if state["etat"] == "en sommeil":
            lines.append(
                f"  -> reessai apres {state['sommeil_jusqu_a']} ;"
                f" erreur : {state['derniere_erreur']}"
            )
    sleeping = sum(state["etat"] == "en sommeil" for state in states)
    lines.append("")
    lines.append(f"{len(states)} source(s), {sleeping} en sommeil")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Etat des sources de La Gazette")
    parser.add_argument("--db", type=Path, default=Path("data/gazette.sqlite3"))
    args = parser.parse_args()
    if not args.db.exists():
        print(f"Aucune base de collecte trouvee : {args.db}")
        return 1
    states = source_states(args.db)
    print(render(states))
    return 2 if any(state["etat"] == "en sommeil" for state in states) else 0


if __name__ == "__main__":
    raise SystemExit(main())
