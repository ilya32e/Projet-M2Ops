import unittest
from pathlib import Path

from gazette.sources import find_source, load_sources


class SourcesTest(unittest.TestCase):
    def test_registry_contains_four_pqr_and_four_pqn(self) -> None:
        sources = load_sources(Path("sources.csv"))
        self.assertEqual(len(sources), 8)
        self.assertEqual(sum(source.source_type == "PQR" for source in sources), 4)
        self.assertEqual(sum(source.source_type == "PQN" for source in sources), 4)

    def test_find_source_is_case_insensitive(self) -> None:
        source = find_source(Path("sources.csv"), "le monde")
        self.assertEqual(source.name, "Le Monde")


if __name__ == "__main__":
    unittest.main()
