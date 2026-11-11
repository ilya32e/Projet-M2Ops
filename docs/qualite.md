# Qualité des données

Entre `articles_bruts/` et l'édition, chaque item passe par trois étapes, enchaînées par
le DAG Airflow `gazette_collecte` après chaque collecte (toutes les 30 minutes) :

1. **Normalisation** ([`normalisation.py`](../src/gazette/normalisation.py)) : une fonction
   pure par transformation, chacune testée dans `tests/test_normalisation.py`.
2. **Règles d'exclusion** ([`regles.py`](../src/gazette/regles.py)) : l'item va dans
   `articles_propres` ou dans `rejets` avec l'identifiant de la règle qui l'a écarté.
3. **Contrôles de qualité** ([`controles.py`](../src/gazette/controles.py)) : des faits
   vérifiés sur les vraies données, publiés en métriques, avec alerte Discord.

Un rapport est réécrit à chaque passage dans `rapports/qualite-AAAA-MM-JJ.md` (et `.json`).

## Les dix pollueurs observés

Relevés dans la collecte du 21 octobre au 11 novembre 2026.

| # | Pollueur | Exemple réel | Règle |
|---|---|---|---|
| 1 | Jeu-concours d'un média | Ici Nord : « "Voyage, voyage", ICI relance son grand jeu avec 10.000 euros de vacances à gagner » | R04_jeux |
| 2 | Page de jeux (mots croisés, sudoku) | La Dépêche : « La Dépêche du Midi lance son espace jeux : à vos neurones, prêts, jouez ! » | R04_jeux |
| 3 | Dépêche d'agence reprise presque à l'identique | Libération et Le Figaro : « Partis politiques (invités) à Matignon après les violences… » (Jaccard 0,95) | R09_doublon_approche |
| 4 | Même dépêche, réécrite légèrement | Le Figaro et Ouest-France : « Quatre personnes d'une même famille… Toulouse » (0,83) | R09_doublon_approche |
| 5 | Même dépêche dans trois titres | 20 Minutes, La Dépêche, Ouest-France : « L'ambassadeur russe aux États-Unis… est mort » (0,88) | R09_doublon_approche |
| 6 | Dates au format RFC 822 non normalisées | items du 21/10 : `Wed, 21 Oct 2026 06:43:45 +0000` | normalisation `date_utc` |
| 7 | Extraits trop longs (jusqu'à 500 caractères) | 77 extraits de plus de 280 caractères | normalisation `borner_extrait` |
| 8 | Balises HTML dans les extraits | `content:encoded` d'Ouest-France | normalisation `retirer_html` |
| 9 | Entités HTML | `&#8217;`, `&eacute;` | normalisation `decoder_entites` |
| 10 | Flux qui refusent les robots ou renvoient des extraits vides | Sud Ouest, Le Télégramme, Les Échos (403), La Voix du Nord (extraits vides) | désactivés dans `sources.csv` |

Aucun horoscope, programme TV ni publi-reportage n'a encore été vu dans nos flux : les
règles R01 à R03 sont gardées car ces contenus existent chez d'autres titres, et elles
sont testées sur une fixture (`tests/fixtures/pollueurs.json`).

## Normalisation

| Fonction | Ce qu'elle fait |
|---|---|
| `retirer_html` | remplace les balises par une espace |
| `decoder_entites` | `&amp;` → `&`, `&eacute;` → `é` |
| `reparer_encodage` | `Ã©` → `é` (UTF-8 lu à tort en Windows-1252) |
| `normaliser_espaces` | une seule espace entre les mots, pas d'espace au début ni à la fin |
| `date_utc` | RFC 822 ou ISO 8601 → ISO 8601 en UTC ; `None` si illisible |
| `borner_extrait` | 280 caractères au plus, coupé sur une fin de mot, avec « … » |
| `mots_titre` | mots du titre en minuscules sans accents (pour comparer des titres) |
| `jaccard` | similarité entre deux ensembles de mots |

## Règles d'exclusion

Les règles sont appliquées dans cet ordre ; la première qui s'applique donne la raison du
rejet. Les motifs et seuils sont en tête de `regles.py`.

| Règle | Ce qu'elle écarte | Pourquoi | Exemple |
|---|---|---|---|
| `R01_publi` | publi-reportages, contenus sponsorisés ou partenaires, bons plans, codes promo | ce n'est pas de l'information | « PUBLI-REPORTAGE. Les meilleures cuisines de la région » |
| `R02_horoscope` | horoscope, astrologie | contenu récréatif | « Horoscope du jeudi 12 novembre » |
| `R03_programme_tv` | programmes télé, « que regarder ce soir » | contenu de service, pas un sujet | « Programme TV : que regarder ce soir à la télé ? » |
| `R04_jeux` | jeux-concours, « à gagner », mots croisés, sudoku, résultats du loto | promotion ou récréatif | « ICI relance son grand jeu… à gagner » |
| `R05_titre_vide` | titre de moins de 10 caractères | illisible seul dans une édition | « Brest » |
| `R06_date_invalide` | date absente, illisible, ou plus de 15 min dans le futur | casse le filtre « moins de 24 h » | date au 13/11 collectée le 11/11 |
| `R07_encodage` | encodage encore cassé après réparation (`Ã©`, `â€`, `�`) | texte illisible | « Ã‰lection : Ã  Rennes » |
| `R08_doublon_exact` | même titre (casse, accents, ponctuation ignorés) qu'un article gardé depuis moins de 48 h | dépêche reprise à l'identique | même titre chez Le Figaro et 20 Minutes |
| `R09_doublon_approche` | titre à Jaccard ≥ 0,8 d'un article gardé depuis moins de 48 h | dépêche reprise à deux mots près | « Partis politiques (invités) à Matignon… » |

Les articles les plus anciens sont traités en premier : c'est la première publication
d'une dépêche qui est gardée, les reprises sont rejetées avec, dans `detail`, la source
et le début du titre de l'article gardé.

Ce que les règles ne font **pas** : écarter le sport, la culture ou la météo. Ce sont
des sujets légitimes d'une édition. « Loto : il découvre qu'il a gagné le jackpot » est un
fait divers et passe ; seuls les « résultats du loto » sont écartés.

## Contrôles de qualité

Ils vérifient des faits sur les données réelles, après chaque passage (tâche
`controles_qualite`). La CI, elle, teste le code des règles sur des fixtures.

| Contrôle | Fait vérifié | Seuil |
|---|---|---|
| `C01_aucune_date_future` | aucun article propre daté de plus de 15 min dans le futur | 0 |
| `C02_aucun_titre_vide` | aucun article propre sans titre ou sans lien | 0 |
| `C03_extrait_court` | aucun extrait de plus de 280 caractères (conformité) | 0 |
| `C04_taux_rejet_max` | taux de rejet du jour par source (sources d'au moins 10 items) | ≤ 80 % |
| `C05_fraicheur_collecte` | chaque source active a réussi une collecte depuis moins de 2 h | 0 source en retard |
| `C06_aucune_source_en_sommeil` | aucune source mise en sommeil après 3 échecs | 0 |

**Pourquoi des assertions écrites à la main plutôt qu'un outil dédié** (Great Expectations,
Soda) : six requêtes SQL suffisent, elles se lisent sans connaître un outil de plus, et
n'ajoutent ni dépendance lourde ni configuration à maintenir. On changera d'avis si le
nombre de contrôles dépasse la vingtaine.

**Métriques** : chaque résultat est enregistré dans la table `mesures_qualite` et exporté
au format Prometheus dans `data/metriques.prom` (`gazette_controle_ok`,
`gazette_controle_valeur`, `gazette_nettoyage_items`, `gazette_rejets_par_regle`), prêt
pour le TD 8. Un contrôle en échec met aussi la tâche Airflow en rouge.

**Alerte** : un message part sur le salon Discord de l'équipe (webhook dans la variable
`GAZETTE_ALERT_WEBHOOK`, fichier `.env` non versionné) quand un contrôle **passe** en
échec, et un second quand il redevient bon. Pas de message répété toutes les 30 minutes.
Pour tester le canal : `python -m gazette.controles --tester-alerte`.

## Journal des ajustements

À compléter après lecture du rapport trois matins de suite : date, règle, changement,
raison.

| Date | Règle | Changement | Pourquoi |
|---|---|---|---|
| 2026-11-11 | R04_jeux | « résultats du loto » seulement, pas « loto » seul | « Loto : il découvre qu'il a gagné le jackpot » est un fait divers |
| 2026-11-11 | R09_doublon_approche | seuil fixé à 0,8 | à 0,7, « … situation du mardi 10 » et « … du mercredi 11 » (La Croix, deux jours différents) étaient fusionnés à tort (0,76) |
