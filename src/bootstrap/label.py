"""
Bootstrap labeler — calls Claude Haiku to assign House labels to articles
already stored in the training database.

Run once:
    python3 -m src.bootstrap.label

Cost estimate: ~218 articles × ~400 tokens ≈ $0.04 at Haiku pricing.
Labels are written to the `labels` table; existing labels are skipped.
"""
import json
import os
import sqlite3
import time
from pathlib import Path

import anthropic
import httpx
import ssl
import truststore
from dotenv import load_dotenv

load_dotenv()

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "training.db"

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
You are a political analyst classifying news articles into thematic categories \
called "Houses." Each House represents a domain of power.

Houses:
- High House War: armed conflict, military operations, weapons, armies, warfare
- High House Coin: finance, trade, economics, markets, sanctions, monetary policy
- High House Shadow: intelligence, espionage, covert operations, surveillance, leaks
- High House Life: health, environment, humanitarian aid, food security, climate
- High House Iron: technology, infrastructure, industry, manufacturing, energy
- High House Words: media, diplomacy, propaganda, narrative control, communications
- High House Chains: treaties, debt, occupation, binding agreements, institutional control
- None: the article does not clearly fit any House

Also determine:
- reversed: true if the House energy is distorted, weaponised, suppressed, or failing \
  (e.g. war crimes, financial fraud, intelligence failure, censorship, famine, tech ban)
- reversed: false for normal / active / constructive expressions of the House domain

Respond with JSON only. No explanation. Format:
{"house": "<House name or None>", "reversed": <true|false>, "confidence": <0.0-1.0>}"""

_USER_TEMPLATE = "Classify this news article:\n\n{text}"


def _fetch_unlabeled(conn: sqlite3.Connection, limit: int = 1000) -> list[dict]:
    rows = conn.execute("""
        SELECT a.id, a.title, a.text
        FROM articles a
        LEFT JOIN labels l ON a.id = l.article_id
        WHERE l.article_id IS NULL
        LIMIT ?
    """, (limit,)).fetchall()
    return [{"id": r[0], "title": r[1], "text": r[2]} for r in rows]


def _call_haiku(client: anthropic.Anthropic, text: str) -> dict | None:
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=128,
            system=_SYSTEM,
            messages=[{"role": "user", "content": _USER_TEMPLATE.format(text=text[:1200])}],
        )
        raw = msg.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        print(f"    API error: {e}")
        return None


def _save_label(conn: sqlite3.Connection, article_id: str, title: str, label: dict) -> None:
    conn.execute("""
        INSERT OR REPLACE INTO labels
            (article_id, house, title, reversed, confidence, key_signals, label_source)
        VALUES (?, ?, ?, ?, ?, '[]', 'claude_bootstrap')
    """, (
        article_id,
        label["house"],
        title,
        int(bool(label.get("reversed", False))),
        float(label.get("confidence", 0.0)),
    ))


def run(batch_size: int = 50, delay: float = 0.15) -> None:
    """Label all unlabeled articles in the training DB."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key.startswith("sk-ant-"):
        raise RuntimeError("ANTHROPIC_API_KEY not set — check your .env file")

    ssl_ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    http_client = httpx.Client(verify=ssl_ctx)
    client = anthropic.Anthropic(api_key=api_key, http_client=http_client)
    conn = sqlite3.connect(_DB_PATH)

    articles = _fetch_unlabeled(conn, limit=1000)
    total = len(articles)
    print(f"Labeling {total} articles with Claude Haiku...")

    labeled = 0
    skipped = 0

    for i, art in enumerate(articles):
        text = f"{art['title']}\n\n{art['text'] or ''}".strip()
        if not text:
            skipped += 1
            continue

        label = _call_haiku(client, text)
        if label is None or label.get("house") not in _HOUSES:
            skipped += 1
            print(f"  [{i+1}/{total}] SKIP (bad response)")
            continue

        _save_label(conn, art["id"], art["title"], label)
        labeled += 1

        house_short = label["house"].replace("High House ", "") if label["house"] != "None" else "None"
        rev = " [R]" if label.get("reversed") else ""
        print(f"  [{i+1}/{total}] {house_short}{rev}  ({label.get('confidence', 0):.0%})  — {art['title'][:60]}")

        if labeled % batch_size == 0:
            conn.commit()
            print(f"  --- committed {labeled} labels so far ---")

        time.sleep(delay)

    conn.commit()
    conn.close()
    print(f"\nDone. Labeled: {labeled}  Skipped: {skipped}  Total: {total}")


if __name__ == "__main__":
    run()
