"""Regroupement des articles des dernières 24 h en thèmes nommés, avec traçage du run.

Un run enregistre dans la table `runs` :
- les données : fenêtre (dates), nombre d'articles, hash de l'entrée ;
- le modèle d'embedding et sa version ;
- les paramètres (copie de config/clustering.yaml) et leur hash ;
- les métriques : nombre de thèmes, taille médiane, part de bruit, silhouette ;
- les artefacts : data/runs/<run_id>/themes.json et affectations.csv.
Les thèmes vont dans `themes`, les affectations dans `articles_themes`, toutes deux
reliées au run qui les a produites.
"""

import argparse
import csv
import hashlib
import json
import logging
import sqlite3
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import yaml
from sklearn.cluster import HDBSCAN
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import silhouette_score

from .embeddings import Encodeur, EncodeurFastEmbed, vectoriser
from .storage import apply_migrations, connect

LOG = logging.getLogger("gazette.regroupement")

MOTS_VIDES = set("""
a à au aux avec ce ces cet cette dans de des du elle en et eux il ils je la le les leur
leurs lui ma mais me même mes moi mon ne nos notre nous on ou où par pas pour qu que qui
sa se ses son sur ta te tes toi ton tu un une vos votre vous y été être avoir avait ont
est sont sera fait faire plus moins très tout tous toute toutes après avant depuis entre
selon sans sous chez contre vers comme si alors donc aussi encore déjà ainsi dont quand
comment pourquoi quoi cela ça celui celle ceux celles leur lors deux trois quatre cinq
an ans jour jours mois année années fois heure heures hier aujourd hui demain ce soir
matin mardi mercredi jeudi vendredi samedi dimanche lundi novembre octobre
nouveau nouvelle nouveaux premier première dernier dernière grand grande petit petite
selon va vont peut doit fait faut dit déclaré annoncé selon après photos vidéo vidéos
direct info infos actu actualité article lire aussi plus faut
l d c qu s n j m t
""".split())


def charger_config(chemin: Path) -> dict:
    return yaml.safe_load(chemin.read_text(encoding="utf-8"))


def _hash_json(objet) -> str:
    return hashlib.sha256(json.dumps(objet, sort_keys=True, ensure_ascii=False)
                          .encode("utf-8")).hexdigest()


def doit_tourner(database: sqlite3.Connection, maintenant: datetime,
                 heures_utc: list[int]) -> bool:
    """Vrai si aucun run terminé n'a eu lieu depuis le dernier créneau horaire passé."""
    creneaux = []
    for jours in (0, 1):
        for heure in heures_utc:
            creneau = (maintenant - timedelta(days=jours)).replace(
                hour=heure, minute=0, second=0, microsecond=0)
            if creneau <= maintenant:
                creneaux.append(creneau)
    if not creneaux:
        return True
    dernier_creneau = max(creneaux)
    deja = database.execute(
        "SELECT 1 FROM runs WHERE statut = 'termine' AND debut >= ? LIMIT 1",
        (dernier_creneau.isoformat(),),
    ).fetchone()
    return deja is None


def articles_fenetre(database: sqlite3.Connection, fin: datetime,
                     heures: int) -> list[tuple[str, str, str]]:
    debut = (fin - timedelta(hours=heures)).isoformat()
    return list(database.execute(
        """SELECT id, titre, extrait FROM articles_propres
           WHERE publie_le > ? AND publie_le <= ? ORDER BY id""",
        (debut, fin.isoformat()),
    ))


def hash_entree(articles: list[tuple[str, str, str]]) -> str:
    return _hash_json([list(article) for article in articles])


def regrouper(vecteurs: np.ndarray, parametres: dict) -> tuple[np.ndarray, np.ndarray]:
    """HDBSCAN sur des vecteurs normalisés (distance euclidienne ~ cosinus)."""
    if len(vecteurs) < parametres["min_cluster_size"]:
        return np.full(len(vecteurs), -1), np.zeros(len(vecteurs))
    modele = HDBSCAN(min_cluster_size=parametres["min_cluster_size"],
                     min_samples=parametres["min_samples"])
    etiquettes = modele.fit_predict(vecteurs)
    return etiquettes, modele.probabilities_


def _sans_accents(mot: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", mot)
                   if not unicodedata.combining(c))


