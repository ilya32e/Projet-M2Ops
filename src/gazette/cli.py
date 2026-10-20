import argparse
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

from .parser import parse_feed
from .sources import find_source


def fetch(url: str, timeout: int) -> bytes:
    request = Request(url, headers={"User-Agent": "LaGazette/0.1 (+RSS reader)"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lit un flux déclaré et écrit des items JSONL.")
    parser.add_argument("--source", required=True, help="Nom exact de la source dans sources.csv")
    parser.add_argument("--sources-file", type=Path, default=Path("sources.csv"))
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source = find_source(args.sources_file, args.source)
    payload = fetch(source.address, int(os.getenv("GAZETTE_TIMEOUT_SECONDS", "15")))
    items = parse_feed(payload, source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for item in items:
            stream.write(json.dumps(item.as_dict(), ensure_ascii=False) + "\n")
    print(f"{len(items)} item(s) écrit(s) depuis {source.name} dans {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
