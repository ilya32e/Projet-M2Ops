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

    def test_parse_atom_fixture_and_normalize_date(self) -> None:
        payload = Path("tests/fixtures/sample.atom").read_bytes()
        source = Source("Fixture Atom", "PQN", "Test", "https://example.test/atom", "Atom")

        items = parse_feed(payload, source)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].url, "https://example.test/atom-1")
        self.assertEqual(items[0].published_at, "2026-10-21T05:30:00+00:00")
        self.assertEqual(items[0].category, "Monde")

    def test_discard_entry_with_invalid_date(self) -> None:
        payload = b"<rss><channel><item><title>Bad date</title><link>https://example.test/bad</link><pubDate>not-a-date</pubDate></item></channel></rss>"
        source = Source("Fixture Bad", "PQN", "Test", "https://example.test/bad", "RSS")

        self.assertEqual(parse_feed(payload, source), [])


if __name__ == "__main__":
    unittest.main()
