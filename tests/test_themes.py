import json
import os
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from gazette.embeddings import vectoriser
from gazette.regroupement import charger_config, doit_tourner, executer_run, nommer
from gazette.storage import apply_migrations, connect

MAINTENANT = datetime(2026, 11, 12, 5, 10, tzinfo=timezone.utc)

SUJETS = {
    "ukraine": ["Ukraine : négociations à Abou Dhabi", "Kyiv et Moscou reprennent le dialogue",
                "Ukraine : Poutine reçoit les émissaires", "Abou Dhabi accueille les négociateurs"],
    "meteo": ["Épisode méditerranéen : vigilance orange", "Orages et pluies intenses dans le Gard",
              "Vigilance orange pour les orages", "Pluies intenses : routes coupées"],
    "nvidia": ["Nvidia : le PDG Jensen Huang fragilisé", "Affaire Nvidia : Jensen Huang répond",
               "Nvidia chute en Bourse après l'affaire",
               "Jensen Huang face aux actionnaires de Nvidia"],
}

DIX_ARTICLES = [
    "Guerre en Ukraine : les négociations d'Abou Dhabi mises en échec",
    "Ukraine : Kyiv et Moscou renouent le dialogue à Abou Dhabi",
    "Épisode méditerranéen : vigilance orange pluie-inondation dans le Gard",
    "Orages : pluies intenses et routes coupées dans l'Hérault",
    "Nvidia : le PDG Jensen Huang de plus en plus fragilisé",
    "Affaire Nvidia : Jensen Huang soupçonné d'une autre infidélité",
    "Football : Zidane confirme le forfait de Mbappé contre l'Italie",
    "Logement : grève des locataires en Espagne",
    "Le Secours catholique alerte sur la pauvreté en France",
    "Cop31 : la conférence sur le climat s'ouvre à Antalya",
]


class EncodeurDeTest:
    """Encodeur déterministe : un vecteur par sujet, plus un petit bruit par article."""

    modele = "test/encodeur-sujets"
    version = "1"

    def __init__(self):
        self.appels = 0

    def encoder(self, textes):
        self.appels += len(textes)
        vecteurs = []
        for texte in textes:
            base = np.zeros(8)
            for rang, mots in enumerate(([s.split()[0] for s in SUJETS["ukraine"]] + ["Kyiv"],
                                         ["Épisode", "Orages", "Vigilance", "Pluies"],
                                         ["Nvidia", "Affaire", "Jensen"])):
                if any(mot in texte for mot in mots):
                    base[rang] = 1.0
            if not base.any():
                base[7] = 1.0                      # article hors sujet : sa propre direction
            base[3 + sum(map(ord, texte)) % 4] += 0.05   # petit bruit, stable entre lancements
            vecteurs.append(base)
        return np.array(vecteurs, dtype=np.float32)


def base_avec_articles(dossier: Path, titres: list[str]) -> Path:
    db = dossier / "gazette.sqlite3"
    database = connect(db)
    apply_migrations(database, Path("migrations"))
    for i, titre in enumerate(titres):
        date = (MAINTENANT - timedelta(hours=1, minutes=i)).isoformat()
        database.execute("INSERT INTO articles VALUES (?, 'S', ?, ?, ?)",
                         (f"id{i:02d}", f"https://x.test/{i}", f"f{i}.json", date))
        database.execute(
            """INSERT INTO articles_propres (id, source, type_source, lien, titre, extrait,
               publie_le, rubrique, fichier_brut, nettoye_le, passage)
               VALUES (?, 'S', 'PQN', ?, ?, '', ?, '', ?, ?, ?)""",
            (f"id{i:02d}", f"https://x.test/{i}", titre, date, f"f{i}.json", date, date))
    database.commit()
    database.close()
    return db


