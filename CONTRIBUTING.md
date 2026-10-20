# Contribuer

## Branches

- `main` reste toujours dans un état construisible et testable.
- Une branche courte est créée par sujet, par exemple `feat/rss-parser` ou `fix/date-filter`.
- Toute fusion passe par une revue, même rapide.

## Commits

Utiliser un préfixe explicite : `feat:`, `fix:`, `test:`, `docs:`, `ci:` ou `chore:`. Un commit doit rester focalisé sur une intention.

## Avant une demande de fusion

```powershell
bin\test.ps1
python -m compileall -q src tests
```

La CI exécute aussi Ruff, les tests et la construction de l'image Docker. Les fixtures sont préférées aux appels réseau dans les tests.

## Sources presse

Toute nouvelle source doit être ajoutée à `sources.csv` avec son type, son accès, son format et ses conditions. Ne pas ajouter de scraping HTML ou de texte intégral sans décision documentée dans `docs/cadrage.md`.
