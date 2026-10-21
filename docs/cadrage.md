# La Gazette - note de cadrage

## 1. Besoin reformulé

Chaque matin à 7 h, **La Gazette** doit proposer une édition courte des sujets qui font l'actualité dans la presse quotidienne régionale (PQR) et nationale (PQN). L'édition regroupe les articles par thèmes et permet de retrouver la source originale.

Pour chaque item, le système conserve uniquement : le titre, un extrait court fourni par le flux, la date de publication, le nom du média et l'URL canonique. L'article complet reste chez l'éditeur.

## 2. Périmètre

### Inclus

- Collecte de flux RSS publics d'au moins quatre sources PQR et quatre sources PQN.
- Normalisation des entrées et dédoublonnage par URL canonique, puis par empreinte titre/source.
- Stockage séparé du brut et des données nettoyées.
- Contrôle qualité : champs obligatoires, date valide, URL accessible, fraîcheur et doublons.
- Regroupement par thèmes avec une taxonomie explicite et révisable.
- Génération d'une édition horodatée contenant les titres, extraits courts, liens et dates.
- Journaux d'exécution, métriques de volume et alertes de supervision.

### Hors périmètre

- Scraping du texte intégral ou contournement de paywalls, CAPTCHA ou protections techniques.
- Résumé automatique par LLM dans le premier incrément.
- Commentaires, comptes lecteurs, personnalisation ou profilage.
- Application web riche et infrastructure de production managée : elles seront traitées dans les TD ultérieurs.

## 3. Contraintes et règles de conformité

- Édition disponible à 7 h ; seules les publications de moins de 24 h sont éligibles.
- Budget nul au stade du projet : développement local et composants open source.
- Aucune donnée personnelle collectée.
- Respect des CGU, du fichier `robots.txt`, des limites de débit et des droits des éditeurs.
- Les sources dont les flux sont réservés à un usage personnel ou soumis à autorisation restent au registre pour étude, mais leur connecteur est désactivé tant que l'autorisation n'est pas obtenue.
- Pas de republication d'article : le produit est un index de veille avec lien vers la source.
- Chaque collecte doit être idempotente et rejouable sans créer de doublons.

## 4. Architecture et flux retenus

Le schéma détaillé est dans [`architecture.md`](architecture.md). La chaîne est découpée en six boîtes :

1. **Collecte des flux** : un ordonnanceur déclenche les connecteurs RSS et applique un débit prudent par domaine.
2. **Stockage brut** : conservation des réponses brutes horodatées pour audit et rejeu.
3. **Nettoyage / contrôle qualité** : validation du schéma, dates, URL, langue, fraîcheur et doublons.
4. **Regroupement thématique** : règles déterministes dans un premier temps, avec une taxonomie versionnée.
5. **Livraison de l'édition** : génération d'un Markdown/JSON daté, limité aux champs autorisés.
6. **Supervision** : logs structurés, compteurs, durée, erreurs par source et alerte si le SLA de 7 h est menacé.

### Stack retenue

- Python pour les connecteurs, la validation et les tests.
- RSS/HTTP avec `requests` ou `httpx`, parseur XML standard ou `feedparser`.
- JSON Lines pour le brut et les échanges ; SQLite en local pour l'index dédoublonné.
- Docker Compose pour reproduire l'environnement à partir du TD2.
- GitHub Actions ou GitLab CI pour lint, tests et construction d'image.
- Markdown et JSON pour les éditions ; aucun stockage du texte intégral.

## 5. Alternatives écartées

| Alternative                             | Décision             | Justification                                                                            |
| --------------------------------------- | --------------------- | ---------------------------------------------------------------------------------------- |
| Scraping HTML systématique             | Écartée             | Fragile, plus coûteux à maintenir et plus risqué au regard des CGU.                   |
| API commerciales ou agrégateur payant  | Écartée pour le MVP | Incompatible avec le budget nul et crée une dépendance externe.                        |
| Recherche plein texte dans les articles | Écartée             | Nécessiterait de conserver du contenu que le cadrage exclut.                            |
| LLM pour résumer dès le TD1           | Reportée             | La priorité est la robustesse de collecte, la traçabilité et la reproductibilité.    |
| Kubernetes dès le départ              | Écartée             | Surdimensionné pour une exécution quotidienne locale ; Docker Compose suffit au socle. |

## 6. Risques et parades

| Risque                                 | Impact                | Parade                                                                               |
| -------------------------------------- | --------------------- | ------------------------------------------------------------------------------------ |
| Flux indisponible ou modifié          | Édition incomplète  | Timeout, retry borné, statut par source, alerte et conservation du dernier succès. |
| Doublons entre flux                    | Édition bruitée     | URL canonique puis empreinte normalisée titre/source/date.                          |
| Date absente ou ambiguë               | Mauvais filtrage 24 h | Rejeter l'entrée et journaliser la cause ; ne jamais inventer la date.              |
| Changement de conditions d'utilisation | Risque juridique      | Revue périodique des CGU/robots et arrêt du connecteur en cas de doute.            |
| Retard de traitement                   | SLA 7 h manqué       | Mesure de durée, seuil d'alerte et traitement parallèle limité par domaine.       |
| Mauvaise catégorisation               | Édition peu lisible  | Taxonomie versionnée, règles testées et revue manuelle des cas limites.           |

## 7. Rôles de l'équipe

- **Référent produit / cadrage** : périmètre, règles éditoriales et validation de l'édition.
- **Référent collecte** : connecteurs, respect des limites d'accès et registre des sources.
- **Référent qualité / données** : schéma, dédoublonnage, tests et fixtures.
- **Référent plateforme** : conteneurs, exécution planifiée, CI et supervision.

Les responsabilités sont collectives : toute modification de source, de schéma ou de taxonomie est revue et documentée dans le dépôt.

## 8. Critères d'acceptation du TD1

- `sources.csv` contient au moins 4 PQR et 4 PQN avec accès, format et conditions documentés.
- Le besoin, le périmètre, les contraintes, les choix et les risques sont explicités dans cette note.
- Le schéma montre les six étapes, les données qui circulent et l'emplacement d'exécution.
- Le contenu respecte la règle « titre, extrait, lien, date » et ne prévoit aucune collecte de texte intégral.
