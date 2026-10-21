# Contrôle qualité des données brutes

Ce document prépare le contrôle demandé pour le TD4. Il décrit les règles de rejet et
les premiers cas à examiner dans `articles_bruts/`.

## Règles de contrôle

Un item est rejeté ou mis en quarantaine lorsqu'il présente l'un des problèmes suivants :

- titre ou lien absent ;
- date absente, invalide ou plus ancienne que 24 heures pour l'édition du jour ;
- doublon selon la clé `(source, lien)` ;
- texte intégral, image, commentaire ou donnée personnelle dans le payload ;
- publi-reportage, contenu promotionnel, publicité ou lien commercial ;
- horoscope, programme TV, jeu ou contenu purement récréatif ;
- extrait vide, illisible ou manifestement encodé incorrectement ;
- rubrique incohérente avec le titre ou source non autorisée.

Les règles éditoriales ne rejettent pas automatiquement un article de sport, de culture,
de science ou d'économie : ces sujets peuvent constituer un thème de l'édition. Ils sont
marqués pour revue lorsqu'ils semblent promotionnels ou trop spécialisés.

## Premiers cas à examiner

Les éléments ci-dessous ont été observés dans la collecte du 21 octobre 2026. Ils sont
des candidats à une revue manuelle, pas des rejets automatiques définitifs.

| Source | Titre ou motif | Décision provisoire | Motif du contrôle |
|---|---|---|---|
| Ici Nord | Le LOSC a un gros problème en attaque... | À revoir | Sport très spécialisé |
| Ici Nord | Le groupement de football amateur 100 % féminin... | À revoir | Article sportif local |
| Ouest-France | Caméra Veo, chaîne YouTube... | À revoir | Risque de contenu promotionnel |
| Libération | « Clayface » : le dernier avatar des studios DC... | À revoir | Promotion culturelle/cinéma |
| Le Figaro | L’Orchestre du nouveau monde... | À revoir | Culture et risque de publi-reportage |
| Ici Nord | Neuf sommeliers en lice pour devenir Meilleur ouvrier de France | À revoir | Concours et contenu lifestyle |
| Ici Nord | « La Huitième Sorcière » : un album jeunesse... | À revoir | Promotion potentielle d’un ouvrage |
| Ici Nord | Seconde main, réparation, upcycling... | À revoir | Peut être éditorial ou promotionnel |
| Ouest-France | Témoignage d’un coureur après une chute | À revoir | Article sportif/témoignage |
| Flux sans titre ou date | Règle de rejet à vérifier sur chaque passage | Rejeter | Item inexploitable |

Au premier contrôle, aucun horoscope, programme TV ou jeu n'a été identifié dans les
fichiers disponibles. Ces motifs restent néanmoins des règles de filtrage à tester lors
des prochaines collectes.

## Actions prévues

1. Ajouter une décision `accepted`, `review` ou `rejected` au contrôle qualité du TD4.
2. Conserver la raison du rejet dans un journal, sans conserver de texte intégral.
3. Vérifier manuellement les dix candidats avant de modifier la taxonomie des thèmes.
4. Suivre le taux de rejet par source pour repérer les flux trop promotionnels ou bruités.
