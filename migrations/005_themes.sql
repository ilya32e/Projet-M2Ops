-- Cache des vecteurs : un vecteur par article et par modèle, jamais recalculé.
CREATE TABLE IF NOT EXISTS embeddings (
    article_id TEXT NOT NULL REFERENCES articles_propres(id),
    modele TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    vecteur BLOB NOT NULL,          -- float32 little-endian
    texte_hash TEXT NOT NULL,       -- hash du texte vectorisé : recalcul si le texte change
    cree_le TEXT NOT NULL,
    PRIMARY KEY (article_id, modele)
);

-- Un run de regroupement = une exécution tracée.
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    debut TEXT NOT NULL,
    fin TEXT,
    statut TEXT NOT NULL,           -- en_cours, termine, echec
    declencheur TEXT NOT NULL,      -- airflow, manuel, test
    -- données
    fenetre_debut TEXT NOT NULL,
    fenetre_fin TEXT NOT NULL,
    nb_articles INTEGER NOT NULL,
    hash_entree TEXT NOT NULL,      -- sha256 des (id, titre, extrait) en entrée
    -- modèle
    modele TEXT NOT NULL,
    version_modele TEXT NOT NULL,
    -- paramètres, métriques, artefacts (JSON)
    parametres TEXT NOT NULL,
    hash_parametres TEXT NOT NULL,
    metriques TEXT,
    artefacts TEXT,
    erreur TEXT
);

CREATE TABLE IF NOT EXISTS themes (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    theme_id INTEGER NOT NULL,
    nom TEXT NOT NULL,
    mots_cles TEXT NOT NULL,        -- JSON : liste ordonnée
    taille INTEGER NOT NULL,
    PRIMARY KEY (run_id, theme_id)
);

CREATE TABLE IF NOT EXISTS articles_themes (
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    article_id TEXT NOT NULL REFERENCES articles_propres(id),
    theme_id INTEGER NOT NULL,      -- -1 = bruit (article isolé, sans thème)
    probabilite REAL NOT NULL,
    PRIMARY KEY (run_id, article_id)
);

-- Les thèmes en vigueur : ceux du dernier run terminé.
CREATE VIEW IF NOT EXISTS themes_du_jour AS
SELECT t.*, r.debut AS run_debut, r.fenetre_debut, r.fenetre_fin
FROM themes t JOIN runs r ON r.run_id = t.run_id
WHERE r.run_id = (SELECT run_id FROM runs WHERE statut = 'termine' ORDER BY debut DESC LIMIT 1);
