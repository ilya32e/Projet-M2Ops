# Dictionnaire de données du TD3

## Sources

La table SQLite `sources` est alimentée depuis [sources.csv](../sources.csv) et conserve l’état de chaque flux.

| Champ | Description |
|---|---|
| `nom` | Nom unique de la source |
| `type` | `PQR` ou `PQN` |
| `url_flux` | Adresse du flux RSS ou Atom |
| `actif` | 1 si la collecte est active, 0 si la source est en sommeil |
| `derniere_reussite` | Date UTC du dernier passage réussi |
| `echecs_consecutifs` | Nombre d’échecs successifs |
| `etag` | Valeur ETag reçue du serveur |
| `last_modified` | Valeur Last-Modified reçue du serveur |
| `derniere_erreur` | Dernière erreur rencontrée, limitée à 1000 caractères |
| `sommeil_jusqu_a` | Date UTC à laquelle une source en sommeil pourra être retentée |

## Articles bruts

Chaque entrée est écrite une seule fois dans `articles_bruts/` selon la clé naturelle `(source, lien)`.
Le fichier JSON contient `id`, `source`, `lien`, `titre`, `resume`, `publie_le`, `recupere_le`, `rubrique` et `payload`.
Le `payload` conserve l’entrée normalisée et le XML du flux reçu pour audit et rejeu ;
aucun article HTML complet, image binaire ou commentaire n’est collecté.

## Articles propres (TD 4)

Table `articles_propres` (migration `004_qualite.sql`), alimentée à chaque passage par la tâche `nettoyage`.

| Champ | Description |
|---|---|
| `id` | Identifiant de l'item brut (`articles.id`) : c'est le lien de traçabilité |
| `source`, `type_source` | Nom du média et `PQR` / `PQN` |
| `lien` | URL de l'article chez l'éditeur |
| `titre` | Titre normalisé (sans HTML, entités décodées, encodage réparé) |
| `extrait` | Extrait normalisé, **280 caractères au plus** |
| `publie_le` | Date de publication en ISO 8601 UTC |
| `rubrique` | Rubrique(s) annoncée(s) par le flux |
| `fichier_brut` | Nom du fichier dans `articles_bruts/` |
| `nettoye_le`, `passage` | Date du passage de nettoyage qui a produit la ligne |

## Rejets

Table `rejets` : mêmes `id`, `source`, `lien`, `titre`, `fichier_brut`, plus `regle` (identifiant `R01_publi` à `R09_doublon_approche`), `detail` (motif lisible, par exemple « Jaccard 0.95 avec Le Figaro « … » ») et `rejete_le`. Les règles sont décrites dans [qualite.md](qualite.md).

Un item brut est soit dans `articles_propres`, soit dans `rejets`, jamais dans les deux, et n'est traité qu'une fois.

## Mesures de qualité et alertes

- `mesures_qualite(passage, controle, valeur, seuil, ok, detail)` : résultat de chaque contrôle à chaque passage.
- `alertes(controle, en_echec_depuis)` : contrôles actuellement en échec, pour n'alerter qu'au changement d'état.
- `data/metriques.prom` : dernières valeurs au format Prometheus.
- `rapports/qualite-AAAA-MM-JJ.md` et `.json` : rapport du jour, réécrit à chaque passage.

## Traçabilité

D'un article propre, on remonte à sa source et à l'item brut tel que reçu :

```sql
SELECT p.titre, p.source, s.url_flux, a.recupere_le, p.fichier_brut
FROM articles_propres p
JOIN articles a ON a.id = p.id
JOIN sources s ON s.nom = p.source
WHERE p.id = ?;
```

Le fichier `articles_bruts/<fichier_brut>` contient l'entrée et le flux XML reçus ce jour-là.

## Contrat de données

**Ce qu'on stocke** : titre, extrait court (280 caractères au plus), lien, date, source, rubrique. C'est ce qu'on a le droit de republier : un index qui renvoie vers l'éditeur.

**Ce qu'on ne stocke pas** : le texte intégral des articles, les images, les commentaires, les noms d'auteurs ou toute autre donnée personnelle, ni le contenu des sources désactivées faute d'autorisation (Le Monde) ou qui refusent les robots.

**Fraîcheur** : collecte toutes les 30 minutes ; une source active sans collecte réussie depuis 2 heures déclenche le contrôle `C05_fraicheur_collecte`. L'édition ne retient que les articles publiés depuis moins de 24 heures.

**Rétention** :

| Donnée | Durée | Ensuite |
|---|---|---|
| `articles_bruts/` (items tels que reçus) | 90 jours | suppression |
| `articles_propres`, `rejets` | 90 jours | suppression |
| `mesures_qualite`, `rapports/` | 1 an | suppression |
| Éditions publiées | 30 jours en ligne | déplacées vers un stockage froid (archive compressée), conservées 1 an |

La purge automatique sera ajoutée avec l'infrastructure de production (TD 7) ; d'ici là, ces durées sont la règle écrite que l'équipe applique.
