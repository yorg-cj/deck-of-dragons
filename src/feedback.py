"""
Feedback loop — write user-confirmed readings as training labels.

Called when the user presses 'c' in the TUI after reviewing a reading.
Each card in the reading becomes a high-quality 'user_confirmed' label
in the training DB, weighted more than bootstrap labels on the next retrain.
"""
import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent / "data" / "training.db"


def confirm_reading(reading: dict) -> int:
    """
    Write all cards in the reading as confirmed training labels.
    Skips cards whose article URL is not already in the articles table.
    Returns the number of labels written.
    """
    cards = reading.get("cards", [])
    if not cards:
        return 0

    conn = sqlite3.connect(_DB_PATH)
    written = 0

    for card in cards:
        url = card["article"]["url"]
        title = card["article"]["title"]
        house = card["house"]

        # Only label if the article is in the DB
        exists = conn.execute(
            "SELECT 1 FROM articles WHERE url = ?", (url,)
        ).fetchone()
        if not exists:
            continue

        conn.execute("""
            INSERT OR REPLACE INTO labels
                (article_id, house, title, reversed, confidence, key_signals, label_source)
            VALUES (?, ?, ?, ?, ?, '[]', 'user_confirmed')
        """, (
            url,
            house,
            title,
            int(card.get("reversed", False)),
            1.0,   # user-confirmed = maximum confidence
        ))
        written += 1

    conn.commit()
    conn.close()
    return written
