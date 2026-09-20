from __future__ import annotations

import argparse
import json
from pathlib import Path

from .commons import search_public_domain, download_asset

DEFAULT_QUERIES = [
    "New Orleans 19th century",
    "Louisiana African American history",
    "Louisiana folk culture historical",
    "New Orleans 1889 Voodoo",
    "New Orleans historical engraving",
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="assets/commons")
    ap.add_argument("--per-query", type=int, default=2)
    ap.add_argument("queries", nargs="*")
    a = ap.parse_args()

    queries = a.queries or DEFAULT_QUERIES
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)

    manifest = []
    seen = set()

    for q in queries:
        print(f"\n[commons] {q}")

        try:
            results = search_public_domain(q, limit=15)
        except Exception as e:
            print("  ERROR:", e)
            continue

        taken = 0

        for item in results:
            if item["url"] in seen:
                continue

            try:
                path = download_asset(
                    item,
                    out,
                    prefix=f"{len(manifest)+1:02d}"
                )
            except Exception as e:
                print("  download failed:", e)
                continue

            seen.add(item["url"])
            item["query"] = q
            item["local_file"] = str(path)
            manifest.append(item)

            print("  +", path.name)
            print("    license:", item["license"])
            print("    source:", item["commons_page"])

            taken += 1
            if taken >= a.per_query:
                break

    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"\nDownloaded {len(manifest)} verified PD assets")
    print("Manifest:", out / "manifest.json")

if __name__ == "__main__":
    main()
