"""Règles d'exclusion de La Gazette.

Chaque règle a un identifiant stable (R01_publi...) repris dans la table `rejets`
et dans le rapport de qualité. Les motifs sont volontairement lisibles : on doit
pouvoir comprendre et ajuster une règle sans lire le reste du code.
Documentation et exemples : docs/qualite.md.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .normalisation import encodage_casse, jaccard

# --- Paramètres ajustables -------------------------------------------------
SEUIL_DOUBLON_APPROCHE = 0.8  # Jaccard sur les mots du titre
FENETRE_DOUBLONS = timedelta(hours=48)  # on ne compare qu'aux articles récents
TOLERANCE_FUTUR = timedelta(minutes=15)  # décalage d'horloge toléré
TITRE_MIN_CARACTERES = 10

MOTIFS = {
    "R01_publi": re.compile(
        r"publi[- ]?(reportage|r[ée]dactionnel|information)|contenu (sponsoris|partenaire)"
        r"|en partenariat avec|sponsoris[ée]|\bcode promo\b|\bbons? plans?\b",
        re.I,
    ),
    "R02_horoscope": re.compile(r"\bhoroscope|\bastrolog|signe du zodiaque", re.I),
    "R03_programme_tv": re.compile(
        r"programme t[ée]l[ée]|programme tv|\bce soir (à|a) la t[ée]l[ée]|que regarder ce soir"
        r"|\bt[ée]l[ée] ce soir\b",
        re.I,
    ),
    "R04_jeux": re.compile(
        r"jeu[- ]concours|\bgrand jeu\b|tentez de gagner|\bà gagner\b|mots[- ]crois[ée]s|\bsudoku"
        r"|espace jeux|r[ée]sultats? (du |de l')?(loto|euromillions|keno)",
        re.I,
    ),
}

RUBRIQUES_EXCLUES = {
    "R01_publi": {"partenaire", "publi-reportage", "contenu sponsorisé", "bons plans"},
    "R02_horoscope": {"horoscope", "astrologie"},
    "R03_programme_tv": {"programme tv", "télévision ce soir"},
    "R04_jeux": {"jeux", "concours"},
}


@dataclass(frozen=True)
class Article:
    id: str
    source: str
    titre: str
    extrait: str
    publie_le: str | None
    rubrique: str
    mots: frozenset[str]


@dataclass(frozen=True)
class Rejet:
    regle: str
    detail: str


def regle_contenu(article: Article) -> Rejet | None:
    """R01 à R04 : contenus qui ne relèvent pas de l'information (titre, extrait ou rubrique)."""
    texte = f"{article.titre} {article.extrait}"
    rubriques = {r.strip().lower() for r in article.rubrique.split(",") if r.strip()}
    for regle, motif in MOTIFS.items():
        trouve = motif.search(texte)
        if trouve:
            return Rejet(regle, f"motif « {trouve.group(0)} »")
        commun = rubriques & RUBRIQUES_EXCLUES[regle]
        if commun:
            return Rejet(regle, f"rubrique « {sorted(commun)[0]} »")
    return None


def regle_titre_vide(article: Article) -> Rejet | None:
    """R05 : titre vide ou trop court pour être compris seul."""
    if len(article.titre) < TITRE_MIN_CARACTERES:
        return Rejet("R05_titre_vide", f"titre de {len(article.titre)} caractère(s)")
    return None


def regle_date(article: Article, maintenant: datetime) -> Rejet | None:
    """R06 : date absente, illisible ou dans le futur."""
    if not article.publie_le:
        return Rejet("R06_date_invalide", "date absente ou illisible")
    date = datetime.fromisoformat(article.publie_le)
    if date > maintenant + TOLERANCE_FUTUR:
        return Rejet("R06_date_invalide", f"date future {article.publie_le}")
    return None


def regle_encodage(article: Article) -> Rejet | None:
    """R07 : encodage encore cassé après tentative de réparation."""
    if encodage_casse(article.titre) or encodage_casse(article.extrait):
        return Rejet("R07_encodage", "séquences Ã©/â€ ou caractère � restant")
    return None


def regle_doublons(article: Article, gardes: list[Article]) -> Rejet | None:
    """R08 doublon exact, R09 doublon approché : même dépêche déjà gardée récemment."""
    meilleur, score = None, 0.0
    for autre in gardes:
        if autre.mots == article.mots:
            return Rejet(
                "R08_doublon_exact", f"même titre que {autre.source} « {autre.titre[:50]} »"
            )
        similarite = jaccard(article.mots, autre.mots)
        if similarite > score:
            meilleur, score = autre, similarite
    if meilleur is not None and score >= SEUIL_DOUBLON_APPROCHE:
        return Rejet(
            "R09_doublon_approche",
            f"Jaccard {score:.2f} avec {meilleur.source} « {meilleur.titre[:50]} »",
        )
    return None


def evaluer(
    article: Article, gardes: list[Article], maintenant: datetime | None = None
) -> Rejet | None:
    """Applique les règles dans l'ordre.

    Renvoie le premier rejet, ou None si l'article est gardé.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    return (
        regle_titre_vide(article)
        or regle_date(article, maintenant)
        or regle_encodage(article)
        or regle_contenu(article)
        or regle_doublons(article, gardes)
    )
