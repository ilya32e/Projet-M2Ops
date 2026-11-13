# Regroupement par thèmes et traçage des runs (MLOps)

Chaque jour, le pipeline regroupe les articles propres des dernières 24 heures en thèmes
nommés. Chaque exécution (un **run**) est tracée : données, modèle, paramètres,
métriques, artefacts. On sait donc toujours quel run a produit les thèmes en base.

## La chaîne

| Étape | Code | Ce qu'elle fait |
|---|---|---|
| Fenêtre de données | [`regroupement.articles_fenetre`](../src/gazette/regroupement.py) | articles propres publiés dans les 24 dernières heures |
| Vectorisation | [`embeddings.py`](../src/gazette/embeddings.py) | « titre. extrait » → vecteur de 384 nombres, **mis en cache** dans la table `embeddings` |
| Regroupement | [`regroupement.regrouper`](../src/gazette/regroupement.py) | HDBSCAN sur les vecteurs normalisés |
| Nommage | [`regroupement.nommer`](../src/gazette/regroupement.py) | les mots les plus discriminants de chaque thème |
| Stockage et traçage | [`regroupement.executer_run`](../src/gazette/regroupement.py) | tables `runs`, `themes`, `articles_themes` et fichiers d'artefacts |

Le run est lancé **par le pipeline, pas à la main** : tâche Airflow `regroupement_themes`,
juste après `nettoyage`. Le DAG passe toutes les 30 minutes, mais le regroupement ne
tourne qu'au premier passage après 5 h, 11 h, 17 h et 23 h UTC (paramètre
`planification.heures_utc`) ; les autres passages sautent la tâche (état *skipped*).
Le run de 5 h UTC donne les thèmes de l'édition de 7 h.

## Le modèle

- **Modèle d'embedding** : `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
  (multilingue, 384 dimensions, ~240 Mo), exécuté sur processeur avec **fastembed**
  (ONNX Runtime, sans PyTorch). Environ 1 seconde pour 300 articles.
- **Version** : le nom du modèle et la version de fastembed sont enregistrés dans chaque
  run (`modele`, `version_modele`). Le modèle est téléchargé une seule fois dans
  `data/modeles/`, jamais versionné dans Git.
- **Pas de fine-tuning**, pas d'API externe : aucun coût, aucune clé.

## Les paramètres

Tous dans [`config/clustering.yaml`](../config/clustering.yaml) : fenêtre (24 h), modèle,
algorithme et ses réglages (`min_cluster_size: 4`, `min_samples: 2`), nombre de
mots-clés, créneaux horaires. Chaque run en garde une copie (`runs.parametres`) et son
empreinte (`runs.hash_parametres`) : deux runs aux paramètres identiques ont le même hash.

## Pourquoi HDBSCAN : les trois approches comparées

Comparaison faite le 12 novembre 2026 sur 730 vrais articles (24 heures), mêmes vecteurs.

| Approche | Principe | Thèmes | Bruit | Taille médiane | Plus gros groupe | Silhouette |
|---|---|---:|---:|---:|---:|---:|
| KMeans, k = 15 | on impose le nombre de groupes | 15 | 0 % | 49 | 80 | 0,10 |
| KMeans, k = 30 | | 30 | 0 % | 24 | 49 | 0,11 |
| Agglomératif, seuil 0,8 | on fusionne jusqu'à un seuil de distance | 23 | 0 % | 4 | **289** | 0,05 |
| Agglomératif, seuil 0,6 | | 177 | 0 % | 2 | 40 | 0,19 |
| **HDBSCAN, taille min. 5** | on cherche les zones denses, le reste est du bruit | 26 | 58 % | 9 | 39 | **0,30** |
| **HDBSCAN, taille min. 3** | | 73 | 46 % | 4 | 18 | **0,36** |

- **KMeans** oblige à choisir le nombre de thèmes à l'avance, alors qu'il change chaque
  jour, et range chaque article dans un groupe : les faits divers isolés diluent les
  vrais thèmes (silhouette 0,10).
- **L'agglomératif** dépend d'un seuil difficile à régler : à 0,8 un groupe fourre-tout
  de 289 articles, à 0,6 une poussière de 177 groupes.
- **HDBSCAN** trouve seul le nombre de thèmes et **accepte le bruit** : un article isolé
  n'est pas forcé dans un thème. C'est ce qu'on veut pour une édition, qui ne parle que
  des sujets repris par plusieurs titres. Silhouette nettement meilleure.
- La troisième famille, les chaînes complètes comme **BERTopic** (réduction de dimension +
  HDBSCAN + nommage), fait la même chose que notre code avec plus de dépendances
  (UMAP, PyTorch). Écartée pour garder simple.

Réglage retenu : `min_cluster_size: 4` (un thème = au moins 4 articles), entre les deux
essais ci-dessus.

## Le nommage

Chaque thème devient un seul document (ses articles mis bout à bout). On calcule pour
chaque mot (et chaque paire de mots) sa fréquence dans le thème multipliée par sa rareté
dans les autres thèmes : c'est un TF-IDF calculé entre thèmes, la méthode de BERTopic.
Les mots vides français sont retirés. Le nom est fait des trois premiers mots-clés.

## Ce qu'un run trace

