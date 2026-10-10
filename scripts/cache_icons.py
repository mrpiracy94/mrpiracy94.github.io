#!/usr/bin/env python3
"""Mirror original published app artwork into a *disposable* GitHub Pages build.

Remote image links may be unavailable or blocked in embedded Chromium/webviews.
Only allowlisted image sources are fetched, with strict size/type checks.
Never grant installation/security approval, or manufacture an app entry.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_BYTES = 2_000_000
PREFIX = "io.github.mrpiracy94."
REMOTE_CDN = re.compile(r"^/gh/walkxcode/dashboard-icons/(?:png|svg)/[A-Za-z0-9._-]+\.(?:png|svg)$")
REMOTE_RAW = re.compile(
    r"^/(?:selfhst/icons|homarr-labs/dashboard-icons|linuxserver/docker-templates|"
    r"dosbox-staging/dosbox-staging|luanti-org/luanti|selkies-project/sealskin)"
    r"/[0-9a-f]{40}/[A-Za-z0-9._/-]+\.(?:png|svg|webp|gif)$")
REMOTE_STORE = re.compile(r"^/mrpiracy94/MrStore/main/Apps/[a-z0-9._-]+/icon\.svg$")
REMOTE_SEEDIT = re.compile(r"^/assets/img/icons/software/[A-Za-z0-9._-]+\.(?:png|webp)$")
REMOTE_APP = re.compile(r"^/MrStore/apps/io\.github\.mrpiracy94\.[a-z0-9._-]+/assets/[A-Za-z0-9._/-]+\.(?:png|jpg|jpeg|webp|svg|gif)$")
LOCAL_APP = re.compile(r"^/apps/io\.github\.mrpiracy94\.[a-z0-9._-]+/assets/[A-Za-z0-9._/-]+\.(?:png|jpg|jpeg|webp|svg|gif)$")


def normalize_url(raw: str) -> str | None:
    if not isinstance(raw, str):
        return None
    if ".." in raw or any(char in raw for char in ("\r", "\n", "\\", "\0")):
        return None
    if LOCAL_APP.fullmatch(raw):
        return "https://mrpiracy94.github.io/MrStore" + raw
    if any(char in raw for char in ("\r", "\n", "\\", "\0")):
        return None
    try:
        uri = urlsplit(raw)
    except ValueError:
        return None
    if (uri.scheme != "https" or uri.username or uri.password or
            uri.port or uri.query or uri.fragment):
        return None
    validators = {
        "cdn.jsdelivr.net": (REMOTE_CDN,),
        "raw.githubusercontent.com": (REMOTE_RAW, REMOTE_STORE),
        "seedit4.me": (REMOTE_SEEDIT,),
        "mrpiracy94.github.io": (REMOTE_APP,),
    }
    if any(pattern.fullmatch(uri.path) for pattern in validators.get(uri.hostname, ())):
        return raw
    return None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


FETCHER = build_opener(NoRedirect)


def identify_image(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "webp"
    if content[:128].lstrip().startswith((b"<svg", b"<?xml")):
        head = content.lower()
        if any(token in head for token in (
                b"<script", b"onload=", b"onerror=", b"javascript:",
                b"<foreignobject", b"<!entity", b"<!doctype", b"xlink:href=")):
            return None
        if b"<svg" in head:
            return "svg"
    return None


def fetch(url: str) -> tuple[bytes, str]:
    trusted = normalize_url(url)
    if not trusted:
        raise ValueError("Untrusted image URL")
    request = Request(trusted, headers={"User-Agent": "MrStore-Icon-Cache/1.0",
                                        "Accept": "image/png,image/webp,image/svg+xml,image/*"})
    with FETCHER.open(request, timeout=12) as response:
        data = response.read(MAX_BYTES + 1)
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Empty or oversized image")
    extension = identify_image(data)
    if not extension:
        raise ValueError("Not a safe raster/vector image")
    return data, extension


def build(site: Path, *, fetcher=fetch, workers: int = 12) -> dict:
    index_path = site / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    apps = index.get("apps")
    if (not isinstance(apps, list) or not apps or
            index.get("app_count") != len(apps)):
        raise ValueError("Refusing to cache an invalid catalog")
    for item in apps:
        if (not isinstance(item, dict) or not isinstance(item.get("id"), str)
                or not item["id"].startswith(PREFIX)):
            raise ValueError("Unexpected app identifier")
    image_dir = site / "assets/catalog-icons"
    image_dir.mkdir(parents=True, exist_ok=True)
    # Deduplicate thumbnail/icon URLs; do NOT follow other internet locations.
    srcs = set()
    for item in apps:
        for name in ("icon", "thumbnail"):
            source = item.get(name)
            if normalize_url(source):
                srcs.add(source)

    def process(source: str):
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:22]
        for ext in ("png", "jpg", "gif", "webp", "svg"):
            candidate = image_dir / (digest + "." + ext)
            if candidate.is_file() and 0 < candidate.stat().st_size <= MAX_BYTES:
                return source, "./assets/catalog-icons/" + candidate.name
        try:
            data, extension = fetcher(normalize_url(source))
            destination = image_dir / (digest + "." + extension)
            destination.write_bytes(data)
            return source, "./assets/catalog-icons/" + destination.name
        except (HTTPError, URLError, ValueError, TimeoutError, OSError):
            return source, None

    resolved = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(process, src) for src in sorted(srcs)]
        for job in as_completed(futures):
            source, local = job.result()
            resolved[source] = local

    with_icons = 0
    with_thumbs = 0
    for item in apps:
        # Preserve provenance for audits; the app approval status is unaffected.
        for name in ("icon", "thumbnail"):
            source = item.get(name)
            local = resolved.get(source)
            if local:
                item[name + "_source"] = source
                item[name] = local
                if name == "icon":
                    with_icons += 1
                else:
                    with_thumbs += 1

    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    report = {
        "schema": 1, "catalog_entries": len(apps),
        "icons_cached": with_icons, "screenshots_cached": with_thumbs,
        "sources_attempted": len(srcs),
        "sources_unavailable": len([x for x in srcs if not resolved.get(x)]),
        "note": "Local artwork improves image reliability, not app compatibility or security.",
    }
    (site / "assets/icon-cache-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Icon cache:", report)
    # A storefront with no usable artwork is a failed release, not a success.
    if with_icons < min(9, len(apps)):
        raise RuntimeError(f"Only {with_icons}/{len(apps)} logos were retrieved")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    args = parser.parse_args()
    build(args.site)


if __name__ == "__main__":
    main()
