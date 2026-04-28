"""
Fetch a large historical batch of articles for training purposes.
Uses wider date ranges and higher per-source limits than the daily reading.

Run:
    python3 scripts/fetch_training_batch.py

Guardian:  30 days × 7 sections × 200 articles = up to 1,400
GDELT:     30 days × 7 queries  × 50  articles = up to 350
NYT:       30 days × 7 queries  (rate-limited, ~45s total)
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.fetch import gdelt, guardian, nyt
from src.fetch.sources import DB_PATH, _save_to_db


def fetch_batch() -> None:
    all_articles: list[dict] = []
    seen: set[str] = set()

    def add(arts: list[dict]) -> int:
        added = 0
        for a in arts:
            if a["url"] not in seen:
                seen.add(a["url"])
                all_articles.append(a)
                added += 1
        return added

    print("=== Training batch fetch (30-day lookback) ===\n")

    print("Guardian (30d, 200/section)...", end=" ", flush=True)
    try:
        arts = guardian.fetch_recent(days=30, per_section=200)
        n = add(arts)
        print(f"{n} new")
    except Exception as e:
        print(f"failed: {e}")

    print("GDELT (30d, 50/query)...", end=" ", flush=True)
    try:
        arts = gdelt.fetch_articles(days=30, per_query=50)
        n = add(arts)
        print(f"{n} new")
    except Exception as e:
        print(f"failed: {e}")

    print("NYT (30d)...", end=" ", flush=True)
    try:
        arts = nyt.fetch_recent(days=30)
        n = add(arts)
        print(f"{n} new")
    except Exception as e:
        print(f"failed: {e}")

    print(f"\nTotal unique articles fetched: {len(all_articles)}")

    # Filter to only articles not already in DB
    conn = sqlite3.connect(DB_PATH)
    existing = {r[0] for r in conn.execute("SELECT url FROM articles").fetchall()}
    conn.close()

    new_articles = [a for a in all_articles if a["url"] not in existing]
    print(f"New to DB (not seen before): {len(new_articles)}")

    if new_articles:
        _save_to_db(new_articles)
        print(f"Saved {len(new_articles)} articles to training DB.")
    else:
        print("Nothing new to save.")

    # Summary of DB state
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    labeled = conn.execute("SELECT COUNT(*) FROM labels").fetchone()[0]
    conn.close()
    print(f"\nDB totals — articles: {total}  labeled: {labeled}  unlabeled: {total - labeled}")


if __name__ == "__main__":
    fetch_batch()
