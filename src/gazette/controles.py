"""Contrôles de qualité sur les données réelles, après chaque passage.

Ce ne sont pas des tests de code : ce sont des faits vérifiés sur la base
(« aucune date future », « aucun titre vide »...). Chaque contrôle produit une
mesure, enregistrée dans `mesures_qualite` et exportée au format Prometheus
(data/metriques.prom) pour le TD 8. Quand un fait devient faux, une alerte part
vers le webhook Discord de l'équipe (variable GAZETTE_ALERT_WEBHOOK) ; une
seconde alerte annonce le retour à la normale. Pas d'alerte répétée entre-temps.
"""

import argparse
import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from .normalisation import EXTRAIT_MAX

LOG = logging.getLogger("gazette.controles")

TAUX_REJET_MAX = 0.8
MIN_ITEMS_POUR_TAUX = 10
FRAICHEUR_MAX = timedelta(hours=2)


def _controle(nom: str, valeur: float, seuil: str, ok: bool, detail: str = "") -> dict:
    return {"controle": nom, "valeur": float(valeur), "seuil": seuil, "ok": bool(ok),
            "detail": detail}


def verifier(database: sqlite3.Connection, maintenant: datetime) -> list[dict]:
    """Calcule chaque contrôle sur les données réelles."""
    resultats = []
    limite_futur = (maintenant + timedelta(minutes=15)).isoformat()

    futures = database.execute(
        "SELECT COUNT(*) FROM articles_propres WHERE publie_le > ?", (limite_futur,)
    ).fetchone()[0]
    resultats.append(_controle("C01_aucune_date_future", futures, "= 0", futures == 0,
                               f"{futures} article(s) daté(s) dans le futur"))

    vides = database.execute(
        "SELECT COUNT(*) FROM articles_propres WHERE trim(titre) = '' OR trim(lien) = ''"
    ).fetchone()[0]
    resultats.append(_controle("C02_aucun_titre_vide", vides, "= 0", vides == 0,
                               f"{vides} article(s) sans titre ou sans lien"))

    trop_longs = database.execute(
        "SELECT COUNT(*) FROM articles_propres WHERE length(extrait) > ?", (EXTRAIT_MAX,)
    ).fetchone()[0]
    resultats.append(_controle("C03_extrait_court", trop_longs, f"= 0 (> {EXTRAIT_MAX} car.)",
                               trop_longs == 0, f"{trop_longs} extrait(s) trop long(s)"))

    jour = maintenant.date().isoformat()
    lignes = database.execute(
        """SELECT source, SUM(rejete), COUNT(*) FROM (
             SELECT source, 0 AS rejete FROM articles_propres WHERE substr(nettoye_le,1,10)=?
             UNION ALL
             SELECT source, 1 FROM rejets WHERE substr(rejete_le,1,10)=?)
           GROUP BY source""",
        (jour, jour),
    ).fetchall()
    pire, pire_taux = "", 0.0
    for source, rejetes, total in lignes:
        if total >= MIN_ITEMS_POUR_TAUX and rejetes / total > pire_taux:
            pire, pire_taux = source, rejetes / total
    resultats.append(_controle("C04_taux_rejet_max", round(pire_taux, 3),
                               f"<= {TAUX_REJET_MAX:.0%} par source",
                               pire_taux <= TAUX_REJET_MAX,
                               f"{pire} rejette {pire_taux:.0%} de ses items"))

    limite = (maintenant - FRAICHEUR_MAX).isoformat()
    perimees = [
        nom for (nom,) in database.execute(
            "SELECT nom FROM sources WHERE actif = 1"
            " AND (derniere_reussite IS NULL OR derniere_reussite < ?)",
            (limite,),
        )
    ]
    resultats.append(_controle("C05_fraicheur_collecte", len(perimees), "= 0 source > 2 h",
                               not perimees, "sans collecte récente : " + ", ".join(perimees)))

    sommeil = [
        nom for (nom,) in database.execute(
            "SELECT nom FROM sources WHERE actif = 0 AND sommeil_jusqu_a IS NOT NULL"
        )
    ]
    resultats.append(_controle("C06_aucune_source_en_sommeil", len(sommeil), "= 0",
                               not sommeil, "en sommeil : " + ", ".join(sommeil)))
    return resultats


