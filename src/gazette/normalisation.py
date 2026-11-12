"""Transformations pures appliquées aux titres, extraits et dates.

Chaque fonction ne fait qu'une chose, ne lit ni n'écrit rien en dehors de ses
arguments, et a son propre test dans tests/test_normalisation.py.
"""

import html
import re
import unicodedata
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

EXTRAIT_MAX = 280

_BALISE = re.compile(r"<[^>]+>")
_ESPACES = re.compile(r"\s+")
_MOJIBAKE = re.compile(r"Ã.|â€|Â[\xa0-\xbf]")
_MOTS = re.compile(r"[a-z0-9]+")


def retirer_html(texte: str) -> str:
    """Remplace chaque balise HTML par une espace."""
    return _BALISE.sub(" ", texte)


def decoder_entites(texte: str) -> str:
    """Décode les entités HTML (&amp;, &eacute;, &#8217;...)."""
    return html.unescape(texte)


def normaliser_espaces(texte: str) -> str:
    """Remplace toute suite d'espaces, tabulations ou retours ligne par une espace."""
    return _ESPACES.sub(" ", texte).strip()


def reparer_encodage(texte: str) -> str:
    """Répare un texte UTF-8 lu à tort en Latin-1 ou Windows-1252 (« Ã© » -> « é »)."""
    if not _MOJIBAKE.search(texte):
        return texte
    for codec in ("cp1252", "latin-1"):
        try:
            return texte.encode(codec).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return texte


def encodage_casse(texte: str) -> bool:
    """Vrai si le texte contient encore des séquences d'encodage cassé ou le caractère �."""
    return bool(_MOJIBAKE.search(texte)) or "�" in texte


def date_utc(valeur: str) -> str | None:
    """Convertit une date RFC 822 ou ISO 8601 en ISO 8601 UTC ; None si illisible."""
    if not valeur:
        return None
    try:
        date = parsedate_to_datetime(valeur)
    except (TypeError, ValueError, IndexError):
        try:
            date = datetime.fromisoformat(valeur.replace("Z", "+00:00"))
        except ValueError:
            return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc).isoformat()


def borner_extrait(texte: str, longueur: int = EXTRAIT_MAX) -> str:
    """Coupe l'extrait à `longueur` caractères au plus, sur une fin de mot, avec « … »."""
    if len(texte) <= longueur:
        return texte
    coupe = texte[: longueur - 1]
    if " " in coupe:
        coupe = coupe.rsplit(" ", 1)[0]
    return coupe.rstrip(" ,;:.-") + "…"


def nettoyer_texte(texte: str) -> str:
    """Enchaîne les transformations de texte : HTML, entités, encodage, espaces."""
    return normaliser_espaces(reparer_encodage(decoder_entites(retirer_html(texte or ""))))


def mots_titre(titre: str) -> frozenset[str]:
    """Ensemble des mots d'un titre, en minuscules et sans accents, pour comparer des titres."""
    sans_accents = unicodedata.normalize("NFKD", titre.lower())
    sans_accents = "".join(c for c in sans_accents if not unicodedata.combining(c))
    return frozenset(_MOTS.findall(sans_accents))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Similarité de Jaccard entre deux ensembles de mots (0 = rien en commun, 1 = identiques)."""
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)
