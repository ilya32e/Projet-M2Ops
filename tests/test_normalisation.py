import unittest

from gazette import normalisation as n


class NormalisationTest(unittest.TestCase):
    def test_retirer_html(self):
        self.assertEqual(n.retirer_html("<p>Un <b>titre</b></p>").split(), ["Un", "titre"])

    def test_decoder_entites(self):
        self.assertEqual(n.decoder_entites("L&#8217;&eacute;t&eacute; &amp; co"), "L’été & co")

    def test_normaliser_espaces(self):
        self.assertEqual(n.normaliser_espaces("  un \n\t deux  "), "un deux")

    def test_reparer_encodage(self):
        casse = "Élection à Rennes".encode("utf-8").decode("cp1252", errors="replace")
        self.assertNotEqual(casse, "Élection à Rennes")
        self.assertEqual(n.reparer_encodage(casse), "Élection à Rennes")
        self.assertEqual(n.reparer_encodage("déjà propre"), "déjà propre")

    def test_encodage_casse(self):
        self.assertTrue(n.encodage_casse("caf�"))
        self.assertTrue(n.encodage_casse("dÃ©but"))
        self.assertFalse(n.encodage_casse("début"))

    def test_date_utc(self):
        self.assertEqual(n.date_utc("Wed, 21 Oct 2026 07:00:00 +0200"),
                         "2026-10-21T05:00:00+00:00")
        self.assertEqual(n.date_utc("2026-10-21T05:00:00Z"), "2026-10-21T05:00:00+00:00")
        self.assertIsNone(n.date_utc("hier soir"))
        self.assertIsNone(n.date_utc(""))

    def test_borner_extrait(self):
        texte = "mot " * 100
        borne = n.borner_extrait(texte, 50)
        self.assertLessEqual(len(borne), 50)
        self.assertTrue(borne.endswith("…"))
        self.assertEqual(n.borner_extrait("court", 50), "court")

    def test_nettoyer_texte(self):
        casse = "Été".encode("utf-8").decode("cp1252")
        self.assertEqual(n.nettoyer_texte(f"<p>{casse}\n  &amp; chaud</p>"), "Été & chaud")

    def test_mots_titre(self):
        self.assertEqual(n.mots_titre("L'Été, à Paris !"), frozenset({"l", "ete", "a", "paris"}))

    def test_jaccard(self):
        a, b = frozenset({"a", "b", "c"}), frozenset({"a", "b", "d"})
        self.assertAlmostEqual(n.jaccard(a, b), 0.5)
        self.assertEqual(n.jaccard(a, a), 1.0)


if __name__ == "__main__":
    unittest.main()