def enregistrer(database: sqlite3.Connection, passage: str, resultats: list[dict]) -> None:
    database.executemany(
        """INSERT OR REPLACE INTO mesures_qualite(passage, controle, valeur, seuil, ok, detail)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [(passage, r["controle"], r["valeur"], r["seuil"], int(r["ok"]), r["detail"])
         for r in resultats],
    )
    database.commit()


def exporter_prometheus(chemin: Path, resultats: list[dict], nettoyage: dict | None) -> None:
    """Écrit les métriques au format texte Prometheus (lu par node_exporter au TD 8)."""
    lignes = [
        "# HELP gazette_controle_ok 1 si le contrôle de qualité est vérifié, 0 sinon",
        "# TYPE gazette_controle_ok gauge",
    ]
    lignes += [f'gazette_controle_ok{{controle="{r["controle"]}"}} {int(r["ok"])}'
               for r in resultats]
    lignes += ["# HELP gazette_controle_valeur Valeur mesurée par le contrôle",
               "# TYPE gazette_controle_valeur gauge"]
    lignes += [f'gazette_controle_valeur{{controle="{r["controle"]}"}} {r["valeur"]:g}'
               for r in resultats]
    if nettoyage:
        lignes += ["# HELP gazette_nettoyage_items Items traités au dernier passage",
                   "# TYPE gazette_nettoyage_items gauge"]
        for cle in ("entres", "gardes", "rejetes"):
            lignes.append(f'gazette_nettoyage_items{{statut="{cle}"}} {nettoyage.get(cle, 0)}')
        for regle, nombre in nettoyage.get("par_regle", {}).items():
            lignes.append(f'gazette_rejets_par_regle{{regle="{regle}"}} {nombre}')
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")


def envoyer_alerte(webhook: str, message: str) -> None:
    corps = json.dumps({"username": "La Gazette", "content": message[:1900]}).encode()
    requete = Request(webhook, data=corps, method="POST", headers={
        "Content-Type": "application/json",
        "User-Agent": "LaGazette/0.1 (alertes qualite)",
    })
    with urlopen(requete, timeout=10) as reponse:
        reponse.read()


def alertes_a_envoyer(database: sqlite3.Connection, passage: str,
                      resultats: list[dict]) -> list[str]:
    """Compare à l'état précédent.

    Une alerte à l'apparition d'un échec, une autre au retour à la normale.
    """
    etat = dict(database.execute("SELECT controle, en_echec_depuis FROM alertes"))
    messages = []
    for r in resultats:
        depuis = etat.get(r["controle"])
        if not r["ok"] and not depuis:
            messages.append(f"🔴 **{r['controle']}** en échec : {r['detail']} (seuil {r['seuil']})")
            database.execute(
                "INSERT OR REPLACE INTO alertes VALUES (?, ?)", (r["controle"], passage)
            )
        elif r["ok"] and depuis:
            messages.append(f"🟢 **{r['controle']}** de nouveau OK (en échec depuis {depuis[:16]})")
            database.execute("DELETE FROM alertes WHERE controle = ?", (r["controle"],))
    database.commit()
    return messages


def controler(
    db_path: Path,
    metriques: Path = Path("data/metriques.prom"),
    nettoyage: dict | None = None,
    webhook: str | None = None,
    maintenant: datetime | None = None,
    envoyer=envoyer_alerte,
) -> list[dict]:
    maintenant = maintenant or datetime.now(timezone.utc)
    webhook = webhook if webhook is not None else os.getenv("GAZETTE_ALERT_WEBHOOK", "")
    passage = maintenant.isoformat()
    database = sqlite3.connect(db_path)
    try:
        resultats = verifier(database, maintenant)
        enregistrer(database, passage, resultats)
        messages = alertes_a_envoyer(database, passage, resultats)
    finally:
        database.close()
    exporter_prometheus(metriques, resultats, nettoyage)
    for r in resultats:
        LOG.log(logging.INFO if r["ok"] else logging.ERROR, json.dumps(r, ensure_ascii=False))
    if messages:
        texte = "**La Gazette : contrôle de qualité**\n" + "\n".join(messages)
        if webhook:
            try:
                envoyer(webhook, texte)
            except OSError as erreur:
                LOG.error(json.dumps({"event": "alerte_non_envoyee", "erreur": str(erreur)}))
        else:
            LOG.warning("Aucun webhook configuré (GAZETTE_ALERT_WEBHOOK) : %s", texte)
    return resultats


def main() -> int:
    parser = argparse.ArgumentParser(description="Contrôles de qualité de La Gazette")
    parser.add_argument("--db", type=Path, default=Path("data/gazette.sqlite3"))
    parser.add_argument("--metriques", type=Path, default=Path("data/metriques.prom"))
    parser.add_argument("--tester-alerte", action="store_true",
                        help="Envoie un message de test sur le webhook et s'arrête")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.tester_alerte:
        envoyer_alerte(os.environ["GAZETTE_ALERT_WEBHOOK"],
                       "🔔 La Gazette : test du canal d'alerte qualité.")
        return 0
    resultats = controler(args.db, args.metriques)
    return 0 if all(r["ok"] for r in resultats) else 2


if __name__ == "__main__":
    raise SystemExit(main())
