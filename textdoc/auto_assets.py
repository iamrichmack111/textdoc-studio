from __future__ import annotations

import json
import re
import time
from pathlib import Path

from .commons import search_public_domain, download_asset


STOP = {
    "about","after","again","against","american","because","before",
    "between","black","could","developed","different","during","from",
    "have","historical","history","into","more","other","over","same",
    "these","they","this","through","under","united","very","were",
    "what","when","where","which","while","with","would","their",
    "traditions","tradition","practices"
}


def concepts_for_scene(scene):
    text = scene["text"]

    words = re.findall(r"[A-Za-z][A-Za-z'-]+", text)

    useful = []

    for word in words:
        w = word.lower().strip("'")

        if len(w) < 4 or w in STOP:
            continue

        if w not in useful:
            useful.append(w)

    # Prefer meaningful proper nouns appearing in the narration.
    proper = re.findall(
        r"\b[A-Z][A-Za-z'-]{3,}\b",
        text
    )

    result = []

    for p in proper:
        if p.lower() not in STOP and p not in result:
            result.append(p)

    for w in useful:
        if w not in [x.lower() for x in result]:
            result.append(w)

    return result[:4]


def make_queries(scene):
    text = scene["text"].lower()
    queries = []

    # Historical/geographic hints improve Commons results.
    if "new orleans" in text:
        queries.append("New Orleans historical")

    if "louisiana" in text:
        queries.append("Louisiana historical")

    if "haiti" in text or "haitian" in text:
        queries.append("Haiti historical")

    if "hoodoo" in text or "rootwork" in text:
        queries.append("African American folk culture historical")

    if "vodou" in text or "voodoo" in text:
        queries.append("Vodou historical")

    if "church" in text or "christian" in text:
        queries.append("African American church historical")

    concepts = concepts_for_scene(scene)

    if concepts:
        queries.append(" ".join(concepts[:3]) + " historical")

    # Preserve order while removing duplicates.
    unique = []

    for q in queries:
        q = q.strip()

        if q and q.lower() not in [x.lower() for x in unique]:
            unique.append(q)

    return unique[:2]


def existing_manifest(path):
    p = Path(path)

    if not p.exists():
        return []

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def acquire_for_documentary(
    scenes,
    picture_root,
    per_scene=1,
    max_downloads=4,
):
    picture_root = Path(picture_root)

    commons_dir = picture_root / "commons"
    commons_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = commons_dir / "manifest.json"
    manifest = existing_manifest(manifest_path)

    image_exts = {".jpg", ".jpeg", ".png", ".webp"}

    cached = [
        p for p in commons_dir.iterdir()
        if p.is_file() and p.suffix.lower() in image_exts
    ]

    print()
    print("==========================================")
    print(" WIKIMEDIA COMMONS")
    print(" Cache-first public-domain acquisition")
    print("==========================================")
    print(f"Cached images: {len(cached)}")

    # A small documentary does not need a unique download for every scene.
    target = min(max_downloads, max(3, min(4, len(scenes))))

    if len(cached) >= target:
        print(
            f"Cache already has {len(cached)} images; "
            "no Wikimedia requests needed."
        )
        print("Manifest:", manifest_path)
        print()
        return commons_dir, manifest

    seen_urls = {
        x.get("original_url") or x.get("url")
        for x in manifest
        if x.get("original_url") or x.get("url")
    }

    # Build a small set of distinct searches for the WHOLE documentary.
    queries = []

    for scene in scenes:
        for q in make_queries(scene):
            key = q.lower()

            if key not in [x.lower() for x in queries]:
                queries.append(q)

    # Never hammer Commons with a search for every scene.
    queries = queries[:4]

    needed = target - len(cached)
    downloaded = 0

    print(f"Target assets: {target}")
    print(f"Need new:      {needed}")
    print(f"Searches max:  {len(queries)}")
    print()

    rate_limited = False

    for query_number, query in enumerate(queries, start=1):
        if downloaded >= needed or rate_limited:
            break

        print(
            f"[commons {query_number}/{len(queries)}] "
            f"{query}"
        )

        try:
            results = search_public_domain(
                query,
                limit=5,
                width=1600,
            )
        except Exception as e:
            if "429" in str(e):
                print("  RATE LIMITED — stopping Commons requests.")
                rate_limited = True
                break

            print("  search failed:", e)
            time.sleep(5)
            continue

        # Separate API searches generously.
        time.sleep(4)

        for item in results:
            identity = (
                item.get("original_url")
                or item.get("url")
            )

            if identity in seen_urls:
                continue

            try:
                prefix = f"auto-{len(cached)+downloaded+1:02d}"

                local = download_asset(
                    item,
                    commons_dir,
                    prefix=prefix,
                    retries=1,
                )

            except Exception as e:
                if "429" in str(e):
                    print(
                        "  RATE LIMITED during download — "
                        "stopping Commons requests."
                    )
                    rate_limited = True
                    break

                print("  download failed:", e)
                continue

            item["query"] = query
            item["local_file"] = str(local)

            manifest.append(item)
            seen_urls.add(identity)

            downloaded += 1

            print("  +", local.name)
            print(
                "    license:",
                item.get("license", "Public domain")
            )

            # One successful download per search is enough.
            time.sleep(5)
            break

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    final_images = [
        p for p in commons_dir.iterdir()
        if p.is_file() and p.suffix.lower() in image_exts
    ]

    print()
    print("Commons acquisition finished.")
    print("Cached images:", len(final_images))
    print("New images:   ", downloaded)

    if rate_limited:
        print(
            "Wikimedia rate limit reached; "
            "continuing with local cached assets."
        )

    print("Manifest:", manifest_path)
    print()

    return commons_dir, manifest
