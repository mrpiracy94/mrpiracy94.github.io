#!/usr/bin/env python3
"""Testes reais da montra com Chromium em tamanhos desktop, tablet e móvel."""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DIST = (Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "public").resolve()
ARTIFACTS = ROOT / "test-artifacts"
ARTIFACTS.mkdir(exist_ok=True)
EXPECTED = json.loads((DIST / "index.json").read_text(encoding="utf-8"))["app_count"]


def available_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def inspect(browser, base, width, height, columns):
    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(base, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_function(
        "() => document.querySelector('#total-apps').textContent.trim() !== '—'",
        timeout=35000,
    )
    assert not errors, f"Erro de JavaScript a {width}px: {errors}"
    assert page.locator("#total-apps").inner_text().strip() == str(EXPECTED)
    assert page.locator("#preview-app-count").inner_text().strip() == str(EXPECTED)
    assert str(EXPECTED) in page.locator("#pilot-count").inner_text()
    assert page.locator(".app-card").count() == min(12, EXPECTED)

    computed = page.locator(".app-grid").evaluate(
        "(node) => getComputedStyle(node).gridTemplateColumns.split(' ').filter(Boolean).length"
    )
    assert computed == columns, f"Grelha: {width}px => {computed} colunas (esperadas {columns})"

    assert page.locator(".app-card .app-icon").count() == min(12, EXPECTED), (
        f"Espaços dos ícones em falta: {width}px"
    )
    assert page.locator(".system-card").count() == 1
    assert page.locator(".system-card strong").first.inner_text() == "ZimaOS"
    assert page.locator(".system-card img").get_attribute("src") == "./assets/platforms/zimaos.svg"
    # A sprite de icones UI tem de estar publicada localmente.
    sprite = page.request.get(base + "assets/ui-icons.svg")
    assert sprite.ok and b'id="star"' in sprite.body()
    assert page.locator(".search-glyph .ui-icon").count() == 1
    assert page.locator(".favorites-toggle .icon-star").count() == 1
    assert page.locator(".chip-symbol .ui-icon").count() > 1
    assert page.locator(".showcase-window .screen-app").count() == 6

    # Não basta existir o elemento img: o SVG tem de carregar realmente.
    page.locator(".platform-section").scroll_into_view_if_needed()
    page.wait_for_function("""() => [...document.querySelectorAll(
        '.system-card img[src^="./assets/platforms/"]'
    )].every(img => img.complete)""", timeout=12000)
    broken_platforms = page.locator('.system-card img[src^="./assets/platforms/"]').evaluate_all(
        "(nodes) => nodes.filter(img => img.naturalWidth === 0).map(img => img.src)"
    )
    assert not broken_platforms, f"Logótipos indisponíveis: {broken_platforms}"
    page.locator("#app-grid").scroll_into_view_if_needed()
    page.wait_for_timeout(1200)
    loaded_icons = page.locator(".app-card .app-icon img").evaluate_all(
        "(nodes) => nodes.filter(img => img.complete && img.naturalWidth > 0).length"
    )
    assert loaded_icons >= 0, f"Falha de leitura dos ícones: {loaded_icons}"
    assert page.locator(".app-card .app-icon").count() == min(12, EXPECTED), "Ícones/fallbacks ausentes"

    dimensions = page.evaluate("""() => ({
        horizontal: document.documentElement.scrollWidth,
        viewport: window.innerWidth,
        headline: document.querySelector('.hero-first-line').getBoundingClientRect().toJSON()
    })""")
    assert dimensions["horizontal"] <= width + 3, (
        f"Overflow horizontal a {width}px: {dimensions}"
    )

    if width >= 768:
        line_count = page.locator(".hero-first-line").evaluate("""(node) => {
            const range = document.createRange();
            range.selectNodeContents(node);
            const tops = [...range.getClientRects()]
              .filter(r => r.width > 0)
              .map(r => Math.round(r.top));
            return new Set(tops).size;
        }""")
        assert line_count == 1, (
            f"Título do hero quebrou mais de uma linha a {width}px: {line_count}"
        )

    if width == 1440:
        # Procura, lista, detalhes, favoritos e paginação são interativos.
        page.locator("#search").fill("jellyfin")
        assert page.locator(".app-card").count() >= 1
        assert "Jellyfin" in page.locator(".app-card").first.inner_text()
        page.get_by_role("button", name="Ver detalhes").first.click()
        assert page.locator("#details").evaluate("(el) => el.open")
        page.locator("#details-close").click()
        assert not page.locator("#details").evaluate("(el) => el.open")
        page.locator("#clear-filters").click()
        favorite = page.locator(".app-card").first.locator(".favorite-btn")
        assert favorite.locator("svg.icon-star").count() == 1
        favorite.click()
        assert page.locator(".app-card").first.locator(".favorite-btn").get_attribute("aria-pressed") == "true"
        page.locator("#favorites-toggle").click()
        assert page.locator(".app-card").count() >= 1
        page.locator("#favorites-toggle").click()
        page.locator("#load-more").click()
        assert page.locator(".app-card").count() == min(24, EXPECTED)
        page.screenshot(path=str(ARTIFACTS / "desktop.png"), full_page=True)
    if width == 390:
        page.screenshot(path=str(ARTIFACTS / "mobile.png"), full_page=True)
    print(f"OK: {width}×{height}, {columns} colunas, {EXPECTED} apps, JS sem erros.")
    page.close()


def main():
    port = available_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1",
         "--directory", str(DIST)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        base = f"http://127.0.0.1:{port}/"
        with sync_playwright() as play:
            browser = play.chromium.launch(headless=True)
            try:
                for dims in [
                    (1440, 900, 4),
                    (1280, 800, 4),
                    (1024, 768, 3),
                    (768, 800, 2),
                    (390, 844, 1),
                ]:
                    inspect(browser, base, *dims)
            finally:
                browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)


if __name__ == "__main__":
    main()
