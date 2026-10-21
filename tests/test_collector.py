import json
import sqlite3
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from gazette.collector import collect_once
from gazette.models import NewsItem
from gazette.storage import connect, initialize, store_item


class FeedHandler(BaseHTTPRequestHandler):
    failures_left = 0
    requests = 0

    def do_GET(self):  # noqa: N802
        type(self).requests += 1
        if type(self).failures_left:
            type(self).failures_left -= 1
            self.send_response(503)
            self.end_headers()
            return
        payload = b"""<?xml version='1.0'?><rss><channel><item>
          <title>Article brut</title><description>Extrait</description>
          <pubDate>Wed, 21 Oct 2026 07:00:00 +0200</pubDate>
          <guid>article-1</guid><link>https://example.test/article-1</link>
        </item></channel></rss>"""
        self.send_response(200)
        self.send_header("Content-Type", "application/rss+xml")
        self.send_header("ETag", '"v1"')
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):
        return


class CollectorTest(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), FeedHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_two_passes_write_zero_duplicates(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "sources.csv"
            sources.write_text(
                "nom,type,region,adresse,format\n"
                f"Test,PQN,Test,http://127.0.0.1:{self.server.server_port},RSS public\n",
                encoding="utf-8",
            )
            first = collect_once(sources, root / "gazette.sqlite3", root / "articles_bruts")
            second = collect_once(sources, root / "gazette.sqlite3", root / "articles_bruts")
            self.assertEqual(first["written"], 1)
            self.assertEqual(second["written"], 0)
            self.assertEqual(len(list((root / "articles_bruts").glob("*.json"))), 1)
            document = json.loads(next((root / "articles_bruts").glob("*.json")).read_text())
            self.assertEqual(document["lien"], "https://example.test/article-1")

    def test_three_failures_put_source_to_sleep(self):
        FeedHandler.failures_left = 3
        with TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "sources.csv"
            sources.write_text(
                "nom,type,region,adresse,format\n"
                f"Test,PQN,Test,http://127.0.0.1:{self.server.server_port},RSS public\n",
                encoding="utf-8",
            )
            for _ in range(3):
                collect_once(sources, root / "gazette.sqlite3", root / "articles_bruts", retries=1)
            with sqlite3.connect(root / "gazette.sqlite3") as database:
                active, failures = database.execute(
                    "SELECT actif, echecs_consecutifs FROM sources"
                ).fetchone()
            database.close()
            self.assertEqual(active, 0)
            self.assertEqual(failures, 3)

    def test_same_guid_from_two_sources_does_not_collide(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            database = connect(root / "gazette.sqlite3")
            initialize(database, [], Path("migrations"))
            first = NewsItem(
                "Source A",
                "PQN",
                "Titre",
                "Extrait",
                "2026-10-21T00:00:00+00:00",
                "https://example.test/a",
                "same-guid",
            )
            second = NewsItem(
                "Source B",
                "PQN",
                "Titre",
                "Extrait",
                "2026-10-21T00:00:00+00:00",
                "https://example.test/b",
                "same-guid",
            )
            self.assertTrue(store_item(database, root / "articles_bruts", first))
            self.assertTrue(store_item(database, root / "articles_bruts", second))
            self.assertEqual(database.execute("SELECT COUNT(*) FROM articles").fetchone()[0], 2)
            database.close()


if __name__ == "__main__":
    unittest.main()
