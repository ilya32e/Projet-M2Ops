import html
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from .models import NewsItem, Source

LOG = logging.getLogger("gazette.parser")
TAG_RE = re.compile(r"<[^>]+>")


def _clean(value: object) -> str:
    text = html.unescape(str(value or ""))
    return " ".join(TAG_RE.sub(" ", text).split())


def _entry_text(entry: dict, *names: str) -> str:
    for name in names:
        value = entry.get(name)
        if value:
            return _clean(value)
    return ""


def _entry_link(entry: dict) -> str:
    for link in entry.get("links", []):
        if link.get("rel", "alternate") == "alternate" and link.get("href"):
            return link["href"].strip()
    return _clean(entry.get("link"))


def _entry_category(entry: dict) -> str:
    categories = [tag.get("term", "") for tag in entry.get("tags", [])]
    return ", ".join(_clean(category) for category in categories if category)


def _normalize_date(value: object) -> str | None:
    if isinstance(value, tuple):
        try:
            parsed = datetime(*value[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None
    elif value:
        try:
            parsed = parsedate_to_datetime(str(value))
        except (TypeError, ValueError, IndexError):
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def parse_feed(payload: bytes, source: Source) -> list[NewsItem]:
    parsed = feedparser.parse(payload)
    if parsed.bozo:
        LOG.warning("Flux mal formé pour %s: %s", source.name, parsed.bozo_exception)

    items = []
    for entry in parsed.entries:
        title = _entry_text(entry, "title")
        url = _entry_link(entry)
        if not title or not url:
            continue
        content = entry.get("content", [])
        content_value = content[0].get("value", "") if content else ""
        excerpt = _entry_text(entry, "summary", "description") or _clean(content_value)
        published_at = _normalize_date(
            entry.get("published_parsed")
            or entry.get("updated_parsed")
            or _entry_text(entry, "published", "updated")
        )
        if published_at is None:
            continue
        guid = _entry_text(entry, "id", "guid")
        category = _entry_category(entry)
        items.append(
            NewsItem(
                source=source.name,
                source_type=source.source_type,
                title=title,
                excerpt=excerpt,
                published_at=published_at,
                url=url,
                guid=guid,
                category=category,
                payload={
                    "title": title,
                    "description": excerpt[:280],
                    "published": published_at,
                    "link": url,
                    "guid": guid,
                    "category": category,
                    "feedparser_bozo": bool(parsed.bozo),
                },
                raw_payload=payload.decode("utf-8", errors="replace"),
            )
        )
    return items
