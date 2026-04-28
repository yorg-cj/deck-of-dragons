"""
GDELT integration via direct Doc API calls. No gdelt Python library required.

Two signals:
  query_actor_tone()        — average tone between two actors (relationship strength)
  query_house_volume_trend() — rising/falling coverage for a House domain (WANING/EMERGING)
"""
import time
from src.fetch.http import client

_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# House-targeted queries for article fetching (unchanged from original)
_DOC_QUERIES = [
    "military attack war troops",
    "sanctions embargo trade restriction",
    "intelligence espionage covert",
    "climate health pandemic humanitarian",
    "technology semiconductor AI",
    "media censorship propaganda diplomacy",
    "debt occupation treaty",
]

# Domain keywords per House — used for volume trend detection
_HOUSE_QUERIES: dict[str, str] = {
    "High House War":    "military conflict war troops battle",
    "High House Coin":   "financial markets economy trade sanctions",
    "High House Shadow": "intelligence espionage surveillance covert leak",
    "High House Life":   "health environment climate humanitarian pandemic",
    "High House Iron":   "technology semiconductor AI infrastructure energy",
    "High House Words":  "media diplomacy censorship narrative propaganda",
    "High House Chains": "debt treaty occupation agreement binding",
}


def fetch_articles(days: int = 2, per_query: int = 15) -> list[dict]:
    """Fetch article titles from GDELT Doc API. No key required."""
    articles = []
    seen: set[str] = set()

    for query in _DOC_QUERIES:
        try:
            resp = client.get(_DOC_API, params={
                "query":      query,
                "mode":       "artlist",
                "maxrecords": per_query,
                "timespan":   f"{days * 24}h",
                "format":     "json",
            }, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"  GDELT doc [{query}]: {e}")
            continue

        for art in resp.json().get("articles", []):
            url   = art.get("url", "")
            title = art.get("title", "")
            if not url or not title or url in seen:
                continue
            seen.add(url)
            articles.append({
                "id":        url,
                "url":       url,
                "title":     title,
                "text":      title[:300],
                "full_text": None,
                "section":   query,
                "source":    "gdelt_doc",
            })

    return articles


def _gdelt_get(params: dict, retries: int = 3, backoff: float = 5.0) -> dict | None:
    """GET the GDELT API with simple retry on 429."""
    for attempt in range(retries):
        try:
            resp = client.get(_DOC_API, params=params, timeout=20)
            if resp.status_code == 429:
                if attempt < retries - 1:
                    time.sleep(backoff * (attempt + 1))
                    continue
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt == retries - 1:
                raise
    return None


def query_actor_tone(actor_a: str, actor_b: str, days: int = 7) -> dict | None:
    """
    Query GDELT for articles mentioning both actors together.
    Returns average tone and derived relationship, or None if insufficient data.

    Tone scale (GDELT): roughly -10 (hostile) to +10 (cooperative).
    Mapped to relationship: opposed < -1.5, allied > 1.0, else neutral.
    """
    try:
        data = _gdelt_get({
            "query":    f"{actor_a} {actor_b}",
            "mode":     "timelinetone",
            "timespan": f"{days}d",
            "format":   "json",
        })
        if data is None:
            return None
        timeline = data.get("timeline", [])
        if not timeline:
            return None

        pts = timeline[0].get("data", [])
        if len(pts) < 3:   # too few data points to be meaningful
            return None

        values = [pt["value"] for pt in pts if pt.get("value") is not None]
        if not values:
            return None

        avg_tone = sum(values) / len(values)

        if avg_tone < -1.5:
            relationship = "opposed"
        elif avg_tone > 1.0:
            relationship = "allied"
        else:
            relationship = "neutral"

        confidence = round(min(0.90, len(values) / 168), 2)  # 168 = 7d × 24h

        return {
            "relationship":   relationship,
            "tone_avg":       round(avg_tone, 3),
            "data_points":    len(values),
            "confidence":     confidence,
            "source":         "gdelt_tone",
        }

    except Exception as e:
        print(f"  GDELT tone [{actor_a} / {actor_b}]: {e}")
        return None


def query_house_volume_trend(house: str, days: int = 7) -> dict | None:
    """
    Query GDELT volume for a House's domain keywords over the past N days.
    Compares first half vs second half of the window to detect rising/falling coverage.

    Returns:
        trend       — 'rising' | 'falling' | 'stable'
        trend_ratio — second_half_avg / first_half_avg  (>1 = rising)
    """
    query = _HOUSE_QUERIES.get(house)
    if not query:
        return None

    try:
        data = _gdelt_get({
            "query":    query,
            "mode":     "timelinevolinfo",
            "timespan": f"{days}d",
            "format":   "json",
        })
        if data is None:
            return None
        timeline = data.get("timeline", [])
        if not timeline:
            return None

        data = timeline[0].get("data", [])
        if len(data) < 6:
            return None

        values = [pt["value"] for pt in data if pt.get("value") is not None]
        mid    = len(values) // 2
        first  = sum(values[:mid]) / mid
        second = sum(values[mid:]) / (len(values) - mid)

        if first == 0:
            return None

        ratio = second / first
        if ratio > 1.15:
            trend = "rising"
        elif ratio < 0.85:
            trend = "falling"
        else:
            trend = "stable"

        return {
            "trend":       trend,
            "trend_ratio": round(ratio, 3),
            "source":      "gdelt_volume",
        }

    except Exception as e:
        print(f"  GDELT volume [{house}]: {e}")
        return None


def query_all_house_trends(houses: list[str], delay: float = 0.5) -> dict[str, dict]:
    """Query volume trends for all active Houses. Returns {house: trend_dict}."""
    trends = {}
    for house in houses:
        result = query_house_volume_trend(house)
        if result:
            trends[house] = result
        time.sleep(delay)
    return trends
