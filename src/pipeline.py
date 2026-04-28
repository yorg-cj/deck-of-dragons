"""
Main pipeline: fetch → classify → deduplicate → cache → return reading.
One card per active House; only Houses above the confidence threshold appear.
"""
import json
import sqlite3
from datetime import date
from pathlib import Path

from src.classify import house as house_clf
from src.classify import title as title_clf
from src.classify import reversal as reversal_clf
from src.fetch import sources
from src.fetch.gdelt import query_actor_tone, query_all_house_trends

_CACHE_DIR  = Path(__file__).parent.parent / "data" / "cache"
_DB_PATH    = Path(__file__).parent.parent / "data" / "training.db"
_CONFIDENCE_THRESHOLD = 0.13   # minimum cosine similarity to appear as a card


def get_reading(force_refresh: bool = False) -> dict:
    """
    Return today's reading. Loads from cache if available; fetches and
    classifies otherwise. Set force_refresh=True to re-run the pipeline.
    """
    _CACHE_DIR.mkdir(exist_ok=True)
    cache_file = _CACHE_DIR / f"{date.today()}.json"

    if cache_file.exists() and not force_refresh:
        return json.loads(cache_file.read_text())

    reading = _build_reading()

    cache_file.write_text(json.dumps(reading, indent=2))
    return reading


def _build_reading() -> dict:
    # 1. Fetch articles from all sources
    articles = sources.fetch_all(days=2, save=True)

    # 2. Classify each article
    classified = []
    for art in articles:
        content = art.get("full_text") or art["text"]
        if not content.strip():
            continue

        result = house_clf.classify(content)
        if result["confidence"] < _CONFIDENCE_THRESHOLD:
            continue

        t     = title_clf.assign(content, result["house"])
        r     = reversal_clf.detect(content, result["house"])

        classified.append({
            "house":      result["house"],
            "title":      t,
            "reversed":   r["reversed"],
            "confidence": result["confidence"],
            "scores":     result["scores"],
            "reversal":   r,
            "article": {
                "title":    art["title"],
                "url":      art["url"],
                "source":   art["source"],
                "full_text": art.get("full_text"),
            },
        })

    # 3. One card per House — keep highest confidence
    by_house: dict[str, dict] = {}
    for card in classified:
        h = card["house"]
        if h not in by_house or card["confidence"] > by_house[h]["confidence"]:
            by_house[h] = card

    active_cards = sorted(by_house.values(), key=lambda c: c["confidence"], reverse=True)

    # 4. Volume trends first (fewer queries, less rate-limit pressure),
    #    then relationship detection between active Houses
    house_trends  = _detect_trends(active_cards)
    relationships = _detect_relationships(active_cards)

    # 5. Assign spatial positions to cards for the reading layout
    positioned = _assign_positions(active_cards, relationships, house_trends)

    reading = {
        "date":          str(date.today()),
        "cards":         positioned,
        "relationships": relationships,
        "house_trends":  house_trends,
    }

    _save_to_db(active_cards)
    return reading


def _extract_actor(title: str, nlp) -> str | None:
    """Extract the primary named entity from an article title via spaCy NER.
    Filters out short abbreviations (< 4 chars) that are unlikely to be real actors."""
    doc = nlp(title[:200])
    for label in ("GPE", "ORG", "PERSON"):
        matches = [
            ent.text.upper() for ent in doc.ents
            if ent.label_ == label and len(ent.text.strip()) >= 4
        ]
        if matches:
            return matches[0]
    return None


def _detect_relationships(cards: list[dict]) -> list[dict]:
    """
    Build relationship pairs between active Houses using GDELT tone scores.
    Queries GDELT Doc API for articles mentioning each actor pair together.
    """
    if len(cards) < 2:
        return []

    import spacy
    import time
    nlp = spacy.load("en_core_web_sm")

    card_actors: list[tuple[dict, str | None]] = [
        (card, _extract_actor(card["article"]["title"], nlp))
        for card in cards
    ]

    relationships = []
    seen_pairs: set[frozenset] = set()

    for i, (card_a, actor_a) in enumerate(card_actors):
        for card_b, actor_b in card_actors[i + 1:]:
            if actor_a is None or actor_b is None:
                continue
            pair = frozenset({card_a["house"], card_b["house"]})
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            rel = query_actor_tone(actor_a, actor_b, days=7)
            time.sleep(1.5)   # avoid GDELT rate limit

            if rel:
                relationships.append({
                    "house_a":      card_a["house"],
                    "house_b":      card_b["house"],
                    "actor_a":      actor_a,
                    "actor_b":      actor_b,
                    "relationship": rel["relationship"],
                    "goldstein_avg": rel["tone_avg"],
                    "confidence":   rel["confidence"],
                    "source":       rel["source"],
                })

    return relationships