def nommer(textes: list[str], etiquettes: np.ndarray,
           nb_mots_cles: int, nb_mots_nom: int) -> dict[int, dict]:
    """Mots les plus discriminants de chaque thème (TF-IDF calculé entre thèmes).

    Chaque thème devient un seul « document » (ses articles mis bout à bout) ; un mot
    fréquent dans un thème et rare dans les autres le décrit le mieux.
    """
    groupes = sorted(set(etiquettes) - {-1})
    if not groupes:
        return {}
    documents = [" ".join(textes[i] for i in np.where(etiquettes == g)[0]) for g in groupes]
    mots_vides = MOTS_VIDES | {_sans_accents(m) for m in MOTS_VIDES}
    compteur = CountVectorizer(
        lowercase=True,
        token_pattern=r"(?u)\b[^\W\d_][\w'-]{2,}\b",
        stop_words=sorted(mots_vides),
        ngram_range=(1, 2),
    )
    comptes = compteur.fit_transform(documents).toarray().astype(float)
    vocabulaire = compteur.get_feature_names_out()
    frequence = comptes / np.maximum(comptes.sum(axis=1, keepdims=True), 1)
    presence = (comptes > 0).sum(axis=0)
    idf = np.log(1 + len(groupes) / presence)
    scores = frequence * idf
    noms = {}
    for rang, groupe in enumerate(groupes):
        ordre = np.argsort(scores[rang])[::-1]
        mots: list[str] = []
        for indice in ordre:
            mot = vocabulaire[indice]
            # pas de mot déjà contenu dans un bigramme retenu, et inversement
            if any(mot in m or m in mot for m in mots):
                continue
            mots.append(mot)
            if len(mots) == nb_mots_cles:
                break
        noms[int(groupe)] = {"nom": " · ".join(mots[:nb_mots_nom]), "mots_cles": mots}
    return noms


def metriques(vecteurs: np.ndarray, etiquettes: np.ndarray) -> dict:
    classes = etiquettes >= 0
    tailles = [int((etiquettes == g).sum()) for g in sorted(set(etiquettes) - {-1})]
    silhouette = None
    if len(tailles) > 1:
        silhouette = round(float(silhouette_score(
            vecteurs[classes], etiquettes[classes], metric="cosine")), 4)
    return {
        "nb_articles": int(len(etiquettes)),
        "nb_themes": len(tailles),
        "taille_mediane": float(np.median(tailles)) if tailles else 0.0,
        "taille_max": max(tailles) if tailles else 0,
        "part_bruit": round(float(1 - classes.mean()), 4) if len(etiquettes) else 0.0,
        "silhouette": silhouette,
    }


def _ecrire_artefacts(dossier: Path, articles, etiquettes, probabilites, noms) -> dict:
    dossier.mkdir(parents=True, exist_ok=True)
    themes = [
        {"theme_id": g, **noms[g], "taille": int((etiquettes == g).sum()),
         "exemples": [articles[i][1] for i in np.where(etiquettes == g)[0][:5]]}
        for g in sorted(noms, key=lambda g: -int((etiquettes == g).sum()))
    ]
    (dossier / "themes.json").write_text(
        json.dumps(themes, ensure_ascii=False, indent=2), encoding="utf-8")
    with (dossier / "affectations.csv").open("w", encoding="utf-8", newline="") as flux:
        ecrivain = csv.writer(flux)
        ecrivain.writerow(["article_id", "theme_id", "probabilite", "titre"])
        for (article_id, titre, _), g, p in zip(articles, etiquettes, probabilites):
            ecrivain.writerow([article_id, int(g), round(float(p), 4), titre])
    # Chemins relatifs au dossier parent de runs/ (data/) : lisibles hors du conteneur.
    base = dossier.parent.parent
    return {nom: (dossier / fichier).relative_to(base).as_posix()
            for nom, fichier in (("themes", "themes.json"), ("affectations", "affectations.csv"))}


