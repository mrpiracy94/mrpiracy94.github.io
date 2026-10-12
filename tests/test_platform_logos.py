"""Regressão: apenas a marca ZimaOS, com ícones UI locais sem scripts externos."""
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PLATFORM_ASSETS = ROOT / "assets" / "platforms"
ICONS = ROOT / "assets" / "ui-icons.svg"


class PlatformParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.images = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "div" and "platform-grid" in data.get("class", "").split():
            self.depth = 1
        elif self.depth:
            if tag == "div":
                self.depth += 1
            elif tag == "img":
                self.images.append(data)

    def handle_endtag(self, tag):
        if tag == "div" and self.depth:
            self.depth -= 1


class PlatformLogoTests(unittest.TestCase):
    def test_zimaos_is_only_displayed_platform(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        parser = PlatformParser()
        parser.feed(html)
        self.assertEqual(len(parser.images), 1)
        self.assertEqual(parser.images[0]["src"], "./assets/platforms/zimaos.svg")
        self.assertEqual(parser.images[0].get("alt"), "")
        self.assertIn("<strong>ZimaOS</strong>", html)
        self.assertIn("ZIMAOS APP STORE V2", html)
        self.assertIn("suporte em dispositivo", html.lower())
        self.assertEqual([p.name for p in PLATFORM_ASSETS.glob("*.svg")],
                         ["zimaos.svg"])
        ET.parse(PLATFORM_ASSETS / "zimaos.svg")
        # Outros sistemas deixam de ter imagens/links na secção de plataformas.
        for text in ("Integração planeada", "CasaOS", "UmbrelOS", "Homeio",
                     "Runtipi", "Olares", "HomeDock OS"):
            self.assertNotIn(text, html)

    def test_svg_ui_sprite_is_local_and_safe(self):
        raw = ICONS.read_text(encoding="utf-8")
        root = ET.fromstring(raw)
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        symbols = [x.get("id") for x in root if x.tag.endswith("symbol")]
        self.assertEqual(len(symbols), len(set(symbols)))
        for required in ("grid", "house", "code", "play-square", "shapes",
                         "tag", "search", "star", "menu", "layers", "circle-alert",
                         "arrow-right", "copy", "chevron-down", "shield-check"):
            self.assertIn(required, symbols)
        for bad in ("<script", "onload=", "onerror=", "javascript:", "<foreignobject",
                    "<image", "xlink:href=", "<!doctype"):
            self.assertNotIn(bad, raw.lower())
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('./assets/ui-icons.svg#search', html)
        self.assertIn('./assets/ui-icons.svg#star', html)
        self.assertIn('./assets/ui-icons.svg#menu', html)
        js = (ROOT / "assets/site.js").read_text(encoding="utf-8")
        self.assertIn("createElementNS", js)
        self.assertIn("CATEGORY_ICONS", js)
        self.assertIn('uiIcon("star"', js)
        self.assertNotIn("innerHTML", js)

    def test_static_builder_copies_only_required_assets(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            from sync_catalog import FILES
        finally:
            sys.path.pop(0)
        self.assertIn("assets/ui-icons.svg", FILES)
        self.assertIn("assets/platforms/zimaos.svg", FILES)
        self.assertFalse(any("assets/platforms/" in p and not p.endswith("zimaos.svg")
                             for p in FILES))
        style = (ROOT / "assets" / "site.css").read_text(encoding="utf-8")
        self.assertIn(".ui-icon{", style)
        self.assertIn(".platform-grid.platform-grid-single", style)


if __name__ == "__main__":
    unittest.main()
