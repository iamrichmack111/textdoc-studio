from __future__ import annotations

import json
import re
from pathlib import Path


STOP = {
    "a", "an", "and", "are", "as", "at", "be", "been",
    "being", "but", "by", "can", "city", "could", "did",
    "do", "does", "for", "from", "had", "has", "have",
    "he", "her", "here", "him", "his", "how", "i", "if",
    "in", "into", "is", "it", "its", "may", "more",
    "most", "not", "of", "on", "or", "our", "people",
    "scene", "she", "so", "some", "such", "than", "that",
    "the", "their", "them", "then", "there", "these",
    "they", "this", "those", "through", "to", "under",
    "very", "was", "we", "were", "what", "when", "where",
    "which", "while", "who", "why", "will", "with",
    "would", "you", "your",
}

GRAPHIC_KINDS = {"chapter", "punch", "quote", "words"}

CONCEPTS = {
    "new_orleans": {
        "new orleans", "orleans", "louisiana",
    },
    "haiti": {
        "haiti", "haitian",
    },
    "vodou": {
        "vodou", "voodoo", "voudou", "vodun",
    },
    "music": {
        "music", "musician", "musicians", "jazz",
        "band", "concert", "song",
    },
    "document": {
        "newspaper", "newspapers", "article", "articles",
        "headline", "headlines", "gazette", "journal",
        "publication", "publications", "illustrated",
        "illustration", "illustrations", "engraving",
        "engraved", "print", "printed", "document",
        "documents", "archive", "archives", "lithograph",
        "notice", "notices", "map", "atlas",
    },
    "map": {
        "map", "atlas", "cartography", "geography",
    },
}


# Offline editorial vocabulary for user-supplied pictures.
# Descriptive filenames act like lightweight semantic tags.
EDITORIAL_TAGS = {
    "community": {
        "creole", "african", "caribbean", "community",
        "communities", "people", "woman", "women",
        "worker", "workers", "street", "streets",
    },
    "city_history": {
        "street", "streets", "map", "cathedral",
        "architecture", "building", "buildings",
        "steamboat", "mississippi", "river",
    },
    "labor": {
        "worker", "workers", "labor", "sugarcane",
        "plantation", "agriculture",
    },
    "river": {
        "mississippi", "river", "steamboat", "boat",
        "shipping", "commerce",
    },
    "creole": {
        "creole",
    },
    "religion": {
        "vodou", "voodoo", "ceremony", "religion",
        "religious", "church", "cathedral",
    },
    "slavery": {
        "slave", "slavery", "enslaved", "sale",
    },
}


def editorial_tags(text):
    words = tokens(text)
    found = set()

    for name, vocab in EDITORIAL_TAGS.items():
        if words & vocab:
            found.add(name)

    return found


COMMERCIAL = {
    "warehouse", "wholesale", "distribution",
    "commercial", "company", "factory", "center",
}

HISTORICAL_MEDIA = {
    "engraving", "engraved", "illustration",
    "illustrated", "newspaper", "archive", "historical",
    "antique", "lithograph", "print", "drawing", "sketch",
}

MODERN_YEARS = {str(y) for y in range(1950, 2027)}


def tokens(text):
    return {
        x for x in re.findall(r"[a-z0-9]+", str(text).lower())
        if len(x) >= 3 and x not in STOP
    }


def phrase_present(text, phrase):
    return phrase in str(text).lower()


def concepts(text):
    low = str(text).lower()
    words = tokens(low)
    found = set()

    for name, vocab in CONCEPTS.items():
        for term in vocab:
            if " " in term:
                if phrase_present(low, term):
                    found.add(name)
                    break
            elif term in words:
                found.add(name)
                break

    return found


def scene_intent(scene):
    text = scene.get("text", "")
    words = tokens(text)
    cs = concepts(text)

    historical = (
        bool(words & {
            "historical", "history", "century",
            "nineteenth", "eighteenth", "seventeenth",
        })
        or bool(re.search(r"\b(17|18|19)\d{2}\b", text))
    )

    cultural = bool(
        words & {
            "african", "european", "caribbean",
            "american", "community", "communities",
            "culture", "cultures", "religious",
            "religion", "tradition", "traditions",
            "folk",
        }
    )

    return {
        "historical": historical,
        "cultural": cultural,
        "document": "document" in cs,
        "concepts": cs,
    }


def load_pool(path=None):
    # V4 is local-first. No external/persistent media pool is
    # loaded unless a manifest path is explicitly supplied.
    if path is None or path == []:
        return []

    path = Path(path)

    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    return data if isinstance(data, list) else []