def executer_run(
    db_path: Path,
    config: dict,
    maintenant: datetime | None = None,
    encodeur: Encodeur | None = None,
    dossier_runs: Path = Path("data/runs"),
    migrations_dir: Path = Path("migrations"),
    declencheur: str = "manuel",
) -> dict:
    """Exécute un run complet et le trace. Renvoie le résumé du run."""
    maintenant = maintenant or datetime.now(timezone.utc)
    database = connect(db_path)
    apply_migrations(database, migrations_dir)
    run_id = maintenant.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    articles = articles_fenetre(database, maintenant, config["fenetre_heures"])
    parametres = {k: config[k] for k in ("fenetre_heures", "embeddings", "regroupement",
                                         "nommage")}
    encodeur = encodeur or EncodeurFastEmbed(config["embeddings"]["modele"],
                                             Path(config["embeddings"]["dossier_cache"]))
    database.execute(
        """INSERT INTO runs (run_id, debut, statut, declencheur, fenetre_debut, fenetre_fin,
           nb_articles, hash_entree, modele, version_modele, parametres, hash_parametres)
           VALUES (?, ?, 'en_cours', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (run_id, maintenant.isoformat(), declencheur,
         (maintenant - timedelta(hours=config["fenetre_heures"])).isoformat(),
         maintenant.isoformat(), len(articles), hash_entree(articles),
         encodeur.modele, encodeur.version,
         json.dumps(parametres, ensure_ascii=False), _hash_json(parametres)),
    )
    database.commit()
    try:
        vecteurs, calcules = vectoriser(database, articles, encodeur)
        etiquettes, probabilites = regrouper(vecteurs, config["regroupement"])
        textes = [f"{titre}. {extrait}" for _, titre, extrait in articles]
        noms = nommer(textes, etiquettes, config["nommage"]["nb_mots_cles"],
                      config["nommage"]["nb_mots_nom"])
        mesures = {**metriques(vecteurs, etiquettes), "vecteurs_calcules": calcules}
        artefacts = _ecrire_artefacts(dossier_runs / run_id, articles, etiquettes,
                                      probabilites, noms)
        database.executemany(
            "INSERT INTO themes (run_id, theme_id, nom, mots_cles, taille) VALUES (?,?,?,?,?)",
            [(run_id, g, n["nom"], json.dumps(n["mots_cles"], ensure_ascii=False),
              int((etiquettes == g).sum())) for g, n in noms.items()],
        )
        database.executemany(
            """INSERT INTO articles_themes (run_id, article_id, theme_id, probabilite)
               VALUES (?, ?, ?, ?)""",
            [(run_id, a[0], int(g), float(p))
             for a, g, p in zip(articles, etiquettes, probabilites)],
        )
        database.execute(
            "UPDATE runs SET statut='termine', fin=?, metriques=?, artefacts=? WHERE run_id=?",
            (datetime.now(timezone.utc).isoformat(), json.dumps(mesures),
             json.dumps(artefacts), run_id),
        )
        database.commit()
    except Exception as erreur:
        database.rollback()
        database.execute("UPDATE runs SET statut='echec', fin=?, erreur=? WHERE run_id=?",
                         (datetime.now(timezone.utc).isoformat(), str(erreur)[:1000], run_id))
        database.commit()
        database.close()
        raise
    database.close()
    resume = {"run_id": run_id, "nb_articles": len(articles), **mesures}
    LOG.info(json.dumps({"event": "regroupement", **resume}, ensure_ascii=False))
    return resume


def _afficher_themes(db_path: Path) -> None:
    database = sqlite3.connect(db_path)
    lignes = database.execute(
        "SELECT run_id, taille, nom FROM themes_du_jour ORDER BY taille DESC").fetchall()
    database.close()
    if lignes:
        print(f"Thèmes du run {lignes[0][0]} :")
    for _, taille, nom in lignes:
        print(f"  {taille:>3}  {nom}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Regroupement des articles par thèmes")
    parser.add_argument("--db", type=Path, default=Path("data/gazette.sqlite3"))
    parser.add_argument("--config", type=Path, default=Path("config/clustering.yaml"))
    parser.add_argument("--runs", type=Path, default=Path("data/runs"))
    parser.add_argument("--maintenant", help="date de fin de fenêtre ISO 8601 (rejouer un run)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    maintenant = datetime.fromisoformat(args.maintenant) if args.maintenant else None
    resume = executer_run(args.db, charger_config(args.config), maintenant,
                          dossier_runs=args.runs)
    print(json.dumps(resume, ensure_ascii=False, indent=2))
    _afficher_themes(args.db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
