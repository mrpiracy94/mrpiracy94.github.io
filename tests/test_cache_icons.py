"""Offline security tests for the Pages icon mirror."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from cache_icons import normalize_url, identify_image, build

ICON = "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/plex.png"
PNG = b"\x89PNG\r\n\x1a\n" + b"fictional-test-payload"


class CacheIconTests(unittest.TestCase):
    def test_only_allowlisted_sources(self):
        self.assertEqual(normalize_url(ICON), ICON)
        self.assertEqual(
            normalize_url("/apps/io.github.mrpiracy94.plex/assets/icon.png"),
            "https://mrpiracy94.github.io/MrStore/apps/io.github.mrpiracy94.plex/assets/icon.png")
        for src in (
            "http://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/plex.png",
            "https://evil.example/image.png",
            "https://cdn.jsdelivr.net.evil.example/gh/walkxcode/dashboard-icons/png/plex.png",
            "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/../../passwd.png",
            "/apps/io.github.mrpiracy94.plex/assets/../../private.png",
            "https://localhost/admin", "file:///etc/shadow",
            "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/plex.png?token=abc",
        ):
            with self.subTest(url=src):
                self.assertIsNone(normalize_url(src))

    def test_image_magic_and_reject_executables(self):
        self.assertEqual(identify_image(PNG), "png")
        self.assertIsNone(identify_image(b"<html>not a logo</html>"))
        self.assertIsNone(identify_image(b"<svg onload='alert(1)'></svg>"))

    def test_mirror_keeps_app_security_status_unchanged(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            catalog = {
                "version": 2, "app_count": 2, "apps": [
                    {"id": "io.github.mrpiracy94.plex", "icon": ICON, "thumbnail": ICON},
                    {"id": "io.github.mrpiracy94.jellyfin", "icon": ICON, "thumbnail": ICON},
                ],
            }
            (root / "index.json").write_text(json.dumps(catalog))
            seen = []
            def stub(url):
                seen.append(url)
                return PNG, "png"
            report = build(root, fetcher=stub, workers=2)
            self.assertEqual(report["icons_cached"], 2)
            self.assertEqual(report["sources_attempted"], 1)
            self.assertEqual(seen, [ICON])
            after = json.loads((root / "index.json").read_text())
            self.assertEqual(after["version"], 2)
            self.assertEqual(after["app_count"], 2)
            self.assertEqual(after["apps"][0]["icon_source"], ICON)
            logo = after["apps"][0]["icon"]
            self.assertTrue(logo.startswith("./assets/catalog-icons/"))
            self.assertTrue((root / logo).is_file())
            self.assertEqual(after["apps"][1]["icon"], logo)


if __name__ == "__main__":
    unittest.main()