def candidate_from_project(path):
    p = Path(path)
    return {
        "path": str(p),
        "origin": "project",
        "title": p.stem.replace("-", " ").replace("_", " "),
        "description": "",
        "keywords": [],
        "provenance_status": "user-project",
    }


def candidate_from_pool(item):
    path = item.get("pool_file")
    if not path or not Path(path).exists():
        return None

    return {
        "path": str(Path(path)),
        "origin": "pool",
        "title": item.get("title", ""),
        "description": item.get("description", ""),
        "keywords": item.get("keywords", []) or [],
        "query": item.get("query", ""),
        "license": item.get("license", ""),
        "provenance_status": item.get(
            "provenance_status", ""
        ),
    }


def candidate_text(c):
    return " ".join([
        c.get("title", ""),
        c.get("description", ""),
        c.get("query", ""),
        " ".join(c.get("keywords", []) or []),
        Path(c.get("path", "")).stem,
    ])


def looks_like_document(candidate):
    return "document" in concepts(candidate_text(candidate))


def score_candidate(scene, candidate, previous_text=""):
    text = scene.get("text", "")
    sw = tokens(text)
    aw = tokens(candidate_text(candidate))

    scene_c = concepts(text)
    asset_c = concepts(candidate_text(candidate))
    previous_c = concepts(previous_text)

    intent = scene_intent(scene)

    score = 0
    reasons = []

    overlap = sw & aw
    if overlap:
        pts = min(3 * len(overlap), 15)
        score += pts
        reasons.append(
            f"meaningful overlap +{pts}: "
            + ", ".join(sorted(overlap)[:6])
        )

    exact_concepts = scene_c & asset_c
    if exact_concepts:
        pts = 16 * len(exact_concepts)
        score += pts
        reasons.append(
            f"subject match +{pts}: "
            + ", ".join(sorted(exact_concepts))
        )

    # User filenames are intentional editorial metadata.
    # Reward semantic relationships rather than requiring
    # literal narration/filename word overlap.
    scene_tags = editorial_tags(scene.get("text", ""))
    asset_tags = editorial_tags(candidate_text(candidate))

    editorial_match = scene_tags & asset_tags

    if candidate.get("origin") == "project" and editorial_match:
        pts = min(24, 8 * len(editorial_match))
        score += pts
        reasons.append(
            f"editorial filename match +{pts}: "
            + ", ".join(sorted(editorial_match))
        )

    # Cultural narration benefits from human/community imagery.
    if (
        candidate.get("origin") == "project"
        and intent["cultural"]
        and "community" in asset_tags
    ):
        score += 18
        reasons.append("cultural/community visual +18")

    # New Orleans cultural material gets a smaller bonus for
    # locally descriptive city-history imagery.
    if (
        candidate.get("origin") == "project"
        and "new_orleans" in scene_c
        and "new_orleans" in asset_c
        and "city_history" in asset_tags
    ):
        score += 12
        reasons.append("New Orleans city-history visual +12")

    # Previous geography is only a weak contextual bonus.
    if (
        "new_orleans" in previous_c
        and "new_orleans" in asset_c
    ):
        score += 4
        reasons.append("prior New Orleans context +4")

    # Named subjects are hard requirements.
    for subject, penalty in (
        ("haiti", 30),
        ("vodou", 34),
    ):
        if subject in scene_c and subject not in asset_c:
            score -= penalty
            reasons.append(
                f"missing required {subject} subject -{penalty}"
            )

    # New Orleans alone is not enough for cultural narration.
    if intent["cultural"]:
        if aw & COMMERCIAL:
            score -= 36
            reasons.append(
                "generic commercial image rejected -36"
            )

        # A mere geographic match needs another relevant subject.
        if (
            "new_orleans" in asset_c
            and not (sw & aw - {"new", "orleans", "louisiana"})
            and not (scene_c & asset_c - {"new_orleans"})
        ):
            score -= 18
            reasons.append(
                "location-only match insufficient -18"
            )

    # Print/newspaper narration requires print/document imagery.
    if intent["document"]:
        if "document" in asset_c:
            score += 30
            reasons.append("document intent matched +30")
        else:
            score -= 32
            reasons.append("document intent not represented -32")

    if intent["historical"]:
        if aw & HISTORICAL_MEDIA:
            score += 14
            reasons.append("historical medium +14")

        if aw & MODERN_YEARS:
            score -= 28
            reasons.append("modern image for historical scene -28")

    if "music" in asset_c and "music" not in scene_c:
        score -= 26
        reasons.append("unrequested music imagery -26")

    if candidate.get("origin") == "project":
        score += 2
        reasons.append("project asset +2")

    if candidate.get("provenance_status") == "metadata-missing":
        score -= 2
        reasons.append("unverified provenance -2")

    return score, reasons


