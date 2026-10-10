#!/usr/bin/env python3
"""Build the MrStore discovery site from public, explicit upstream sources.

No legacy application is ever implicitly treated as audited or certified.
The upstream candidate shortlist is authoritative for the pilot website.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import yaml
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_RAW = "https://raw.githubusercontent.com/mrpiracy94/MrStore"
PREFIX = "io.github.mrpiracy94."
FILES = ("index.html", "assets/site.css", "assets/site.js", "assets/mark.svg")


def get_json(url: str, *, allow_missing: bool = False):
    request = Request(url, headers={"User-Agent": "mrstore-pages-sync/1.0",
                                    "Accept": "application/json"})
    try:
        with urlopen(request, timeout=35) as response:
            body = response.read(4_000_001)
            if len(body) > 4_000_000:
                raise ValueError("Upstream JSON exceeds size limit: " + url)
    except HTTPError as err:
        if allow_missing and err.code == 404:
            return None
        raise
    return json.loads(body.decode("utf-8"))


def valid_index(data) -> bool:
    if not isinstance(data, dict) or data.get("version") != 2:
        return False
    apps = data.get("apps")
    if not isinstance(apps, list) or type(data.get("app_count")) is not int:
        return False
    if len(apps) != data["app_count"] or len(apps) != len({
            app.get("id") for app in apps if isinstance(app, dict)}):
        return False
    return all(
        isinstance(app, dict)
        and isinstance(app.get("id"), str)
        and re.fullmatch(r"io\.github\.mrpiracy94\.[a-z0-9._-]+", app["id"])
        and isinstance(app.get("title"), str)
        and isinstance(app.get("category"), str)
        and isinstance(app.get("architectures"), list)
        for app in apps
    )


def valid_upstream_release(release, index) -> bool:
    if not valid_index(index) or not isinstance(release, dict):
        return False
    approved = release.get("approved")
    count = release.get("approved_count")
    if not isinstance(approved, list) or type(count) is not int or count < 1:
        return False
    if len(approved) != count or count != index["app_count"]:
        return False
    expected = {PREFIX + slug for slug in approved if isinstance(slug, str)}
    return len(expected) == count and expected == {app["id"] for app in index["apps"]}


def build_selection(featured, published, source_release):
    if not isinstance(featured, dict) or not isinstance(featured.get("apps"), list):
        raise ValueError("Missing curated upstream shortlist")
    slugs = featured["apps"]
    if not slugs or len(slugs) != len(set(slugs)) or not all(
            isinstance(s, str) and re.fullmatch(r"[a-z0-9._-]+", s) for s in slugs):
        raise ValueError("Invalid or duplicate curated slugs")
    if not valid_index(published):
        raise ValueError("Invalid upstream public index")

    lookup = {a["id"]: a for a in published["apps"]}
    available = [lookup.get(PREFIX + slug) for slug in slugs]
    # The main catalog can be ahead of gh-pages. Confirm each missing app
    # exists in the upstream Git tree before showing an editorial-only entry.
    if any(app is None for app in available):
        tree = get_json("https://api.github.com/repos/mrpiracy94/MrStore/git/trees/main?recursive=1")
        paths = {entry.get("path") for entry in tree.get("tree", []) if entry.get("type") == "blob"}
        for i, slug in enumerate(slugs):
            if available[i] is not None:
                continue
            if "Apps/" + slug + "/docker-compose.yml" not in paths:
                raise ValueError("Missing upstream application manifest: " + slug)
            manifest_url = UPSTREAM_RAW + "/main/Apps/" + slug + "/docker-compose.yml"
            request = Request(manifest_url, headers={"User-Agent": "mrstore-pages-sync/1.0"})
            with urlopen(request, timeout=35) as response:
                manifest = yaml.safe_load(response.read(500_001).decode("utf-8"))
            meta = manifest.get("x-casaos", {}) or {}
            def english(value, default):
                return value.get("en_US", next(iter(value.values()), default)) if isinstance(value, dict) else default
            icon = meta.get("icon", "")
            thumbnail = meta.get("thumbnail", "")
            available[i] = {
                "id": PREFIX + slug,
                "title": english(meta.get("title"), slug.replace("-", " ").title()),
                "tagline": english(meta.get("tagline"), "Aplicação selecionada para a MrStore"),
                "category": meta.get("category", "Others"),
                "categories": [str(meta.get("category", "Others")).lower()],
                "architectures": meta.get("architectures", []),
                "version": str(meta.get("version", "")),
                "developer": meta.get("developer", "Comunidade"),
                "icon": icon if isinstance(icon, str) else "",
                "thumbnail": thumbnail if isinstance(thumbnail, str) else "",
                "editorial_only": True,
            }
    if not available:
        raise ValueError("No editorial applications found upstream")

    verified = valid_upstream_release(source_release, published) and not any(
        app.get("editorial_only") for app in available)
    if verified:
        # Published approval is authoritative; never promote an absent slug.
        released = {PREFIX + slug for slug in source_release["approved"]}
        apps = [app for app in available if app["id"] in released]
        approved = [app["id"][len(PREFIX):] for app in apps]
        status = {
            "schema": 1, "status": "approved_subset_of_upstream_release",
            "approved": approved, "approved_count": len(approved),
            "candidate_count": len(slugs), "candidates": slugs,
            "source": "https://github.com/mrpiracy94/MrStore/tree/gh-pages",
            "notice": "Subconjunto da seleção editorial incluído no relatório aprovado de origem. A certificação nativa em cada sistema exige testes independentes."
        }
    else:
        apps = available
        status = {
            "schema": 1, "status": "editorial_pilot_unverified",
            "approved": [], "approved_count": 0,
            "candidate_count": len(slugs), "candidates": slugs,
            "source": "https://github.com/mrpiracy94/MrStore",
            "notice": "Seleção editorial piloto sem relatório completo de aprovação. Não representa certificação de instalação ou segurança."
        }

    result = {
        "version": 2, "updated_at": published.get("updated_at"),
        "app_count": len(apps),
        "base_url": "https://mrpiracy94.github.io/MrStore",
        "catalogue_status": status["status"],
        "apps": apps,
    }
    if not valid_index(result):
        raise ValueError("Refusing to publish invalid or empty source data")
    return result, status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "public")
    args = parser.parse_args()
    featured = get_json(UPSTREAM_RAW + "/main/data/featured-apps.json")
    published = get_json(UPSTREAM_RAW + "/gh-pages/index.json")
    approved = get_json(UPSTREAM_RAW + "/gh-pages/release-status.json",
                        allow_missing=True)
    index, status = build_selection(featured, published, approved)

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    for relative in FILES:
        origin = ROOT / relative
        destination = output / relative
        if not origin.is_file():
            raise FileNotFoundError(origin)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, destination)
    (output / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "release-status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / ".nojekyll").touch()
    print(f"MrStore: {index['app_count']} entradas | {status['status']}")
    print("Informational discovery only. No installation/certification claimed.")


if __name__ == "__main__":
    main()
