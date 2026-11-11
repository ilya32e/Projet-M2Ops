import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from gazette.controles import controler
from gazette.models import NewsItem, Source
from gazette.nettoyage import ecrire_rapport, nettoyer
from gazette.storage import connect, initialize, mark_success, store_item

MAINTENANT = datetime(2026, 11, 12, 6, 0, tzinfo=timezone.utc)


def item(source, titre, minutes_avant=60, lien=None, resume="Un extrait"):
    date = (MAINTENANT - timedelta(minutes=minutes_avant)).isoformat()
    return NewsItem(source, "PQR", titre, resume, date,
                    lien or f"https://example.test/{abs(hash(titre))}")


class QualiteTest(unittest.TestCase):
    def setUp(self):
        self.dossier = TemporaryDirectory()
        self.root = Path(self.dossier.name)
        self.db = self.root / "gazette.sqlite3"
        self.bruts = self.root / "articles_bruts"
        database = connect(self.db)
        initialize(database, [Source("A", "PQR", "Bretagne", "https://a.test/rss", "RSS"),
                              Source("B", "PQN", "Nationale", "https://b.test/rss", "RSS")],
                   Path("migrations"))
        for nom in ("A", "B"):
            mark_success(database, nom, None, None)
        database.execute("UPDATE sources SET derniere_reussite=?", (MAINTENANT.isoformat(),))
        database.commit()
        self.database = database

    def tearDown(self):
        self.database.close()
        self.dossier.cleanup()

    def ajouter(self, *items):
        for i in items:
            store_item(self.database, self.bruts, i)

    def test_nettoyage_remplit_propres_et_rejets_avec_tracabilite(self):
        self.ajouter(
            item("A", "Le conseil municipal vote le budget 2027", 120),
            item("B", "Le conseil municipal vote le budget 2027 !", 60),
            item("A", "Horoscope du jour : Bélier, Taureau, Gémeaux"),
        )
        bilan = nettoyer(self.db, self.bruts, maintenant=MAINTENANT)
        self.assertEqual((bilan["entres"], bilan["gardes"], bilan["rejetes"]), (3, 1, 2))
        self.assertEqual(bilan["par_regle"], {"R08_doublon_exact": 1, "R02_horoscope": 1})
        # Traçabilité : l'article propre pointe vers son fichier brut et sa source.
        source, fichier = self.database.execute(
            "SELECT source, fichier_brut FROM articles_propres"
        ).fetchone()
        self.assertEqual(source, "A")
        self.assertTrue((self.bruts / fichier).exists())

    def test_deux_passages_ne_retraitent_rien(self):
        self.ajouter(item("A", "Un premier article bien titré"))
        nettoyer(self.db, self.bruts, maintenant=MAINTENANT)
        second = nettoyer(self.db, self.bruts, maintenant=MAINTENANT)
        self.assertEqual(second["entres"], 0)

    def test_rapport_compte_par_regle_et_par_source(self):
        self.ajouter(item("A", "Programme TV : que regarder ce soir à la télé ?"),
                     item("A", "Un article d'information locale"))
        nettoyer(self.db, self.bruts, maintenant=MAINTENANT)
        chemin = ecrire_rapport(self.db, self.root / "rapports", maintenant=MAINTENANT)
        texte = chemin.read_text(encoding="utf-8")
        self.assertEqual(chemin.name, "qualite-2026-11-12.md")
        self.assertIn("| R03_programme_tv | 1 |", texte)
        self.assertIn("| A | 2 | 1 | 1 | 50% |", texte)

    def test_controle_en_echec_alerte_une_seule_fois_puis_retour_a_la_normale(self):
        self.ajouter(item("A", "Un article d'information locale"))
        nettoyer(self.db, self.bruts, maintenant=MAINTENANT)
        # On fabrique une donnée fausse : un article propre daté dans le futur.
        futur = (MAINTENANT + timedelta(days=2)).isoformat()
        self.database.execute("UPDATE articles_propres SET publie_le=?", (futur,))
        self.database.commit()
        envoyes = []
        metriques = self.root / "metriques.prom"

        def passage():
            return controler(self.db, metriques, webhook="https://hook.test",
                             maintenant=MAINTENANT, envoyer=lambda _w, m: envoyes.append(m))

        resultats = passage()
        echecs = [r["controle"] for r in resultats if not r["ok"]]
        self.assertEqual(echecs, ["C01_aucune_date_future"])
        self.assertEqual(len(envoyes), 1)
        self.assertIn("C01_aucune_date_future", envoyes[0])
        self.assertIn('gazette_controle_ok{controle="C01_aucune_date_future"} 0',
                      metriques.read_text(encoding="utf-8"))

        passage()  # toujours en échec : pas de nouvelle alerte
        self.assertEqual(len(envoyes), 1)

        self.database.execute("UPDATE articles_propres SET publie_le=?",
                              (MAINTENANT.isoformat(),))
        self.database.commit()
        passage()  # retour à la normale annoncé
        self.assertEqual(len(envoyes), 2)
        self.assertIn("de nouveau OK", envoyes[1])
        mesures = self.database.execute("SELECT COUNT(*) FROM mesures_qualite").fetchone()[0]
        self.assertGreater(mesures, 0)


if __name__ == "__main__":
    unittest.main()