def plan_scene(
    scene,
    index,
    project_pictures,
    pool_items,
    previous_text="",
    threshold=12,
    used_assets=None,
):
    kind = str(scene.get("kind", "narration")).lower()

    result = {
        "scene": index + 1,
        "kind": kind,
        "text": scene.get("text", ""),
        "treatment": kind if kind in GRAPHIC_KINDS else "narration",
        "primary": None,
        "secondary": None,
        "score": None,
        "origin": None,
        "provenance_status": None,
        "reasons": [],
    }

    if kind in GRAPHIC_KINDS:
        result["reasons"].append(f"{kind} is graphics-first")
        return result

    requested = str(scene.get("image", "")).strip()
    if requested:
        wanted = Path(requested).name.lower()

        for p in project_pictures:
            if Path(p).name.lower() == wanted:
                result.update({
                    "treatment": "archive",
                    "primary": str(p),
                    "score": 999,
                    "origin": "explicit",
                    "provenance_status": "user-project",
                    "reasons": ["explicit IMAGE directive"],
                })
                return result

        result["reasons"].append(
            f"requested IMAGE not found: {requested}"
        )

    candidates = [
        candidate_from_project(p)
        for p in project_pictures
    ]

    seen = {
        str(Path(c["path"]).resolve())
        for c in candidates
    }

    for item in pool_items:
        c = candidate_from_pool(item)
        if not c:
            continue

        resolved = str(Path(c["path"]).resolve())
        if resolved not in seen:
            candidates.append(c)
            seen.add(resolved)

    scored = []

    for c in candidates:
        score, reasons = score_candidate(
            scene, c, previous_text
        )

        prior_uses = 0

        if used_assets:
            prior_uses = used_assets.get(
                c["path"],
                0,
            )

        if prior_uses:
            penalty = 30 * prior_uses
            score -= penalty

            reasons = list(reasons)
            reasons.append(
                f"reuse penalty -{penalty} "
                f"({prior_uses} prior use"
                f"{'s' if prior_uses != 1 else ''})"
            )

        scored.append(
            (score, c["path"], c, reasons)
        )

    scored.sort(key=lambda x: (-x[0], x[1]))

    if not scored:
        result["reasons"].append(
            "no candidates; graphics fallback"
        )
        return result

    best_score, _, best, reasons = scored[0]
    result["score"] = best_score
    result["reasons"].extend(reasons)

    if best_score < threshold:
        result["reasons"].append(
            f"below relevance threshold "
            f"({best_score} < {threshold}); graphics fallback"
        )
        return result

    result["primary"] = best["path"]
    result["origin"] = best.get("origin")
    result["provenance_status"] = best.get(
        "provenance_status"
    )

    result["treatment"] = (
        "document"
        if looks_like_document(best)
        else "archive"
    )

    # Secondary imagery must independently pass relevance.
    for score, _, c, _ in scored[1:]:
        if score >= threshold:
            result["secondary"] = c["path"]
            break

    return result


def make_plan(
    scenes,
    project_pictures,
    pool_manifest=None,
    threshold=12,
):
    pool = load_pool(pool_manifest)
    result = []
    previous = ""
    used_assets = {}

    for i, scene in enumerate(scenes):
        decision = plan_scene(
            scene,
            i,
            project_pictures,
            pool,
            previous_text=previous,
            threshold=threshold,
            used_assets=used_assets,
        )

        result.append(decision)

        primary = decision.get("primary")

        if primary:
            used_assets[primary] = (
                used_assets.get(primary, 0) + 1
            )

        previous = scene.get("text", "")

    return result


def print_plan(plan):
    print()
    print("==========================================")
    print(" V4 DIRECTOR SHOT PLAN")
    print("==========================================")

    for item in plan:
        primary = (
            Path(item["primary"]).name
            if item.get("primary")
            else "TYPOGRAPHY"
        )

        print(
            f"SCENE {item['scene']:02d} "
            f"{item['kind'].upper():10} "
            f"{item['treatment'].upper():10} "
            f"score={item['score']} "
            f"{primary}"
        )

        for reason in item.get("reasons", []):
            print("   -", reason)

    print("==========================================")
