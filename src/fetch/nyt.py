import os
import time
from dotenv import load_dotenv
from src.fetch.http import client

load_dotenv()

_KEY = os.environ.get("NYT_API_KEY", "")
_BASE = "https://api.nytimes.com/svc/search/v2/articlesearch.json"

_QUERIES = [
    "geopolitics military conflict",
    "economic sanctions trade war",
    "intelligence espionage",
    "climate environment health",
    "technology AI semiconductor",
    "diplomacy treaty international",
    "debt IMF occupation",
]


def fetch_recent(days: int = 2, per_query: int = 8) -> list[dict]:
    if not _KEY:
        raise EnvironmentError("NYT_API_KEY not set in .env")

    articles = []
    seen: set[str] = set()

    for query in _QUERIES:
        try:
            resp = client.get(_BASE, params={
                "api-key": _KEY,
                "q": query,
                "sort": "newest",
            })
            resp.raise_for_status()
        except Exception as e:
            print(f"  NYT [{query}]: {e}")
            time.sleep(1)
            continue

        for doc in resp.json().get("response", {}).get("docs", [])[:per_query]:
            url = doc.get("web_url", "")
            if not url or url in seen:
                continue
            seen.add(url)

            headline = (doc.get("headline") or {}).get("main", "") or ""
            abstract = doc.get("abstract") or ""
            text = f"{headline}. {abstract}".strip(". ")

            articles.append({
                "id": url,
                "url": url,
                "title": headline,
                "text": text[:300],
                "full_text": None,
                "section": doc.get("section_name", ""),
                "source": "nyt",
            })

        time.sleep(6.5)  # NYT rate limit: 10 calls/min = 1 per 6s

    return articles


def _days_ago(n: int) -> str:
    from datetime import date, timedelta
    return (date.today() - timedelta(days=n)).isoformat()
