# Stratégie CI/CD

La CI est exécutée par GitHub Actions à chaque pull request et à chaque push sur `main`.
Le job de vérification installe Python 3.12, exécute Ruff, les tests unitaires et la compilation.
Une modification qui échoue à l’une de ces étapes doit être corrigée avant la fusion.
Après une vérification réussie sur `main`, le job d’image construit le [Dockerfile](../Dockerfile).
L’image est publiée dans GitHub Container Registry (`ghcr.io`) avec un tag horodaté et le SHA du commit.
Le tag `latest` pointe également vers la dernière image construite depuis `main`.
Les pull requests vérifient le code mais ne publient pas d’image.
La CI ne réalise aucun déploiement automatique : l’ordonnancement et le déploiement seront traités dans les TD suivants.
Les tests utilisent les fixtures locales afin de rester reproductibles et de ne pas dépendre des flux de presse.
En local, les commandes de référence sont `bin/test.ps1` et `docker compose up --build`.
