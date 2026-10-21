CREATE TABLE IF NOT EXISTS sources (
    nom TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    url_flux TEXT NOT NULL,
    actif INTEGER NOT NULL DEFAULT 1,
    derniere_reussite TEXT,
    echecs_consecutifs INTEGER NOT NULL DEFAULT 0,
    etag TEXT,
    last_modified TEXT
);

CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    lien TEXT NOT NULL,
    fichier TEXT NOT NULL,
    recupere_le TEXT NOT NULL,
    UNIQUE(source, lien)
);
