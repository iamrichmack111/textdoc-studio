from __future__ import annotations

import json
import time
from pathlib import Path

from .commons import search_public_domain, download_asset
from .director_v4 import make_plan, scene_intent
from .pending_v4 import queue_candidate, remove_candidate


ROOT = Path.home() / "textdoc-cli"
POOL_IMAGES = ROOT / "media-pool" / "images"
POOL_MANIFEST = ROOT / "media-pool" / "manifest.json"

MAX_SEARCHES = 3
MAX_RESULTS = 10


def load_manifest():
    if not POOL_MANIFEST.exists():
        return []

    try:
        data = json.loads(
            POOL_MANIFEST.read_text(encoding="utf-8")
        )
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_manifest(items):
    POOL_MANIFEST.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    POOL_MANIFEST.write_text(
        json.dumps(
            items,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def acquisition_query(scene, previous_text=""):
    """
    Return several SHORT Commons searches.

    Commons search has much better recall with short literal
    queries than with one natural-language description.
    """
    text = scene.get("text", "")
    low = text.lower()
    previous = previous_text.lower()
    intent = scene_intent(scene)

    if "haiti" in low and (
        "vodou" in low or "voodoo" in low
    ):
        return [
            "Haiti Voodoo",
            "Haiti Vodou",
            "Haiti engraving",
            "Haiti religion",
            "Haiti ceremony",
        ]

    if "new orleans" in low and any(
        word in low
        for word in (
            "african",
            "caribbean",
            "communities",
            "cultures",
        )
    ):
        return [
            "New Orleans African American engraving",
            "New Orleans 19th century engraving",
            "New Orleans African American",
            "Louisiana African American engraving",
        ]

    if intent["document"]:
        return [
            "New Orleans newspaper engraving",
            "New Orleans 19th century engraving",
            "New Orleans illustration",
        ]

    if "new orleans" in low:
        return [
            "New Orleans 19th century engraving",
            "New Orleans engraving",
        ]

    if "new orleans" in previous:
        return [
            "New Orleans 19th century engraving",
        ]

    return [
        "19th century engraving",
    ]


def candidate_text(item):
    return " ".join([
        item.get("title", ""),
        item.get("description", ""),
        item.get("artist", ""),
        item.get("credit", ""),
    ]).lower()


def pre_score(scene, item):
    """
    Conservative metadata ranking before download.

    Score not only subject/geography but whether the depicted
    event actually fits what the narration is discussing.
    """
    text = scene.get("text", "").lower()
    meta = candidate_text(item)

    score = 0
    reasons = []

    # -----------------------------------------------------
    # Geography / subject
    # -----------------------------------------------------

    if "new orleans" in text:
        if (
            "new orleans" in meta
            or "louisiana" in meta
        ):
            score += 20
            reasons.append("New Orleans/Louisiana +20")

    if "haiti" in text:
        if "haiti" in meta or "haitian" in meta:
            score += 24
            reasons.append("Haiti +24")
        else:
            score -= 25
            reasons.append("missing Haiti -25")

    if "vodou" in text or "voodoo" in text:
        if any(
            x in meta
            for x in (
                "vodou",
                "voodoo",
                "voudou",
                "vodun",
            )
        ):
            score += 28
            reasons.append("Vodou +28")
        else:
            score -= 28
            reasons.append("missing Vodou -28")

    # -----------------------------------------------------
    # Historical medium
    # -----------------------------------------------------

    historical_words = (
        "engraving",
        "engraved",
        "illustration",
        "illustrated",
        "lithograph",
        "print",
        "drawing",
        "sketch",
        "1880",
        "1870",
        "1860",
        "1850",
        "1840",
        "1830",
        "1820",
        "1810",
    )

    if any(x in meta for x in historical_words):
        score += 16
        reasons.append("historical medium/period +16")

    # -----------------------------------------------------
    # Cultural/community narration
    # -----------------------------------------------------

    cultural_scene = any(
        x in text
        for x in (
            "culture",
            "cultures",
            "cultural",
            "community",
            "communities",
            "african",
            "caribbean",
            "tradition",
            "traditions",
        )
    )

    everyday_people = any(
        x in meta
        for x in (
            "woman",
            "women",
            "man",
            "men",
            "people",
            "african-american",
            "african american",
            "street",
            "square",
            "park",
            "walking",
            "fashion",
        )
    )

    if cultural_scene and everyday_people:
        score += 12
        reasons.append(
            "community/everyday-life context +12"
        )

    # -----------------------------------------------------
    # Event compatibility
    # -----------------------------------------------------

    violent_asset = any(
        x in meta
        for x in (
            "riot",
            "murder",
            "murdering",
            "violence",
            "battle",
            "massacre",
            "killed",
            "war",
        )
    )

    violent_scene = any(
        x in text
        for x in (
            "riot",
            "murder",
            "violence",
            "battle",
            "massacre",
            "killed",
            "war",
        )
    )

    if violent_asset and not violent_scene:
        score -= 35
        reasons.append(
            "violent event not discussed -35"
        )

    funeral_asset = any(
        x in meta
        for x in (
            "funeral",
            "cortege",
            "burial",
            "cemetery",
        )
    )

    funeral_scene = any(
        x in text
        for x in (
            "funeral",
            "burial",
            "death",
            "died",
            "cemetery",
        )
    )

    if funeral_asset and not funeral_scene:
        score -= 20
        reasons.append(
            "funeral event not discussed -20"
        )

    # -----------------------------------------------------
    # Music mismatch
    #
    # Require strong music metadata rather than substring-ish
    # incidental metadata.
    # -----------------------------------------------------

    music_asset = any(
        x in meta
        for x in (
            "jazz band",
            "musicians",
            "musician",
            "concert",
            "performing music",
            "musical performance",
        )
    )

    music_scene = any(
        x in text
        for x in (
            "jazz",
            "music",
            "musician",
            "concert",
            "band",
        )
    )

    if music_asset and not music_scene:
        score -= 30
        reasons.append("unrequested music -30")

    return score, reasons


def safe_name(text):
    import re

    text = re.sub(
        r"[^a-zA-Z0-9]+",
        "-",
        text,
    ).strip("-")

    return text[:100] or "commons-asset"


def already_known(items, commons_page, title):
    for item in items:
        if (
            commons_page
            and item.get("commons_page") == commons_page
        ):
            return True

        if title and item.get("title") == title:
            return True

    return False


def acquire_missing(
    scenes,
    project_pictures,
    threshold=12,
):
    POOL_IMAGES.mkdir(
        parents=True,
        exist_ok=True,
    )

    initial_plan = make_plan(
        scenes=scenes,
        project_pictures=project_pictures,
        threshold=threshold,
    )

    requests = []
    previous = ""

    for scene, decision in zip(
        scenes,
        initial_plan,
    ):
        if (
            scene.get("kind") == "narration"
            and not decision.get("primary")
        ):
            requests.append({
                "scene": decision["scene"],
                "scene_data": scene,
                "query": acquisition_query(
                    scene,
                    previous,
                ),
            })

        previous = scene.get("text", "")

    if not requests:
        print("No missing narration shots.")
        return initial_plan

    requests = requests[:MAX_SEARCHES]

    manifest = load_manifest()
    added = 0

    print()
    print("==========================================")
    print(" V4 TARGETED ACQUISITION")
    print("==========================================")

    for req in requests:
        number = req["scene"]
        scene = req["scene_data"]
        queries = req["query"]

        if isinstance(queries, str):
            queries = [queries]

        print()
        print(
            f"SCENE {number:02d} SEARCH FAMILY:"
        )

        for q in queries:
            print("  -", q)

        results = []
        seen_results = set()

        for query in queries:
            try:
                batch = search_public_domain(
                    query,
                    limit=6,
                    width=1600,
                )
            except Exception as exc:
                print(
                    "  Commons unavailable:",
                    type(exc).__name__,
                    exc,
                )

                if "429" in str(exc):
                    print(
                        "  Rate limited; ending search family."
                    )
                    break

                continue

            for item in batch:
                key = (
                    item.get("commons_page")
                    or item.get("title")
                )

                if not key or key in seen_results:
                    continue

                seen_results.add(key)

                # Remember which short query found it.
                item = dict(item)
                item["_acquisition_query"] = query
                results.append(item)

            # Be deliberately polite to Commons.
            time.sleep(3)

        ranked = []

        for item in results:
            score, reasons = pre_score(
                scene,
                item,
            )

            ranked.append(
                (score, item, reasons)
            )

        ranked.sort(
            key=lambda x: x[0],
            reverse=True,
        )

        accepted = None

        for score, item, reasons in ranked:
            print()
            print(
                f"  candidate score={score}:",
                item.get("title", "UNKNOWN"),
            )

            for reason in reasons:
                print("    -", reason)

            # Conservative acquisition threshold.
            if score < 20:
                continue

            if already_known(
                manifest,
                item.get("commons_page", ""),
                item.get("title", ""),
            ):
                print("    already in pool")
                continue

            accepted = (
                score,
                item,
                reasons,
            )
            break

        if not accepted:
            print(
                "  No candidate passed metadata gate."
            )
            time.sleep(2)
            continue

        score, item, reasons = accepted

        # Save the selected candidate BEFORE network I/O.
        # If Commons returns 429, we retain the discovery.
        queue_candidate(
            scene_number=number,
            scene_text=scene.get("text", ""),
            query=item.get(
                "_acquisition_query",
                queries[0],
            ),
            item=item,
            score=score,
            reasons=reasons,
        )

        #
        # download_asset() takes an OUTPUT DIRECTORY,
        # creates its own filename, and returns that path.
        #
        try:
            destination = download_asset(
                item,
                POOL_IMAGES,
                prefix=f"scene-{number:02d}",
                retries=1,
            )
        except Exception as exc:
            message = str(exc)

            print(
                "  Download deferred:",
                type(exc).__name__,
                message,
            )

            if (
                "WIKIMEDIA_RATE_LIMITED" in message
                or "429" in message
            ):
                print(
                    "  Wikimedia throttled the asset; "
                    "keeping graphics fallback."
                )
                break

            continue

        destination = Path(destination)

        if (
            not destination.is_file()
            or destination.stat().st_size < 4096
        ):
            print(
                "  Download did not produce a valid image."
            )
            continue

        # Successful local acquisition: it is no longer pending.
        remove_candidate(item)

        entry = {
            "title": item.get("title", ""),
            "description": item.get(
                "description", ""
            ),
            "artist": item.get("artist", ""),
            "credit": item.get("credit", ""),
            "license": item.get("license", ""),
            "license_url": item.get(
                "license_url", ""
            ),
            "commons_page": item.get(
                "commons_page", ""
            ),
            "original_url": item.get(
                "original_url", ""
            ),
            "query": item.get(
                "_acquisition_query",
                queries[0],
            ),
            "pool_file": str(destination),
            "keywords": sorted(
                set(query.lower().split())
            ),
            "provenance_status":
                "verified-public-domain",
            "rights_status":
                "verified-public-domain",
            "acquired_for_scene": number,
            "metadata_score": score,
        }

        manifest.append(entry)
        save_manifest(manifest)

        added += 1

        print()
        print("  ADDED:", destination.name)
        print(
            "  LICENSE:",
            entry["license"],
        )

        time.sleep(3)

    print()
    print("------------------------------------------")
    print("New verified assets:", added)
    print("------------------------------------------")

    # Critical step: Director gets the final say.
    final_plan = make_plan(
        scenes=scenes,
        project_pictures=project_pictures,
        threshold=threshold,
    )

    return final_plan
