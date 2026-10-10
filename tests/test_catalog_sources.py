"""Keep every MrStore manifest visible without falsifying security evidence."""
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sync_catalog import source_app_slugs, valid_upstream_release


class CompleteCatalogTests(unittest.TestCase):
    def test_discovers_every_manifest_without_curated_shortlist(self):
        data = {"truncated": False, "tree": [
            {"type": "blob", "path": "Apps/plex/docker-compose.yml"},
            {"type": "blob", "path": "Apps/immich/docker-compose.yml"},
            {"type": "blob", "path": "Docs/README.md"},
        ]}
        self.assertEqual(source_app_slugs(data), ["immich", "plex"])

    def test_rejects_truncated_or_missing_trees(self):
        for data in ({}, {"truncated": True, "tree": []},
                     {"truncated": False, "tree": []}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                source_app_slugs(data)

    def test_editorial_release_is_not_certification(self):
        index = {"version": 2, "app_count": 1, "apps": [{
            "id": "io.github.mrpiracy94.plex", "title": "Plex",
            "category": "Media", "architectures": ["amd64"]}]}
        edition = {"approved": ["plex"], "approved_count": 1,
                   "certification": "not_assessed"}
        self.assertFalse(valid_upstream_release(edition, index))
        edition["certification"] = "security_scanned"
        self.assertTrue(valid_upstream_release(edition, index))


if __name__ == "__main__":
    unittest.main()