Table `runs`, une ligne par exécution :

| Catégorie | Colonnes |
|---|---|
| Identité | `run_id` (date UTC + suffixe aléatoire), `debut`, `fin`, `statut` (`en_cours`, `termine`, `echec`), `declencheur` (`airflow`, `pipeline`, `manuel`, `test`), `erreur` |
| Données | `fenetre_debut`, `fenetre_fin`, `nb_articles`, `hash_entree` (SHA-256 des id, titres et extraits en entrée) |
| Modèle | `modele`, `version_modele` |
| Paramètres | `parametres` (JSON), `hash_parametres` |
| Métriques | `metriques` (JSON) : `nb_themes`, `taille_mediane`, `taille_max`, `part_bruit`, `silhouette`, `vecteurs_calcules` (combien n'étaient pas déjà en cache) |
| Artefacts | `artefacts` (JSON) : chemins, relatifs à `data/`, de `runs/<run_id>/themes.json` (thèmes nommés avec exemples) et `runs/<run_id>/affectations.csv` (chaque article, son thème, sa probabilité) |

Les résultats sont reliés au run : `themes(run_id, theme_id, nom, mots_cles, taille)` et
`articles_themes(run_id, article_id, theme_id, probabilite)`, avec `theme_id = -1` pour
les articles isolés (bruit). La vue `themes_du_jour` donne les thèmes du **dernier run
terminé**.

**Pourquoi une table plutôt qu'un outil de suivi d'expériences** (MLflow, Weights &
Biases) : la base SQLite existe déjà, la table se lit avec une requête, et on n'ajoute
ni serveur ni dépendance lourde. Ce qui compte, c'est que le traçage soit systématique :
il est fait par `executer_run`, impossible à contourner, y compris en cas d'échec
(`statut = 'echec'` et le message d'erreur).

## Où regarder

**Les runs** :
```sql
SELECT run_id, declencheur, nb_articles, json_extract(metriques, '$.nb_themes') AS themes,
       json_extract(metriques, '$.part_bruit') AS bruit,
       json_extract(metriques, '$.silhouette') AS silhouette
FROM runs ORDER BY debut DESC;
```

**Les thèmes en vigueur et le run qui les a produits** :
```sql
SELECT run_id, taille, nom FROM themes_du_jour ORDER BY taille DESC;
```

**Les articles d'un thème** :
```sql
SELECT p.source, p.titre FROM articles_themes a JOIN articles_propres p ON p.id = a.article_id
WHERE a.run_id = ? AND a.theme_id = ? ORDER BY a.probabilite DESC;
```

**Dans VS Code** : extension « SQLite Viewer » sur `data/gazette.sqlite3`, ou les fichiers
`data/runs/<run_id>/themes.json`.

**Dans Airflow** : tâche `regroupement_themes` de chaque passage (son journal affiche le
résumé du run).

**Rejouer un run** sur la même fenêtre :
```powershell
$env:PYTHONPATH="src"; python -m gazette.regroupement --maintenant 2026-11-12T17:37:02+00:00
```
Même fenêtre, mêmes paramètres → même `hash_entree` et même `hash_parametres`.

## Les thèmes du jour

Run `20261112T173702Z-bcf5a3`, lancé par Airflow le 12 novembre 2026 à 17 h 37 UTC.
Fenêtre du 11/11 17 h 37 au 12/11 17 h 37 UTC, 748 articles, 51 thèmes, taille médiane 5,
51 % de bruit, silhouette 0,34. Les quinze plus gros :

| Thème | Articles |
|---|---:|
| lycées · bombe · alertes | 37 |
| huang · nvidia · jensen | 19 |
| épisode méditerranéen · var · vigilance | 17 |
| tessier · trappes · kévin | 16 |
| israélienne · gaza · six morts | 15 |
| ukraine · émissaires américains · poutine | 14 |
| pauvreté · français · secours catholique | 13 |
| librairie · exemplaires · goncourt | 10 |
| homme · tranchée · gorge | 9 |
| zidane · italie · zinédine | 9 |
| logement · espagne · ehpad | 8 |
| marine pen · référendum · constitution | 8 |
| excellence · fibre · judiciaire | 7 |
| places supplémentaires · licence · lecornu | 7 |
| depardieu · gérard · figurante | 7 |

## Relecture à la main (matière du TD 6)

À faire sur deux journées : ce qui est bon, ce qui est absurde, une hypothèse.

Premières observations (12 novembre) :

- **Bon** : les grands sujets du jour sont isolés proprement (alertes à la bombe dans les
  lycées, affaire Nvidia, épisode méditerranéen, attentat de Trappes, négociations sur
  l'Ukraine), et chaque nom suffit à comprendre le sujet.
- **Absurde** : « marine pen » au lieu de « Le Pen » ; « logement · espagne · ehpad »
  mélange visiblement deux sujets.
- **Hypothèses** : « le » est un mot vide, retiré au milieu du nom propre ; le mélange
  vient de la moitié d'articles en bruit, qui laisse des groupes de petite taille se
  coller entre eux.

| Date | Run | Bon | Absurde | Hypothèse |
|---|---|---|---|---|
| | | | | |
| | | | | |

Question à garder pour le TD 6 : qu'est-ce qu'un « bon » regroupement ?
