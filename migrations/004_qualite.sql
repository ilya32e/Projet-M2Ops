-- Articles retenus après normalisation et règles d'exclusion.
-- id = identifiant de l'item brut (articles.id) : traçabilité vers articles_bruts/<id>.json
CREATE TABLE IF NOT EXISTS articles_propres (
    id TEXT PRIMARY KEY REFERENCES articles(id),
    source TEXT NOT NULL,
    type_source TEXT NOT NULL,
    lien TEXT NOT NULL,
    titre TEXT NOT NULL,
    extrait TEXT NOT NULL,
    publie_le TEXT NOT NULL,
    rubrique TEXT NOT NULL DEFAULT '',
    fichier_brut TEXT NOT NULL,
    nettoye_le TEXT NOT NULL,
    passage TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_propres_publie_le ON articles_propres(publie_le);

-- Items écartés, avec la règle qui les a écartés.
CREATE TABLE IF NOT EXISTS rejets (
    id TEXT PRIMARY KEY REFERENCES articles(id),
    source TEXT NOT NULL,
    lien TEXT NOT NULL,
    titre TEXT NOT NULL,
    regle TEXT NOT NULL,
    detail TEXT NOT NULL,
    fichier_brut TEXT NOT NULL,
    rejete_le TEXT NOT NULL,
    passage TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rejets_regle ON rejets(regle);

-- Résultat de chaque contrôle de qualité, à chaque passage (métriques).
CREATE TABLE IF NOT EXISTS mesures_qualite (
    passage TEXT NOT NULL,
    controle TEXT NOT NULL,
    valeur REAL NOT NULL,
    seuil TEXT NOT NULL,
    ok INTEGER NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (passage, controle)
);

-- État des alertes, pour n'alerter qu'au changement d'état (pas toutes les 30 minutes).
CREATE TABLE IF NOT EXISTS alertes (
    controle TEXT PRIMARY KEY,
    en_echec_depuis TEXT
);
