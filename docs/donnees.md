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

## Articles bruts

Chaque entrée est écrite une seule fois dans `articles_bruts/` selon la clé naturelle `(source, lien)`.
Le fichier JSON contient `id`, `source`, `lien`, `titre`, `resume`, `publie_le`, `recupere_le`, `rubrique` et `payload`.
Le `payload` ne contient que les métadonnées et l’extrait fourni par le flux ; aucun texte intégral, image ou commentaire n’est collecté.
