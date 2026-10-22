import argparse
import json
import logging
import socket
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .parser import parse_feed
from .sources import load_sources
from .storage import active_sources, connect, initialize, mark_failure, mark_success, store_item

LOG = logging.getLogger("gazette.collector")
RETRYABLE = {408, 429, 500, 502, 503, 504}


def _retry_delay(headers, attempt: int) -> int:
    retry_after = headers.get("Retry-After") if headers else None
    if retry_after:
        try:
            return max(0, int(retry_after))
        except (TypeError, ValueError):
            pass
    return 2**attempt


def fetch(url: str, headers: dict[str, str], timeout: int, retries: int = 3, sleep=time.sleep):
    request_headers = {
        "User-Agent": "LaGazette/0.1 (+RSS reader; contact: team@example.invalid)",
        **headers,
    }
    for attempt in range(retries):
        try:
            request = Request(url, headers=request_headers)
            with urlopen(request, timeout=timeout) as response:
                return response.status, response.headers, response.read()
        except HTTPError as error:
            if error.code == 304:
                return 304, error.headers, b""
            if error.code not in RETRYABLE or attempt == retries - 1:
                raise
            delay = _retry_delay(error.headers, attempt)
        except (URLError, TimeoutError, socket.timeout):
            if attempt == retries - 1:
                raise
            delay = 2**attempt
        sleep(delay)
    raise RuntimeError("fetch failed")


def collect_once(
    sources_file: Path = Path("sources.csv"),
    db_path: Path = Path("data/gazette.sqlite3"),
    raw_dir: Path = Path("articles_bruts"),
    timeout: int = 15,
    retries: int = 3,
) -> dict[str, int]:
    database = connect(db_path)
    initialize(database, load_sources(sources_file), Path("migrations"))
    counters = {"sources": 0, "received": 0, "written": 0, "ignored": 0, "errors": 0}
    for source_row in active_sources(database):
        started = time.monotonic()
        counters["sources"] += 1
        headers = {}
        if source_row["etag"]:
            headers["If-None-Match"] = source_row["etag"]
        if source_row["last_modified"]:
            headers["If-Modified-Since"] = source_row["last_modified"]
        try:
            status, response_headers, payload = fetch(
                source_row["url_flux"], headers, timeout, retries
            )
            if status == 304:
                mark_success(
                    database,
                    source_row["nom"],
                    source_row["etag"],
                    source_row["last_modified"],
                )
                received = written = ignored = 0
            else:
                source = next(s for s in load_sources(sources_file) if s.name == source_row["nom"])
                items = parse_feed(payload, source)
                received = len(items)
                written = sum(store_item(database, raw_dir, item) for item in items)
                ignored = received - written
                mark_success(
                    database,
                    source_row["nom"],
                    response_headers.get("ETag"),
                    response_headers.get("Last-Modified"),
                )
            counters["received"] += received
            counters["written"] += written
            counters["ignored"] += ignored
            LOG.info(
                json.dumps(
                    {
                        "source": source_row["nom"],
                        "received": received,
                        "written": written,
                        "ignored": ignored,
                        "duration_ms": round((time.monotonic() - started) * 1000),
                    }
                )
            )
        except Exception as error:
            counters["errors"] += 1
            failures = mark_failure(database, source_row["nom"], str(error))
            LOG.error(
                json.dumps(
                    {
                        "source": source_row["nom"],
                        "error": str(error),
                        "failures": failures,
                        "sleeping": failures >= 3,
                        "duration_ms": round((time.monotonic() - started) * 1000),
                    }
                )
            )
    database.close()
    LOG.info(json.dumps({"event": "collection_summary", **counters}))
    return counters


def main() -> int:
    parser = argparse.ArgumentParser(description="Collecte périodique des flux de La Gazette")
    parser.add_argument("--sources-file", type=Path, default=Path("sources.csv"))
    parser.add_argument("--db", type=Path, default=Path("data/gazette.sqlite3"))
    parser.add_argument("--raw-dir", type=Path, default=Path("articles_bruts"))
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="Intervalle en secondes; 0 exécute un seul passage",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    while True:
        collect_once(args.sources_file, args.db, args.raw_dir)
        if args.interval <= 0:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
