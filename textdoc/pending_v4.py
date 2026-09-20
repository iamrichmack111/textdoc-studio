from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

QUEUE_FILE = (
    Path.home()
    / "textdoc-cli"
    / "media-pool"
    / "acquisition-pending.json"
)


def load_pending():
    if not QUEUE_FILE.exists():
        return []

    try:
        data = json.loads(
            QUEUE_FILE.read_text(encoding="utf-8")
        )
    except Exception:
        return []

    return data if isinstance(data, list) else []


def save_pending(items):
    QUEUE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = QUEUE_FILE.with_suffix(".tmp")

    tmp.write_text(
        json.dumps(
            items,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    tmp.replace(QUEUE_FILE)


def candidate_key(item):
    return (
        item.get("commons_page")
        or item.get("original_url")
        or item.get("url")
        or item.get("title")
    )


def queue_candidate(
    scene_number,
    scene_text,
    query,
    item,
    score,
    reasons,
):
    items = load_pending()
    key = candidate_key(item)

    items = [
        x for x in items
        if candidate_key(
            x.get("candidate", {})
        ) != key
    ]

    items.append({
        "scene_number": scene_number,
        "scene_text": scene_text,
        "query": query,
        "score": score,
        "reasons": list(reasons),
        "status": "pending",
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "candidate": dict(item),
    })

    save_pending(items)


def remove_candidate(item):
    key = candidate_key(item)

    items = [
        x for x in load_pending()
        if candidate_key(
            x.get("candidate", {})
        ) != key
    ]

    save_pending(items)


def print_pending():
    items = load_pending()

    print("=" * 42)
    print(" V4 PENDING ACQUISITIONS")
    print("=" * 42)

    if not items:
        print("None.")
        return

    for record in items:
        item = record.get("candidate", {})

        print()
        print(
            "SCENE",
            str(
                record.get("scene_number", "?")
            ).zfill(2),
        )
        print(" SCORE:", record.get("score"))
        print(" TITLE:", item.get("title"))
        print(" QUERY:", record.get("query"))
        print(
            " PAGE :",
            item.get("commons_page"),
        )


if __name__ == "__main__":
    print_pending()
