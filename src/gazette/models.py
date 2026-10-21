from dataclasses import dataclass, field


@dataclass(frozen=True)
class Source:
    name: str
    source_type: str
    region: str
    address: str
    format: str
    active: bool = True


@dataclass(frozen=True)
class NewsItem:
    source: str
    source_type: str
    title: str
    excerpt: str
    published_at: str
    url: str
    guid: str = ""
    category: str = ""
    payload: dict[str, str] = field(default_factory=dict)
    raw_payload: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "source_type": self.source_type,
            "title": self.title,
            "excerpt": self.excerpt,
            "published_at": self.published_at,
            "url": self.url,
        }
