"""
Combines all news sources into a single deduplicated article list.
Guardian is the primary source (full text). NYT and WorldNews add
editorial diversity. GDELT adds multilingual global coverage.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

from src.fetch import guardian, nyt, worldnews, gdelt

DB_PATH = Path(__file__).parent.parent.parent / "data" / "training.db"


def fetch_all(days: int = 2, save: bool = True) -> list[dict]:
    """
    Fetch from all sources, deduplicate by URL, optionally persist to DB.
    Articles already in the DB are skipped to avoid duplicate labeling.
    """
    print("Fetching articles...")

    all_articles: list[dict] = []

    print("  Guardian...", end=" ", flush=True)
    try:
        g = guardian.fetch_recent(days=days)
        print(f"{len(g)} articles")
        all_articles.extend(g)
    except Exception as e:
        print(f"skipped ({e})")

    print("  NYT...", end=" ", flush=True)
    try:
        n = nyt.fetch_recent(days=days)
        print(f"{len(n)} articles")
        all_articles.extend(n)
    except Exception as e:
        print(f"skipped ({e})")

    print("  World News...", end=" ", flush=True)
    try:
        w = worldnews.fetch_recent()
        print(f"{len(w)} articles")
        all_articles.extend(w)
    except Exception as e:
        print(f"skipped ({e})")

    print("  GDELT...", end=" ", flush=True)
    try:
        gd = gdelt.fetch_articles(days=days)
        print(f"{len(gd)} articles")
        all_articles.extend(gd)
    except Exception as e:
        print(f"skipped ({e})")

    # Deduplicate by URL, preserving first occurrence (Guardian prioritised by fetch order)
    seen: set[str] = set()
    deduped: list[dict] = []
    for art in all_articles:
        if art["url"] not in seen:
            seen.add(art["url"])
            deduped.append(art)

    print(f"\n{len(deduped)} unique articles from {len(all_articles)} total fetched.")

    if save:
        _save_to_db(deduped)

    return deduped


def _save_to_db(articles: list[dict]):
    if not DB_PATH.exists():
        return
    conn = sqlite3.connect(DB_PATH)
    new_count = 0
    for art in articles:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO articles
                   (id, url, title, text, full_text, section, source, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (art["id"], art["url"], art["title"], art["text"],
                 art.get("full_text"), art.get("section", ""), art["source"],
                 datetime.now().isoformat())
            )
            if conn.total_changes > new_count:
                new_count = conn.total_changes
        except sqlite3.Error:
            pass
    conn.commit()
    conn.close()
    print(f"Saved {new_count} new articles to database.")
