import os
from dotenv import load_dotenv
from src.fetch.http import client

load_dotenv()

_KEY = os.environ.get("GUARDIAN_API_KEY", "")
_BASE = "https://content.guardianapis.com/search"
_SECTIONS = ["world", "politics", "business", "technology", "environment", "science", "society"]


def fetch_recent(days: int = 2, per_section: int = 50) -> list[dict]:
    if not _KEY:
        raise EnvironmentError("GUARDIAN_API_KEY not set in .env")

    articles = []
    for section in _SECTIONS:
        try:
            resp = client.get(_BASE, params={
                "api-key": _KEY,
                "section": section,
                "show-fields": "bodyText,headline",
                "page-size": per_section,
                "order-by": "newest",
                "from-date": _days_ago(days),
            })
            resp.raise_for_status()
        except Exception as e:
            print(f"  Guardian [{section}]: {e}")
            continue

        for item in resp.json().get("response", {}).get("results", []):
            fields = item.get("fields", {})
            body = fields.get("bodyText", "")
            headline = fields.get("headline", item.get("webTitle", ""))
            if not headline:
                continue
            articles.append({
                "id": item["id"],
                "url": item["webUrl"],
                "title": headline,
                "text": f"{headline}. {body[:250]}".strip(),
                "full_text": body[:4000],
                "section": section,
                "source": "guardian",
            })

    return articles


def _days_ago(n: int) -> str:
    from datetime import date, timedelta
    return (date.today() - timedelta(days=n)).isoformat()
