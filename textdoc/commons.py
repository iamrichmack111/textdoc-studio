from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path
from urllib.error import HTTPError

API = "https://commons.wikimedia.org/w/api.php"

# Wikimedia asks API clients to identify themselves.
UA = "TextDoc/0.4 (local documentary renderer; Wikimedia Commons client)"

def _get(params, retries=4):
    url = API + "?" + urllib.parse.urlencode(params)

    for attempt in range(retries):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)

        except HTTPError as e:
            if e.code != 429 or attempt == retries - 1:
                raise

            wait = 3 * (attempt + 1)
            print(f"  Wikimedia rate limit; waiting {wait}s...")
            time.sleep(wait)

def _plain(v):
    if isinstance(v, dict):
        v = v.get("value", "")

    v = unescape(str(v or ""))
    return re.sub(r"<[^>]+>", "", v).strip()

def _safe_name(title):
    name = title.removeprefix("File:")
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")
    return name[:150] or "asset.jpg"

def search_public_domain(query, limit=12, width=1920):
    data = _get({
        "action": "query",
        "format": "json",
        "formatversion": 2,

        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": limit,

        "prop": "imageinfo",

        # thumburl is the important part.
        "iiprop": "url|mime|size|extmetadata",
        "iiurlwidth": width,
    })

    found = []

    for page in data.get("query", {}).get("pages", []):
        infos = page.get("imageinfo") or []
        if not infos:
            continue

        ii = infos[0]
        meta = ii.get("extmetadata", {})

        mime = ii.get("mime", "")
        copyrighted = _plain(meta.get("Copyrighted")).lower()
        license_name = _plain(meta.get("LicenseShortName"))
        license_lower = license_name.lower()

        is_pd = (
            copyrighted == "false"
            or "public domain" in license_lower
            or license_lower == "cc0"
            or license_lower.startswith("pd-")
        )

        if not is_pd:
            continue

        if mime not in {
            "image/jpeg",
            "image/png",
            "image/webp",
        }:
            continue

        # IMPORTANT:
        # prefer Wikimedia's resized thumbnail, not the giant original.
        download_url = ii.get("thumburl") or ii.get("url")

        if not download_url:
            continue

        title = page.get("title", "")

        found.append({
            "title": title,

            "url": download_url,
            "original_url": ii.get("url", ""),

            "width": ii.get("width"),
            "height": ii.get("height"),

            "thumbwidth": ii.get("thumbwidth"),
            "thumbheight": ii.get("thumbheight"),

            "description": _plain(meta.get("ImageDescription")),
            "artist": _plain(meta.get("Artist")),
            "credit": _plain(meta.get("Credit")),

            "license": license_name,
            "license_url": _plain(meta.get("LicenseUrl")),
            "copyrighted": copyrighted,

            "commons_page":
                "https://commons.wikimedia.org/wiki/" +
                urllib.parse.quote(title.replace(" ", "_")),
        })

    return found

def download_asset(item, output_dir, prefix="commons", retries=5):
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    url = item["url"]

    parsed = urllib.parse.urlparse(url)
    ext = Path(parsed.path).suffix.lower()

    # Wikimedia thumbnails sometimes have odd-looking suffixes.
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"

    stem = Path(_safe_name(item["title"])).stem

    dest = outdir / f"{prefix}-{stem}{ext}"

    # CACHE:
    # don't hit Wikimedia again if we already downloaded it.
    if dest.exists() and dest.stat().st_size > 4096:
        print("  cached:", dest.name)
        return dest

    for attempt in range(retries):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": UA,
                "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()

            if len(data) < 4096:
                raise RuntimeError(
                    f"Downloaded file suspiciously small: {len(data)} bytes"
                )

            dest.write_bytes(data)

            # Be polite to Commons.
            time.sleep(1.0)

            return dest

        except HTTPError as e:
            # Downloads are optional enrichment. If Wikimedia
            # throttles us, fail immediately so documentary
            # rendering can continue with local/graphic fallback.
            #
            # Search and acquisition can retry on a later run;
            # do not hammer the image endpoint repeatedly.
            if e.code == 429:
                retry_after = e.headers.get("Retry-After")

                raise RuntimeError(
                    "WIKIMEDIA_RATE_LIMITED"
                    + (
                        f" retry_after={retry_after}"
                        if retry_after
                        else ""
                    )
                ) from e

            raise

            # Legacy retry code below is unreachable and retained
            # temporarily to minimize this patch.
            retry_after = e.headers.get("Retry-After")

            try:
                wait = int(retry_after)
            except (TypeError, ValueError):
                wait = 5 * (attempt + 1)

            print(
                f"  Wikimedia 429; waiting {wait}s "
                f"(attempt {attempt+1}/{retries})"
            )

            time.sleep(wait)

    raise RuntimeError("Download failed after retries")
