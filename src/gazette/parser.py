import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from .models import NewsItem, Source

TAG_RE = re.compile(r"<[^>]+>")
ATOM = "{http://www.w3.org/2005/Atom}"


def _text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return " ".join(html.unescape(TAG_RE.sub(" ", "".join(element.itertext()))).split())


def _first_text(element: ET.Element, names: tuple[str, ...]) -> str:
    for name in names:
        child = element.find(name)
        if child is None:
            child = element.find(f"{ATOM}{name}")
        value = _text(child)
        if value:
            return value
    return ""


def _link(element: ET.Element) -> str:
    link = element.find("link")
    if link is not None and link.get("href"):
        return link.get("href", "").strip()
    for candidate in element.findall(f"{ATOM}link"):
        if candidate.get("rel", "alternate") == "alternate" and candidate.get("href"):
            return candidate.get("href", "").strip()
    return _text(link)


def _categories(element: ET.Element) -> str:
    values = [_text(child) for child in element.findall("category")]
    values += [_text(child) for child in element.findall(f"{ATOM}category")]
    return ", ".join(value for value in values if value)


def _normalize_date(value: str) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def parse_feed(payload: bytes, source: Source) -> list[NewsItem]:
    root = ET.fromstring(payload)
    entries = root.findall(".//item") or root.findall(f".//{ATOM}entry")
    items = []
    for entry in entries:
        title = _first_text(entry, ("title",))
        url = _link(entry)
        if not title or not url:
            continue
        excerpt = _first_text(entry, ("description", "summary", "content"))[:280]
        published_at = _normalize_date(_first_text(entry, ("pubDate", "published", "updated")))
        if published_at is None:
            continue
        guid = _first_text(entry, ("guid", "id"))
        category = _categories(entry)
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
                    "description": excerpt,
                    "published": published_at,
                    "link": url,
                    "guid": guid,
                    "category": category,
                    "raw_xml": ET.tostring(entry, encoding="unicode"),
                },
            )
        )
    return items
