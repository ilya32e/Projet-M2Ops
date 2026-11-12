"""Vectorisation des articles propres, avec cache en base (table embeddings).

Le texte vectorisé est « titre. extrait ». Un vecteur n'est calculé qu'une fois par
article et par modèle ; il est recalculé seulement si le texte de l'article change.
"""

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import numpy as np


class Encodeur(Protocol):
    modele: str
    version: str

    def encoder(self, textes: list[str]) -> np.ndarray: ...


class EncodeurFastEmbed:
    """Modèle multilingue léger, exécuté sur processeur avec ONNX Runtime (fastembed)."""

    def __init__(self, modele: str, dossier_cache: Path):
        import fastembed
        from fastembed import TextEmbedding

        self.modele = modele
        self.version = f"fastembed-{fastembed.__version__}"
        self._modele = TextEmbedding(modele, cache_dir=str(dossier_cache))

    def encoder(self, textes: list[str]) -> np.ndarray:
        return np.array(list(self._modele.embed(textes)), dtype=np.float32)


def texte_article(titre: str, extrait: str) -> str:
    return f"{titre}. {extrait}".strip()


def _hash(texte: str) -> str:
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def vectoriser(
    database: sqlite3.Connection,
    articles: list[tuple[str, str, str]],
    encodeur: Encodeur,
) -> tuple[np.ndarray, int]:
    """Renvoie les vecteurs normalisés des articles (id, titre, extrait), dans le même ordre.

    Seuls les articles absents du cache (ou dont le texte a changé) sont vectorisés.
    Renvoie aussi le nombre de vecteurs calculés pendant cet appel.
    """
    textes = {id_: texte_article(titre, extrait) for id_, titre, extrait in articles}
    en_cache = {
        article_id: (texte_hash, vecteur)
        for article_id, texte_hash, vecteur in database.execute(
            "SELECT article_id, texte_hash, vecteur FROM embeddings WHERE modele = ?",
            (encodeur.modele,),
        )
    }
    a_calculer = [
        id_ for id_, texte in textes.items()
        if id_ not in en_cache or en_cache[id_][0] != _hash(texte)
    ]
    if a_calculer:
        nouveaux = encodeur.encoder([textes[id_] for id_ in a_calculer])
        maintenant = datetime.now(timezone.utc).isoformat()
        database.executemany(
            """INSERT OR REPLACE INTO embeddings
               (article_id, modele, dimension, vecteur, texte_hash, cree_le)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (id_, encodeur.modele, int(vecteur.shape[0]),
                 vecteur.astype("<f4").tobytes(), _hash(textes[id_]), maintenant)
                for id_, vecteur in zip(a_calculer, nouveaux)
            ],
        )
        database.commit()
        for id_, vecteur in zip(a_calculer, nouveaux):
            en_cache[id_] = (_hash(textes[id_]), vecteur.astype("<f4").tobytes())
    vecteurs = np.vstack([
        np.frombuffer(en_cache[id_][1], dtype="<f4") for id_, _, _ in articles
    ]) if articles else np.zeros((0, 0), dtype=np.float32)
    normes = np.linalg.norm(vecteurs, axis=1, keepdims=True) if len(vecteurs) else 1
    return vecteurs / np.where(normes == 0, 1, normes), len(a_calculer)
