import os
from dotenv import load_dotenv
from src.fetch.http import client

load_dotenv()

_KEY = os.environ.get("WORLDNEWS_API_KEY", "")
_BASE = "https://api.worldnewsapi.com/search-news"

# Five queries × 5 articles = 25 points/day (half the free budget; leaves room for future use)
_QUERIES = [
    "military conflict war",
    "economic sanctions finance",
    "climate environment humanitarian",
    "artificial intelligence technology",
    "diplomacy occupation treaty",
]


def fetch_recent(per_query: int = 5) -> list[dict]:
    if not _KEY:
        raise EnvironmentError("WORLDNEWS_API_KEY not set in .env")

    articles = []
    seen: set[str] = set()

    for query in _QUERIES:
        try:
            resp = client.get(_BASE, params={
                "api-key": _KEY,
                "text": query,
                "number": per_query,
                "language": "en",
                "sort": "publish-time",
                "sort-direction": "DESC",
            })
            resp.raise_for_status()
        except Exception as e:
            print(f"  WorldNews [{query}]: {e}")
            continue

        for art in resp.json().get("news", []):
            url = art.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)

            title = art.get("title", "")
            summary = art.get("summary", art.get("text", ""))[:200]
            text = f"{title}. {summary}".strip(". ")

            articles.append({
                "id": url,
                "url": url,
                "title": title,
                "text": text[:300],
                "full_text": None,
                "section": query,
                "source": "worldnews",
            })

    return articles
