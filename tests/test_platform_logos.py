"""Regressão: os 11 símbolos de plataforma devem ser logótipos, não emojis."""
from html.parser import HTMLParser
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BRANDS = ("umbrel-os", "casaos", "zimaos", "portainer", "cosmos",
          "dockge", "runtipi", "docker", "homedock-os", "olares")


class PlatformParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.images = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div" and "platform-grid" in attrs.get("class", "").split():
            self.depth = 1
        elif self.depth:
            if tag == "div":
                self.depth += 1
            elif tag == "img":
                self.images.append(attrs)

    def handle_endtag(self, tag):
        if tag == "div" and self.depth:
            self.depth -= 1


class PlatformLogoTests(unittest.TestCase):
    def test_11_original_platform_icons_and_csp(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        parser = PlatformParser()
        parser.feed(html)
        self.assertEqual(len(parser.images), 11)
        sources = [item["src"] for item in parser.images]
        self.assertEqual(len(set(sources)), 11)
        self.assertTrue(all(item.get("alt") == "" for item in parser.images))
        for slug in BRANDS:
            source = "./assets/platforms/" + slug + ".svg"
            self.assertIn(source, sources)
            asset = ROOT / "assets" / "platforms" / (slug + ".svg")
            self.assertTrue(asset.is_file(), source)
            ET.parse(asset)
            contents = asset.read_text(encoding="utf-8").lower()
            for unsafe in ("<script", "onload=", "onerror=", "javascript:", "<foreignobject"):
                self.assertNotIn(unsafe, contents)
        homeio = [x for x in sources if "/doctor-io/homeio/" in x]
        self.assertEqual(len(homeio), 1)
        self.assertIn("13a40d496e57b8939f5efd2b54bd0ad0a702ca17", homeio[0])
        # CSP continua a restringir imagens a fontes explicitamente aprovadas.
        self.assertIn("https://raw.githubusercontent.com", html)
        self.assertIn("https://cdn.jsdelivr.net", html)
        self.assertIn("https://seedit4.me;", html)

    def test_static_builder_includes_all_platform_assets(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            from sync_catalog import FILES
        finally:
            sys.path.pop(0)
        for name in BRANDS:
            self.assertIn("assets/platforms/" + name + ".svg", FILES)
        style = (ROOT / "assets/site.css").read_text(encoding="utf-8")
        self.assertIn(".system-glyph img{display:block;", style)


if __name__ == "__main__":
    unittest.main()
