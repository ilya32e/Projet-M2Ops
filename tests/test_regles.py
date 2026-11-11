import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gazette.normalisation import mots_titre, nettoyer_texte
from gazette.regles import Article, evaluer

MAINTENANT = datetime(2026, 11, 12, 6, 0, tzinfo=timezone.utc)
HIER = (MAINTENANT - timedelta(hours=3)).isoformat()


def article(titre, extrait="Extrait", rubrique="", publie_le=HIER, source="Test", id_="x"):
    return Article(id_, source, titre, extrait, publie_le, rubrique, mots_titre(titre))


class ReglesFixtureTest(unittest.TestCase):
    """Chaque pollueur de la fixture est écarté par la bonne règle ; les vrais articles passent."""

    def test_fixture_pollueurs(self):
        cas = json.loads(Path("tests/fixtures/pollueurs.json").read_text(encoding="utf-8"))
        for exemple in cas:
            with self.subTest(titre=exemple["titre"]):
                # Le titre « Ã‰lection » est testé tel quel : c'est la règle R07 qu'on vérifie.
                titre = exemple["titre"] if exemple["attendu"] == "R07_encodage" \
                    else nettoyer_texte(exemple["titre"])
                rejet = evaluer(
                    article(titre, exemple["extrait"], exemple["rubrique"]), [], MAINTENANT
                )
                self.assertEqual(rejet.regle if rejet else None, exemple["attendu"])


class ReglesDatesEtDoublonsTest(unittest.TestCase):
    def test_r06_date_future(self):
        futur = (MAINTENANT + timedelta(days=1)).isoformat()
        rejet = evaluer(article("Un titre suffisamment long", publie_le=futur), [], MAINTENANT)
        self.assertEqual(rejet.regle, "R06_date_invalide")

    def test_r06_date_absente(self):
        rejet = evaluer(article("Un titre suffisamment long", publie_le=None), [], MAINTENANT)
        self.assertEqual(rejet.regle, "R06_date_invalide")

    def test_r08_doublon_exact_entre_deux_sources(self):
        garde = article("L'ambassadeur russe aux États-Unis est mort", source="Le Figaro", id_="a")
        copie = article("L’ambassadeur russe aux Etats-Unis est mort !", source="20 Minutes")
        self.assertEqual(evaluer(copie, [garde], MAINTENANT).regle, "R08_doublon_exact")

    def test_r09_doublon_approche(self):
        garde = article(
            "Partis politiques à Matignon après les violences : « On va y aller »", id_="a"
        )
        proche = article(
            "Partis politiques invités à Matignon après les violences : « On va y aller »"
        )
        self.assertEqual(evaluer(proche, [garde], MAINTENANT).regle, "R09_doublon_approche")

    def test_titres_proches_mais_differents_sont_gardes(self):
        mardi = article("Guerre en Ukraine : ce qu'il faut retenir de la situation du mardi 10",
                        id_="a")
        mercredi = article(
            "Guerre en Ukraine : ce qu'il faut retenir de la situation du mercredi 11"
        )
        self.assertIsNone(evaluer(mercredi, [mardi], MAINTENANT))


if __name__ == "__main__":
    unittest.main()
