"""Nettoyage : items bruts -> articles_propres ou rejets, puis rapport de qualité du jour."""

import argparse
import json
import logging
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .normalisation import borner_extrait, date_utc, mots_titre, nettoyer_texte
from .regles import FENETRE_DOUBLONS, Article, evaluer
from .storage import apply_migrations, connect

LOG = logging.getLogger("gazette.nettoyage")


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def _articles_gardes_recents(database: sqlite3.Connection, maintenant: datetime) -> list[Article]:
    limite = (maintenant - FENETRE_DOUBLONS).isoformat()
    lignes = database.execute(
        "SELECT id, source, titre, extrait, publie_le, rubrique FROM articles_propres"
        " WHERE publie_le >= ?",
        (limite,),
    )
    return [
        Article(id_, source, titre, extrait, publie_le, rubrique or "", mots_titre(titre))
        for id_, source, titre, extrait, publie_le, rubrique in lignes
    ]


def _items_a_traiter(database: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        database.execute(
            """SELECT a.id, a.source, a.lien, a.fichier, s.type AS type_source
               FROM articles a JOIN sources s ON s.nom = a.source
               WHERE a.id NOT IN (SELECT id FROM articles_propres)
                 AND a.id NOT IN (SELECT id FROM rejets)"""
        )
    )


def normaliser(brut: dict, item_id: str) -> Article:
    titre = nettoyer_texte(brut.get("titre", ""))
    extrait = borner_extrait(nettoyer_texte(brut.get("resume", "")))
    return Article(
        id=item_id,
        source=brut.get("source", ""),
        titre=titre,
        extrait=extrait,
        publie_le=date_utc(brut.get("publie_le", "")),
        rubrique=nettoyer_texte(brut.get("rubrique", "")),
        mots=mots_titre(titre),
    )


def nettoyer(
    db_path: Path,
    raw_dir: Path,
    migrations_dir: Path = Path("migrations"),
    maintenant: datetime | None = None,
) -> dict:
    """Traite les items bruts pas encore traités. Idempotent : un item n'est traité qu'une fois."""
    maintenant = maintenant or _maintenant()
    passage = maintenant.isoformat()
    database = connect(db_path)
    database.row_factory = sqlite3.Row
    apply_migrations(database, migrations_dir)

    items = []
    for ligne in _items_a_traiter(database):
        chemin = raw_dir / ligne["fichier"]
        try:
            brut = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as erreur:
            LOG.warning(json.dumps({"item": ligne["id"], "erreur": str(erreur)}))
            continue
        items.append((ligne, normaliser(brut, ligne["id"])))
    # Les plus anciens d'abord : c'est la première publication d'une dépêche qui est gardée.
    items.sort(key=lambda paire: paire[1].publie_le or "")

    gardes = _articles_gardes_recents(database, maintenant)
    compteurs = {"entres": len(items), "gardes": 0, "rejetes": 0}
    par_regle: Counter = Counter()
    for ligne, article in items:
        rejet = evaluer(article, gardes, maintenant)
        if rejet:
            database.execute(
                """INSERT OR IGNORE INTO rejets
                   (id, source, lien, titre, regle, detail, fichier_brut, rejete_le, passage)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (article.id, article.source, ligne["lien"], article.titre, rejet.regle,
                 rejet.detail, ligne["fichier"], passage, passage),
            )
            compteurs["rejetes"] += 1
            par_regle[rejet.regle] += 1
        else:
            database.execute(
                """INSERT OR IGNORE INTO articles_propres
                   (id, source, type_source, lien, titre, extrait, publie_le, rubrique,
                    fichier_brut, nettoye_le, passage)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (article.id, article.source, ligne["type_source"], ligne["lien"], article.titre,
                 article.extrait, article.publie_le, article.rubrique, ligne["fichier"],
                 passage, passage),
            )
            compteurs["gardes"] += 1
            gardes.append(article)
    database.commit()
    database.close()
    LOG.info(json.dumps({"event": "nettoyage", **compteurs, "par_regle": dict(par_regle)}))
    return {**compteurs, "par_regle": dict(par_regle), "passage": passage}


