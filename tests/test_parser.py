import unittest
from pathlib import Path

from gazette.models import Source
from gazette.parser import parse_feed


class ParserTest(unittest.TestCase):
    def test_parse_rss_fixture_and_discard_incomplete_item(self) -> None:
        payload = Path("tests/fixtures/sample.xml").read_bytes()
        source = Source("Fixture", "PQN", "Test", "https://example.test/rss", "RSS public")

        items = parse_feed(payload, source)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Un titre de test")
        self.assertEqual(items[0].excerpt, "Un extrait & court pour vérifier le parseur.")
        self.assertEqual(items[0].url, "https://example.test/article-1")
        self.assertEqual(items[0].published_at, "2026-10-19T05:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
