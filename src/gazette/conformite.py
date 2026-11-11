"""Mise en conformité des items bruts déjà collectés.

Avant le 11/11/2026, chaque fichier de articles_bruts/ gardait le flux XML complet
(`payload.feed_xml`), qui contient des noms d'auteurs (dc:creator, author) et des liens
d'images. Cette commande retire ce champ des fichiers existants ; les nouveaux fichiers
ne le contiennent plus. Opération irréversible : seule l'entrée normalisée est gardée.

    python -m gazette.conformite --raw-dir articles_bruts
"""

import argparse
import json
from pathlib import Path


def purger_flux_bruts(raw_dir: Path) -> int:
    """Retire `payload.feed_xml` de chaque fichier brut ; renvoie le nombre de fichiers modifiés."""
    modifies = 0
    for chemin in sorted(raw_dir.glob("*.json")):
        document = json.loads(chemin.read_text(encoding="utf-8"))
        if "feed_xml" in document.get("payload", {}):
            del document["payload"]["feed_xml"]
            chemin.write_text(json.dumps(document, ensure_ascii=False, indent=2),
                              encoding="utf-8")
            modifies += 1
    return modifies


def main() -> int:
    parser = argparse.ArgumentParser(description="Retire le flux XML complet des items bruts")
    parser.add_argument("--raw-dir", type=Path, default=Path("articles_bruts"))
    args = parser.parse_args()
    print(f"{purger_flux_bruts(args.raw_dir)} fichier(s) mis en conformité")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