def statistiques_du_jour(database: sqlite3.Connection, jour: str) -> dict:
    """Chiffres de la journée (UTC) : entrés, gardés, rejetés par règle et par source."""
    gardes = dict(
        database.execute(
            "SELECT source, COUNT(*) FROM articles_propres WHERE substr(nettoye_le,1,10)=?"
            " GROUP BY source",
            (jour,),
        ).fetchall()
    )
    rejets = database.execute(
        "SELECT source, regle, titre, detail FROM rejets WHERE substr(rejete_le,1,10)=?",
        (jour,),
    ).fetchall()
    par_regle = Counter(r[1] for r in rejets)
    rejets_source = Counter(r[0] for r in rejets)
    sources = sorted(set(gardes) | set(rejets_source))
    par_source = []
    for source in sources:
        entres = gardes.get(source, 0) + rejets_source.get(source, 0)
        par_source.append({
            "source": source,
            "entres": entres,
            "gardes": gardes.get(source, 0),
            "rejetes": rejets_source.get(source, 0),
            "taux_rejet": round(rejets_source.get(source, 0) / entres, 3) if entres else 0.0,
        })
    frequents = Counter((r[1], r[0]) for r in rejets).most_common(5)
    exemples = {}
    for source, regle, titre, detail in rejets:
        exemples.setdefault((regle, source), (titre, detail))
    total_gardes = sum(gardes.values())
    return {
        "jour": jour,
        "entres": total_gardes + len(rejets),
        "gardes": total_gardes,
        "rejetes": len(rejets),
        "par_regle": dict(par_regle.most_common()),
        "par_source": par_source,
        "rejets_frequents": [
            {"regle": regle, "source": source, "nombre": nombre,
             "exemple": exemples[(regle, source)][0], "detail": exemples[(regle, source)][1]}
            for (regle, source), nombre in frequents
        ],
    }


def rapport_markdown(stats: dict, controles: list[dict] | None = None) -> str:
    lignes = [
        f"# Rapport de qualité du {stats['jour']}",
        "",
        f"- Items entrés : **{stats['entres']}**",
        f"- Gardés : **{stats['gardes']}**",
        f"- Rejetés : **{stats['rejetes']}**",
        "",
        "## Rejets par règle",
        "",
        "| Règle | Rejets |",
        "|---|---:|",
    ]
    lignes += [f"| {regle} | {nombre} |" for regle, nombre in stats["par_regle"].items()]
    if not stats["par_regle"]:
        lignes.append("| (aucun) | 0 |")
    lignes += [
        "",
        "## Par source",
        "",
        "| Source | Entrés | Gardés | Rejetés | Taux de rejet |",
        "|---|---:|---:|---:|---:|",
    ]
    lignes += [
        f"| {s['source']} | {s['entres']} | {s['gardes']} | {s['rejetes']} |"
        f" {s['taux_rejet']:.0%} |"
        for s in stats["par_source"]
    ]
    lignes += [
        "",
        "## Les cinq rejets les plus fréquents",
        "",
        "| Règle | Source | Nombre | Exemple | Motif |",
        "|---|---|---:|---|---|",
    ]
    lignes += [
        f"| {r['regle']} | {r['source']} | {r['nombre']} | {r['exemple'][:80]} | {r['detail']} |"
        for r in stats["rejets_frequents"]
    ]
    if controles is not None:
        lignes += ["", "## Contrôles de qualité (dernier passage)", "",
                   "| Contrôle | Valeur | Seuil | Résultat |", "|---|---:|---|---|"]
        lignes += [
            f"| {c['controle']} | {c['valeur']:g} | {c['seuil']} |"
            f" {'OK' if c['ok'] else 'ÉCHEC : ' + c['detail']} |"
            for c in controles
        ]
    return "\n".join(lignes) + "\n"


def ecrire_rapport(
    db_path: Path, rapports_dir: Path, controles: list[dict] | None = None,
    maintenant: datetime | None = None,
) -> Path:
    """Écrit (ou réécrit) rapports/qualite-YYYY-MM-DD.md pour la journée en cours."""
    maintenant = maintenant or _maintenant()
    jour = maintenant.date().isoformat()
    database = sqlite3.connect(db_path)
    try:
        stats = statistiques_du_jour(database, jour)
    finally:
        database.close()
    rapports_dir.mkdir(parents=True, exist_ok=True)
    chemin = rapports_dir / f"qualite-{jour}.md"
    chemin.write_text(rapport_markdown(stats, controles), encoding="utf-8")
    (rapports_dir / f"qualite-{jour}.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return chemin


def main() -> int:
    parser = argparse.ArgumentParser(description="Nettoyage des items bruts de La Gazette")
    parser.add_argument("--db", type=Path, default=Path("data/gazette.sqlite3"))
    parser.add_argument("--raw-dir", type=Path, default=Path("articles_bruts"))
    parser.add_argument("--rapports", type=Path, default=Path("rapports"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    nettoyer(args.db, args.raw_dir)
    print(ecrire_rapport(args.db, args.rapports))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
