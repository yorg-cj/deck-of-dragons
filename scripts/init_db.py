"""Initialize the SQLite database. Run once before anything else."""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "training.db"


def init(db_path: Path = DB_PATH):
    db_path.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(db_path)

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id          TEXT PRIMARY KEY,
            url         TEXT NOT NULL,
            title       TEXT NOT NULL,
            text        TEXT NOT NULL,      -- headline + first ~300 chars (used for training/classification)
            full_text   TEXT,               -- full body where available (Guardian only; display only)
            section     TEXT,
            source      TEXT NOT NULL,      -- 'guardian' | 'nyt' | 'worldnews' | 'gdelt_doc'
            fetched_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS labels (
            article_id      TEXT PRIMARY KEY,
            house           TEXT NOT NULL,
            title           TEXT NOT NULL,
            reversed        INTEGER NOT NULL DEFAULT 0,
            confidence      REAL NOT NULL,
            key_signals     TEXT NOT NULL DEFAULT '[]',   -- JSON array
            label_source    TEXT NOT NULL,                -- 'claude_bootstrap' | 'user_confirmed' | 'user_corrected'
            labeled_at      TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (article_id) REFERENCES articles(id)
        );

        CREATE INDEX IF NOT EXISTS idx_labels_house        ON labels(house);
        CREATE INDEX IF NOT EXISTS idx_labels_label_source ON labels(label_source);
        CREATE INDEX IF NOT EXISTS idx_articles_source     ON articles(source);
        CREATE INDEX IF NOT EXISTS idx_articles_fetched    ON articles(fetched_at);
    """)

    conn.commit()
    conn.close()
    print(f"Database initialised at {db_path}")


if __name__ == "__main__":
    init()
