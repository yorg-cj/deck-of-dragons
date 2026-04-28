"""
AI reviewer — sends each card from the most recent reading to Claude Haiku
for review. Haiku judges whether the House assignment is correct and writes
confirmed or corrected labels to the training DB.

Run after any draw or refresh:
    python3 scripts/ai_review_reading.py

This is a training-time tool only. The deployed app does not use it.
Cost: ~$0.0003 per reading (7 cards × ~200 tokens each at Haiku pricing).
"""
import json
import os
import sqlite3
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
import httpx
import truststore
from dotenv import load_dotenv

load_dotenv()

_DB_PATH    = Path(__file__).parent.parent / "data" / "training.db"
_CACHE_DIR  = Path(__file__).parent.parent / "data" / "cache"

_HOUSES = [
    "High House War",
    "High House Coin",
    "High House Shadow",
    "High House Life",
    "High House Iron",
    "High House Words",
    "High House Chains",
    "None",
]

_SYSTEM = """\
You are reviewing automated House assignments for a political oracle. \
Each House represents a domain of power in world events:

- High House War: armed conflict, military operations, weapons, warfare, defense
- High House Coin: finance, trade, economics, markets, sanctions, monetary policy
- High House Shadow: intelligence, espionage, covert ops, surveillance, leaks, disinformation
- High House Life: health, environment, humanitarian aid, food security, climate, ecology
- High House Iron: technology, infrastructure, industry, manufacturing, energy, space
- High House Words: media, diplomacy, narrative control, communications, soft power, law
- High House Chains: treaties, debt, occupation, binding agreements, institutional control

Reversed means the House is active in a distorted, blocked, weaponised, or failing form \
(e.g. war crimes, financial fraud, intelligence failure, censorship, famine, tech ban).

You will be shown an article and its current assignment. \
Respond with JSON only. No explanation. Format:
{"correct": <true|false>, "house": "<correct House or None>", "reversed": <true|false>, "confidence": <0.0-1.0>}

If the assignment is correct, echo it back with "correct": true. \
If wrong, give the right House with "correct": false."""

_USER_TEMPLATE = """\
Article:
{text}

Current assignment: {house}{rev}

Is this correct?"""


def _make_client() -> anthropic.Anthropic:
    ssl_ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    http_client = httpx.Client(verify=ssl_ctx)
    return anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        http_client=http_client,
    )


def _get_article_text(conn: sqlite3.Connection, url: str) -> str:
    row = conn.execute(
        "SELECT full_text, text, title FROM articles WHERE url = ?", (url,)
    ).fetchone()
    if not row:
        return ""
    full_text, text, title = row
    return (full_text or text or title or "")[:1500]


def _review_card(client: anthropic.Anthropic, article_text: str, card: dict) -> dict | None:
    rev_str = " (REVERSED)" if card.get("reversed") else ""
    prompt = _USER_TEMPLATE.format(
        text=article_text,
        house=card["house"],
        rev=rev_str,
    )
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=128,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        print(f"    API error: {e}")
        return None


def _save_label(conn: sqlite3.Connection, url: str, title: str, review: dict) -> None:
    conn.execute("""
        INSERT OR REPLACE INTO labels
            (article_id, house, title, reversed, confidence, key_signals, label_source)
        VALUES (?, ?, ?, ?, ?, '[]', 'ai_reviewed')
    """, (
        url,
        review["house"],
        title,
        int(bool(review.get("reversed", False))),
        float(review.get("confidence", 0.9)),
    ))


def run(cache_file: Path | None = None) -> None:
    # Find reading to review
    if cache_file is None:
        candidates = sorted(_CACHE_DIR.glob("*.json"), reverse=True)
        if not candidates:
            print("No cached reading found. Run the app and draw first.")
            return
        cache_file = candidates[0]

    reading = json.loads(cache_file.read_text())
    cards = reading.get("cards", [])
    print(f"Reviewing reading from {reading['date']} ({len(cards)} cards)\n")

    client  = _make_client()
    conn    = sqlite3.connect(_DB_PATH)
    written = 0

    for card in cards:
        url   = card["article"]["url"]
        title = card["article"]["title"]
        text  = _get_article_text(conn, url)

        if not text:
            print(f"  SKIP (no article text in DB): {title[:60]}")
            continue

        review = _review_card(client, text, card)
        if review is None or review.get("house") not in _HOUSES:
            print(f"  SKIP (bad response): {title[:60]}")
            continue

        was       = card["house"].replace("High House ", "")
        now       = review["house"].replace("High House ", "")
        rev_now   = " [R]" if review.get("reversed") else ""
        changed   = was != now or bool(card.get("reversed")) != bool(review.get("reversed"))
        tag       = "CORRECTED" if changed else "confirmed"
        arrow     = f"{was} → {now}{rev_now}" if changed else f"{now}{rev_now}"

        print(f"  {tag:<10} {arrow:<30} {title[:50]}")

        _save_label(conn, url, title, review)
        written += 1

    conn.commit()
    conn.close()
    print(f"\nDone. {written}/{len(cards)} labels written to training DB.")
    print("Run  python3 -m src.train.train  to retrain with the new labels.")


if __name__ == "__main__":
    run()
