from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


ROOT = Path.home() / "textdoc-cli" / "media-pool"
IMAGES = ROOT / "images"
MANIFEST = ROOT / "manifest.json"

EXTS = {".jpg", ".jpeg", ".png", ".webp"}

STOP = {
    "the","and","for","with","from","that","this","into","were",
    "was","are","their","through","during","about","have","has",
    "historical","history","image","images"
}


def load():
    if not MANIFEST.exists():
        return []

    try:
        x = json.loads(MANIFEST.read_text(encoding="utf-8"))
        return x if isinstance(x, list) else []
    except Exception:
        return []


def save(items):
    ROOT.mkdir(parents=True, exist_ok=True)
    IMAGES.mkdir(parents=True, exist_ok=True)

    MANIFEST.write_text(
        json.dumps(items, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def tokens(text):
    return {
        x.lower()
        for x in re.findall(r"[A-Za-z0-9'-]+", text)
        if len(x) >= 4 and x.lower() not in STOP
    }


def import_manifest(manifest_file):
    source = Path(manifest_file).expanduser().resolve()

    if not source.exists():
        raise RuntimeError(f"Missing manifest: {source}")

    data = json.loads(source.read_text(encoding="utf-8"))

    existing = load()

    identities = {
        x.get("original_url") or x.get("url")
        for x in existing
    }

    added = 0

    for item in data:
        identity = item.get("original_url") or item.get("url")

        if identity and identity in identities:
            continue

        local = Path(item.get("local_file", ""))

        if not local.exists():
            # Older manifests may contain a filename relative to themselves.
            candidate = source.parent / local.name
            if candidate.exists():
                local = candidate

        if not local.exists():
            continue

        if local.suffix.lower() not in EXTS:
            continue

        target = IMAGES / local.name

        if target.exists():
            stem = target.stem
            suffix = target.suffix

            n = 2
            while target.exists():
                target = IMAGES / f"{stem}-{n}{suffix}"
                n += 1

        shutil.copy2(local, target)

        record = dict(item)
        record["pool_file"] = str(target)

        searchable = " ".join([
            str(item.get("title", "")),
            str(item.get("description", "")),
            str(item.get("query", "")),
            str(item.get("text", "")),
            target.stem.replace("-", " "),
        ])

        record["keywords"] = sorted(tokens(searchable))

        existing.append(record)

        if identity:
            identities.add(identity)

        added += 1

    save(existing)

    print(f"Imported: {added}")
    print(f"Pool total: {len(existing)}")
    print(MANIFEST)


def search(query, limit=8):
    wanted = tokens(query)

    ranked = []

    for item in load():
        searchable = set(item.get("keywords", []))

        searchable |= tokens(
            " ".join([
                str(item.get("title", "")),
                str(item.get("description", "")),
                str(item.get("query", "")),
            ])
        )

        score = len(wanted & searchable)

        if score:
            ranked.append((score, item))

    ranked.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return ranked[:limit]



def import_directory(directory):
    """Recover local image assets into the persistent media pool."""
    src = Path(directory).expanduser().resolve()

    if not src.exists():
        print("Missing:", src)
        return 0

    existing = load()

    known_sources = {
        str(Path(x.get("source_file", "")).resolve())
        for x in existing
        if x.get("source_file")
    }

    IMAGES.mkdir(parents=True, exist_ok=True)

    added = 0

    for local in sorted(src.rglob("*")):
        if not local.is_file():
            continue

        if local.suffix.lower() not in EXTS:
            continue

        source_key = str(local.resolve())

        if source_key in known_sources:
            continue

        target = IMAGES / local.name

        if target.exists():
            stem = target.stem
            suffix = target.suffix
            n = 2

            while target.exists():
                target = IMAGES / f"{stem}-{n}{suffix}"
                n += 1

        shutil.copy2(local, target)

        searchable = (
            local.stem
            .replace("-", " ")
            .replace("_", " ")
        )

        existing.append({
            "title": searchable,
            "description": "",
            "query": "",
            "license": "UNKNOWN - RECOVERED LOCAL ASSET",
            "pool_file": str(target),
            "source_file": source_key,
            "keywords": sorted(tokens(searchable)),
            "provenance_status": "metadata-missing",
        })

        known_sources.add(source_key)
        added += 1

        print("  +", target.name)

    save(existing)

    print("Recovered:", added)
    print("Pool total:", len(existing))

    return added

def main():
    ap = argparse.ArgumentParser()

    sub = ap.add_subparsers(dest="cmd", required=True)

    imp = sub.add_parser("import")
    imp.add_argument("manifest")

    sea = sub.add_parser("search")
    sea.add_argument("query")
    sea.add_argument("--limit", type=int, default=8)

    sub.add_parser("stats")

    args = ap.parse_args()

    if args.cmd == "import":
        import_manifest(args.manifest)

    elif args.cmd == "search":
        results = search(args.query, args.limit)

        for score, item in results:
            print()
            print("SCORE:", score)
            print("FILE: ", item.get("pool_file"))
            print("TITLE:", item.get("title", ""))
            print("QUERY:", item.get("query", ""))
            print("LIC:  ", item.get("license", ""))

    elif args.cmd == "stats":
        items = load()

        print("PUBLIC-DOMAIN MEDIA POOL")
        print("------------------------")
        print("Assets:", len(items))
        print("Images:", IMAGES)
        print("Index: ", MANIFEST)


if __name__ == "__main__":
    main()