class EmbeddingsTest(unittest.TestCase):
    def test_cache_ne_recalcule_pas(self):
        with TemporaryDirectory() as dossier:
            db = base_avec_articles(Path(dossier), DIX_ARTICLES)
            database = sqlite3.connect(db)
            articles = list(database.execute("SELECT id, titre, extrait FROM articles_propres"))
            encodeur = EncodeurDeTest()
            premier, calcules = vectoriser(database, articles, encodeur)
            second, recalcules = vectoriser(database, articles, encodeur)
            database.close()
            self.assertEqual((calcules, recalcules), (10, 0))
            self.assertEqual(encodeur.appels, 10)
            np.testing.assert_allclose(premier, second)
            np.testing.assert_allclose(np.linalg.norm(premier, axis=1), 1, rtol=1e-5)

    @unittest.skipIf(os.getenv("GAZETTE_TESTS_SANS_MODELE"), "modèle non téléchargé")
    def test_vrai_modele_sur_dix_articles(self):
        """Le modèle multilingue rapproche les articles d'un même sujet."""
        from gazette.embeddings import EncodeurFastEmbed

        config = charger_config(Path("config/clustering.yaml"))
        encodeur = EncodeurFastEmbed(config["embeddings"]["modele"],
                                     Path(config["embeddings"]["dossier_cache"]))
        vecteurs = encodeur.encoder(DIX_ARTICLES)
        self.assertEqual(vecteurs.shape, (10, 384))
        vecteurs /= np.linalg.norm(vecteurs, axis=1, keepdims=True)
        similarite = vecteurs @ vecteurs.T
        # Les deux articles sur l'Ukraine sont plus proches entre eux que d'un article sur Nvidia.
        self.assertGreater(similarite[0, 1], similarite[0, 4])
        self.assertGreater(similarite[4, 5], similarite[4, 0])


class RegroupementTest(unittest.TestCase):
    def setUp(self):
        self.dossier = TemporaryDirectory()
        self.root = Path(self.dossier.name)
        titres = [t for sujet in SUJETS.values() for t in sujet]
        titres.append("Un article isolé sur le jardinage")
        self.db = base_avec_articles(self.root, titres)
        self.config = charger_config(Path("config/clustering.yaml"))

    def tearDown(self):
        self.dossier.cleanup()

    def lancer(self):
        return executer_run(self.db, self.config, MAINTENANT, encodeur=EncodeurDeTest(),
                            dossier_runs=self.root / "runs", declencheur="test")

    def test_run_trace_donnees_parametres_metriques_artefacts(self):
        resume = self.lancer()
        self.assertEqual(resume["nb_themes"], 3)
        database = sqlite3.connect(self.db)
        run = database.execute(
            "SELECT statut, nb_articles, hash_entree, modele, parametres, metriques, artefacts"
            " FROM runs").fetchone()
        themes = database.execute("SELECT nom, taille FROM themes_du_jour").fetchall()
        affectations = database.execute("SELECT COUNT(*) FROM articles_themes").fetchone()[0]
        database.close()
        statut, nb, hash_entree, modele, parametres, metriques, artefacts = run
        self.assertEqual((statut, nb, modele), ("termine", 13, "test/encodeur-sujets"))
        self.assertEqual(len(hash_entree), 64)
        self.assertEqual(json.loads(parametres)["regroupement"]["algorithme"], "hdbscan")
        self.assertEqual(json.loads(metriques)["nb_themes"], 3)
        for chemin in json.loads(artefacts).values():
            self.assertTrue((self.root / chemin).exists())
        self.assertEqual(sorted(t for _, t in themes), [4, 4, 4])
        self.assertEqual(affectations, 13)
        noms = " ".join(nom for nom, _ in themes).lower()
        self.assertIn("nvidia", noms)

    def test_meme_entree_meme_hash(self):
        self.lancer()
        self.lancer()
        database = sqlite3.connect(self.db)
        hashes = {h for (h,) in database.execute("SELECT hash_entree FROM runs")}
        derniers = database.execute("SELECT COUNT(DISTINCT run_id) FROM themes_du_jour").fetchone()
        database.close()
        self.assertEqual(len(hashes), 1)
        self.assertEqual(derniers[0], 1)  # themes_du_jour ne montre que le dernier run

    def test_planification(self):
        database = connect(self.db)
        apply_migrations(database, Path("migrations"))
        self.assertTrue(doit_tourner(database, MAINTENANT, [5, 11]))
        database.close()
        self.lancer()
        database = connect(self.db)
        self.assertFalse(doit_tourner(database, MAINTENANT + timedelta(minutes=30), [5, 11]))
        self.assertTrue(doit_tourner(database, MAINTENANT + timedelta(hours=6), [5, 11]))
        database.close()


class NommageTest(unittest.TestCase):
    def test_mots_discriminants(self):
        textes = SUJETS["nvidia"] + SUJETS["meteo"]
        etiquettes = np.array([0] * 4 + [1] * 4)
        noms = nommer(textes, etiquettes, nb_mots_cles=3, nb_mots_nom=2)
        self.assertIn("nvidia", noms[0]["mots_cles"] + [noms[0]["nom"]])
        self.assertNotIn("le", noms[0]["mots_cles"])


if __name__ == "__main__":
    unittest.main()