def _detect_trends(cards: list[dict]) -> dict[str, dict]:
    """Query GDELT volume trends for all active Houses."""
    houses = [c["house"] for c in cards]
    try:
        return query_all_house_trends(houses, delay=0.5)
    except Exception:
        return {}


def _assign_positions(
    cards: list[dict],
    relationships: list[dict],
    house_trends: dict[str, dict] | None = None,
) -> list[dict]:
    """
    Assign a layout position to each card based on confidence, relationships,
    and GDELT volume trends.

    Positions:
        CENTER     — highest confidence card (dominant force)
        ASCENDING  — most opposed to CENTER per GDELT tone (falls back to 2nd highest)
        FOUNDATION — most stable/structural force (lowest trend ratio = long-running)
        WANING     — falling coverage in GDELT volume trend
        EMERGING   — rising coverage in GDELT volume trend
        WILD       — remaining unaligned cards
    """
    if not cards:
        return cards

    positioned = [dict(c) for c in cards]
    house_trends = house_trends or {}

    # CENTER: highest confidence
    positioned[0]["position"] = "CENTER"
    if len(positioned) == 1:
        return positioned

    center_house = positioned[0]["house"]
    assigned: set[int] = {0}

    # ASCENDING: card most opposed to CENTER
    opposing = {
        (r["house_b"] if r["house_a"] == center_house else r["house_a"]): r["goldstein_avg"]
        for r in relationships
        if center_house in (r["house_a"], r["house_b"])
        and r.get("relationship") == "opposed"
    }

    ascending_idx = None
    if opposing:
        most_opposed = min(opposing, key=opposing.get)
        for i, c in enumerate(positioned[1:], 1):
            if c["house"] == most_opposed:
                ascending_idx = i
                break

    if ascending_idx is None:
        ascending_idx = 1  # fallback: second-highest confidence

    positioned[ascending_idx]["position"] = "ASCENDING"
    assigned.add(ascending_idx)

    remaining = [i for i in range(len(positioned)) if i not in assigned]

    # WANING: falling GDELT volume — falls back to lowest-confidence remaining card
    falling = [
        i for i in remaining
        if house_trends.get(positioned[i]["house"], {}).get("trend") == "falling"
    ]
    if falling:
        waning_idx = min(falling, key=lambda i: house_trends[positioned[i]["house"]]["trend_ratio"])
    elif len(remaining) >= 3:
        waning_idx = remaining[-1]   # lowest confidence among remaining
    else:
        waning_idx = None

    if waning_idx is not None:
        positioned[waning_idx]["position"] = "WANING"
        assigned.add(waning_idx)
        remaining = [i for i in remaining if i != waning_idx]

    # EMERGING: rising GDELT volume — falls back to third-highest confidence remaining card
    rising = [
        i for i in remaining
        if house_trends.get(positioned[i]["house"], {}).get("trend") == "rising"
    ]
    if rising:
        emerging_idx = max(rising, key=lambda i: house_trends[positioned[i]["house"]]["trend_ratio"])
    elif len(remaining) >= 2:
        emerging_idx = remaining[-1]  # lowest confidence among remaining (different from waning)
    else:
        emerging_idx = None

    if emerging_idx is not None:
        positioned[emerging_idx]["position"] = "EMERGING"
        assigned.add(emerging_idx)
        remaining = [i for i in remaining if i != emerging_idx]

    # FOUNDATION: most stable remaining card — falls back to next highest confidence
    if remaining:
        stable = sorted(
            remaining,
            key=lambda i: abs(house_trends.get(positioned[i]["house"], {}).get("trend_ratio", 1.0) - 1.0)
        )
        positioned[stable[0]]["position"] = "FOUNDATION"
        assigned.add(stable[0])
        remaining = [i for i in remaining if i != stable[0]]

    # WILD: at most 2 overflow cards (grid only renders 2 WILD slots)
    for i in remaining[:2]:
        positioned[i]["position"] = "WILD"
    # Any extras beyond 2 WILD slots get folded into FOUNDATION's position
    # by keeping them as WILD — they'll still appear in sources list
    for i in remaining[2:]:
        positioned[i]["position"] = "WILD"

    return positioned


def _save_to_db(cards: list[dict]):
    """Persist the article→house mapping to the training database."""
    conn = sqlite3.connect(_DB_PATH)
    for card in cards:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO articles
                   (id, url, title, text, full_text, section, source, fetched_at)
                   VALUES (?, ?, ?, ?, ?, '', ?, datetime('now'))""",
                (card["article"]["url"], card["article"]["url"],
                 card["article"]["title"], card["article"]["title"],
                 card["article"].get("full_text"), card["article"]["source"])
            )
        except Exception:
            pass
    conn.commit()
    conn.close()
