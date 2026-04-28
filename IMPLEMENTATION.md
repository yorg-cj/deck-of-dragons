# Implementation Plan — Hybrid Approach

## Overview

Three sequential phases. Phase 1 uses Claude API once to generate labeled training data. Phase 2 trains local classifiers on that data. Phase 3 is the permanent live system with no external AI dependency. You can run Phase 1 output as a working product immediately while Phase 2 and 3 are built underneath it.

```
Phase 1: Claude labels ~800 articles → SQLite training dataset
Phase 2: Train local classifiers on that dataset → .pkl model files
Phase 3: Live pipeline uses local models, GDELT, REBEL, and three news APIs
```

---

## Project Structure

```
deck-of-dragons/
├── data/
│   ├── training.db          # SQLite: labeled articles, user corrections
│   ├── models/              # Saved classifier .pkl files (Phase 2+)
│   └── cache/               # Daily reading JSON cache
├── src/
│   ├── fetch/
│   │   ├── guardian.py      # Guardian API — full article text, UK/center-left
│   │   ├── nyt.py           # NYT API — headlines + metadata, US perspective
│   │   ├── worldnews.py     # World News API — 210 countries, geographic spread
│   │   ├── sources.py       # Combines all three, deduplicates by URL
│   │   └── gdelt.py         # GDELT event + Goldstein fetcher
│   ├── bootstrap/
│   │   └── label.py         # Phase 1 only: Claude batch labeling script
│   ├── classify/
│   │   ├── house.py         # House classification (similarity → trained LR)
│   │   ├── title.py         # Title assignment (NER + CAMEO actor type)
│   │   ├── reversal.py      # Reversal detection (sentiment)
│   │   └── relationship.py  # Ally/opposed detection (GDELT + REBEL)
│   ├── train/
│   │   └── train.py         # Classifier training + evaluation
│   ├── ui/
│   │   ├── app.py           # Textual TUI app entry point
│   │   └── cards.py         # ASCII card rendering
│   └── pipeline.py          # Orchestrates fetch → classify → layout
├── pyproject.toml
├── .env                     # API keys (never commit)
└── CLAUDE.md
```

---

## Phase 1 — Bootstrap with Claude

**Goal:** Collect ~800 labeled article examples. This is the only time Claude is used. The output is a SQLite database that becomes the training dataset for Phase 2.

**Why 800?** Sentence transformer + logistic regression reliably reaches 85-90% accuracy around 100-200 examples per class. With 7 Houses and some imbalance expected, 800 total gives good coverage. More is better; 800 is the minimum target.

### 1a. Fetch Articles

Collect from three news sources with distinct editorial perspectives. Each source has different
strengths; together they reduce the monoculture problem.

**A note on training data and copyright:** Full article text is legally grey territory for ML
training. The safe practice throughout is to classify on `headline + first 300 characters` of
body text only. That content is clearly intended for display and is what GDELT, NYT, and World
News API provide anyway. Guardian's full body text is used only for the live reading display
and article links — not as training input to Claude.

---

**Guardian API** — the only free source with full article text; UK, center-left; strong on
environment, international affairs, society:

```python
# src/fetch/guardian.py
import httpx
import os

GUARDIAN_KEY = os.environ["GUARDIAN_API_KEY"]
BASE = "https://content.guardianapis.com/search"

SECTIONS = [
    "world", "politics", "business", "technology",
    "environment", "science", "society"
]

def fetch_recent(days: int = 7, per_section: int = 50) -> list[dict]:
    articles = []
    for section in SECTIONS:
        resp = httpx.get(BASE, params={
            "api-key": GUARDIAN_KEY,
            "section": section,
            "show-fields": "bodyText,headline",
            "page-size": per_section,
            "order-by": "newest",
        })
        for item in resp.json()["response"]["results"]:
            body = item["fields"].get("bodyText", "")
            articles.append({
                "id": item["id"],
                "url": item["webUrl"],
                "title": item["fields"]["headline"],
                "text": body[:300],        # first 300 chars for classification/training
                "full_text": body[:3000],  # full text stored separately for display only
                "section": section,
                "source": "guardian",
            })
    return articles
```

**NYT API** — free, no credit card, headlines + metadata only; US, center-left; strong on
finance, tech, and US foreign policy. 500 calls/day. Sign up at developer.nytimes.com.

```python
# src/fetch/nyt.py
import httpx
import os

NYT_KEY = os.environ["NYT_API_KEY"]
BASE = "https://api.nytimes.com/svc/search/v2/articlesearch.json"

NYT_QUERIES = [
    "geopolitics", "military", "sanctions", "diplomacy",
    "technology policy", "climate", "economy", "intelligence"
]

def fetch_recent(days: int = 3, per_query: int = 10) -> list[dict]:
    articles = []
    seen = set()
    for query in NYT_QUERIES:
        resp = httpx.get(BASE, params={
            "api-key": NYT_KEY,
            "q": query,
            "sort": "newest",
            "fl": "headline,abstract,web_url,section_name,pub_date",
        })
        for doc in resp.json().get("response", {}).get("docs", [])[:per_query]:
            url = doc["web_url"]
            if url in seen:
                continue
            seen.add(url)
            headline = doc["headline"].get("main", "")
            abstract = doc.get("abstract", "")
            articles.append({
                "id": url,
                "url": url,
                "title": headline,
                "text": f"{headline}. {abstract}"[:300],
                "full_text": None,  # NYT does not provide full text via free API
                "section": doc.get("section_name", ""),
                "source": "nyt",
            })
    return articles
```

**World News API** — 50 points/day (use sparingly); 210 countries, 6,000+ publications; best
geographic spread of any free option. No credit card. Sign up at worldnewsapi.com.

```python
# src/fetch/worldnews.py
import httpx
import os

WORLDNEWS_KEY = os.environ["WORLDNEWS_API_KEY"]
BASE = "https://api.worldnewsapi.com/search-news"

# Targeted queries to stretch the 50-point daily budget across domains
WORLDNEWS_QUERIES = [
    "military conflict", "economic sanctions", "climate environment",
    "artificial intelligence policy", "humanitarian crisis"
]

def fetch_recent(per_query: int = 5) -> list[dict]:
    """Fetch ~25 articles per day (5 per query × 5 queries = 25 points used)."""
    articles = []
    seen = set()
    for query in WORLDNEWS_QUERIES:
        resp = httpx.get(BASE, params={
            "api-key": WORLDNEWS_KEY,
            "text": query,
            "number": per_query,
            "language": "en",
            "sort": "publish-time",
            "sort-direction": "DESC",
        })
        for art in resp.json().get("news", []):
            url = art.get("url", "")
            if url in seen:
                continue
            seen.add(url)
            title = art.get("title", "")
            summary = art.get("summary", art.get("text", ""))[:200]
            articles.append({
                "id": url,
                "url": url,
                "title": title,
                "text": f"{title}. {summary}"[:300],
                "full_text": None,
                "section": query,
                "source": "worldnews",
            })
    return articles
```

**Combinator — deduplicate across all three sources:**

```python
# src/fetch/sources.py
from src.fetch.guardian import fetch_recent as guardian_fetch
from src.fetch.nyt import fetch_recent as nyt_fetch
from src.fetch.worldnews import fetch_recent as worldnews_fetch

def fetch_all(days: int = 2) -> list[dict]:
    """Fetch from all sources, deduplicate by URL."""
    all_articles = (
        guardian_fetch(days=days) +
        nyt_fetch(days=days) +
        worldnews_fetch()
    )
    seen = set()
    deduped = []
    for art in all_articles:
        if art["url"] not in seen:
            seen.add(art["url"])
            deduped.append(art)
    return deduped
```

**Source breakdown per day (approximate):**

| Source | Articles | Content | Perspective |
|---|---|---|---|
| Guardian | ~350 | Headline + full body | UK, center-left |
| NYT | ~80 | Headline + abstract | US, center-left |
| World News | ~25 | Headline + summary | 210 countries, global |
| **Total** | **~450** | | |

---

**GDELT** — event-coded news, already partially labeled by CAMEO:
```python
# src/fetch/gdelt.py
import httpx
import json

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

def fetch_gdelt_articles(query: str, days: int = 3) -> list[dict]:
    resp = httpx.get(GDELT_DOC_API, params={
        "query": query,
        "mode": "artlist",
        "maxrecords": 75,
        "timespan": f"{days}d",
        "format": "json",
    })
    articles = []
    for art in resp.json().get("articles", []):
        articles.append({
            "id": art["url"],
            "url": art["url"],
            "title": art["title"],
            "text": art.get("seendate", ""),  # GDELT gives less text; title is primary
            "source": "gdelt_doc",
        })
    return articles

def fetch_gdelt_events(actor1: str = None, actor2: str = None, days: int = 30) -> list[dict]:
    """Fetch GDELT event records with Goldstein scores for relationship detection."""
    import gdelt
    gd = gdelt.gdelt(version=2)
    # Returns a DataFrame with Actor1Name, Actor2Name, GoldsteinScale, EventCode, etc.
    results = gd.Search(
        date=days,
        table="events",
        output="df",
    )
    if actor1:
        results = results[results["Actor1Name"].str.contains(actor1, na=False)]
    if actor2:
        results = results[results["Actor2Name"].str.contains(actor2, na=False)]
    return results
```

### 1b. Store Articles in SQLite

```python
# data schema — run once to initialize
CREATE TABLE articles (
    id TEXT PRIMARY KEY,
    url TEXT,
    title TEXT,
    text TEXT,
    section TEXT,
    source TEXT,
    fetched_at TEXT
);

CREATE TABLE labels (
    article_id TEXT PRIMARY KEY,
    house TEXT,
    title TEXT,
    reversed INTEGER,       -- 0 or 1
    confidence REAL,
    key_signals TEXT,       -- JSON array of words
    label_source TEXT,      -- 'claude_bootstrap', 'user_confirmed', 'user_corrected'
    labeled_at TEXT,
    FOREIGN KEY (article_id) REFERENCES articles(id)
);
```

### 1c. Claude Batch Labeling Script

This is the one-time Claude usage. Uses the Batch API (50% cheaper, asynchronous):

```python
# src/bootstrap/label.py
import anthropic
import json
import sqlite3

SYSTEM_PROMPT = """
You label news articles for a geopolitical oracle system. Each article maps to one House
and one Title. Return JSON only — no prose, no explanation.

HOUSES (pick exactly one):
- High House War: armed conflict, military mobilization, weapons trade, troop deployment,
  defense alliances, battles, sieges, arms deals
- High House Coin: financial markets, economic sanctions, trade wars, central banking,
  corporate mergers, investment flows, currency manipulation, debt
- High House Shadow: intelligence operations, covert action, espionage, disinformation
  campaigns, propaganda, black budgets, assassination, cyber operations
- High House Life: public health, medicine, pandemic, environment, climate,
  humanitarian aid, food security, ecology
- High House Iron: technology dominance, AI development, semiconductor supply chains,
  infrastructure, manufacturing, energy systems, industrial capacity
- High House Words: media narratives, diplomatic statements, censorship, information
  warfare, international law, treaty negotiations, public perception campaigns
- High House Chains: sovereign debt, IMF conditions, military occupation, binding
  agreements, sanctions regimes, legal constraints on nations

TITLES — determine from the primary entity type in the article:
  Nation / military alliance / international org → The King, The Queen, The Knight, or The Army
  Corporation / industry / financial institution → The Merchant
  Named individual (person) → The Warlord (aggressive), The Assassin (covert),
                               The Magi (expert/advisor), The Herald (spokesperson)
  The Throne → apex power, the defining actor in this House right now
  The Weaver → entity primarily shaping narrative/perception

REVERSED — true if the House energy is distorted, blocked, corrupted, or suppressed:
  Examples: medicine weaponized (Life reversed), censorship victory (Words reversed),
  financial collapse (Coin reversed), intelligence exposed (Shadow reversed)

Return exactly:
{
  "house": "High House War",
  "title": "The Army",
  "reversed": false,
  "confidence": 0.91,
  "key_signals": ["troops", "NATO", "eastern flank", "deployment"]
}
"""

def create_batch_requests(articles: list[dict]) -> list[dict]:
    return [
        {
            "custom_id": article["id"],
            "params": {
                "model": "claude-haiku-4-5-20251001",  # cheapest model; task is structured enough
                "max_tokens": 200,
                "system": SYSTEM_PROMPT,
                "messages": [{
                    "role": "user",
                    "content": f"Title: {article['title']}\n\n{article['text'][:800]}"
                }]
            }
        }
        for article in articles
    ]

def run_bootstrap(db_path: str):
    conn = sqlite3.connect(db_path)
    client = anthropic.Anthropic()

    # Fetch unlabeled articles
    articles = conn.execute(
        """SELECT a.id, a.title, a.text FROM articles a
           LEFT JOIN labels l ON a.id = l.article_id
           WHERE l.article_id IS NULL"""
    ).fetchall()
    articles = [{"id": r[0], "title": r[1], "text": r[2]} for r in articles]

    print(f"Labeling {len(articles)} articles via Claude Batch API...")

    # Submit batch
    batch = client.messages.batches.create(
        requests=create_batch_requests(articles)
    )
    print(f"Batch submitted: {batch.id}")
    print("Check status with: python -m src.bootstrap.status <batch_id>")
    print("Results auto-saved when complete.")

def save_batch_results(batch_id: str, db_path: str):
    """Run this after the batch completes (check console.anthropic.com)."""
    client = anthropic.Anthropic()
    conn = sqlite3.connect(db_path)

    for result in client.messages.batches.results(batch_id):
        if result.result.type == "succeeded":
            try:
                label = json.loads(result.result.message.content[0].text)
                conn.execute(
                    """INSERT OR REPLACE INTO labels
                       (article_id, house, title, reversed, confidence, key_signals, label_source, labeled_at)
                       VALUES (?, ?, ?, ?, ?, ?, 'claude_bootstrap', datetime('now'))""",
                    (result.custom_id, label["house"], label["title"],
                     int(label["reversed"]), label["confidence"],
                     json.dumps(label["key_signals"]))
                )
            except (json.JSONDecodeError, KeyError):
                pass  # malformed responses are skipped; retry manually

    conn.commit()
    print(f"Labels saved to {db_path}")
```

**Cost estimate for bootstrap:** Using Haiku (cheapest model) at ~$0.25/MTok input:
- 800 articles × ~200 tokens each = ~160K tokens input
- 800 articles × ~80 tokens output = ~64K tokens output
- Total: roughly **$0.06**. Less than a cent per 10 articles.

---

## Phase 2 — Train Local Classifiers

Run once after the bootstrap labels are saved. Produces `.pkl` model files.

```python
# src/train/train.py
import sqlite3
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from pathlib import Path

def train_house_classifier(db_path: str, output_path: str = "data/models/house_classifier.pkl"):
    conn = sqlite3.connect(db_path)

    rows = conn.execute(
        """SELECT a.text, l.house, l.confidence
           FROM articles a JOIN labels l ON a.id = l.article_id
           WHERE l.confidence >= 0.80"""  # only high-confidence labels
    ).fetchall()

    texts  = [r[0][:1000] for r in rows]
    labels = [r[1] for r in rows]

    print(f"Training on {len(texts)} examples across {len(set(labels))} houses...")

    encoder = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = encoder.encode(texts, show_progress_bar=True)

    X_train, X_test, y_train, y_test = train_test_split(
        embeddings, labels, test_size=0.2, stratify=labels, random_state=42
    )

    clf = LogisticRegression(max_iter=1000, C=1.0)
    clf.fit(X_train, y_train)

    print(classification_report(y_test, clf.predict(X_test)))

    Path(output_path).parent.mkdir(exist_ok=True)
    with open(output_path, "wb") as f:
        pickle.dump({"classifier": clf, "encoder": encoder}, f)

    print(f"Model saved to {output_path}")
```

**When to retrain:** Any time you accumulate 50+ new user-confirmed or user-corrected labels. The feedback loop (Phase 3) writes to the same `labels` table with `label_source = 'user_confirmed'` or `'user_corrected'`. User corrections should be weighted more heavily — they represent disagreements with the model.

---

## Phase 3 — Live Pipeline

### 3a. House Classifier

Automatically falls back to cosine similarity if no trained model exists yet:

```python
# src/classify/house.py
import numpy as np
import pickle
from sentence_transformers import SentenceTransformer

ARCHETYPE_DESCRIPTIONS = {
    "High House War":    "armed conflict military troops weapons deployment battle force alliance",
    "High House Coin":   "financial markets economic sanctions trade investment currency debt bank",
    "High House Shadow": "intelligence espionage covert disinformation propaganda cyber secret",
    "High House Life":   "health medicine pandemic environment climate humanitarian food ecology",
    "High House Iron":   "technology AI semiconductor infrastructure manufacturing energy industry",
    "High House Words":  "media diplomacy narrative censorship treaty information communication",
    "High House Chains": "occupation debt IMF sanctions binding agreement legal control treaty",
}

class HouseClassifier:
    def __init__(self, model_path: str = None):
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        self.clf = None

        if model_path:
            try:
                with open(model_path, "rb") as f:
                    saved = pickle.load(f)
                self.clf = saved["classifier"]
                print("Using trained classifier.")
            except FileNotFoundError:
                print("No trained model found. Using cosine similarity fallback.")

        # Always compute archetype embeddings (used as fallback or cross-check)
        self.archetype_embeddings = {
            house: self.encoder.encode(desc)
            for house, desc in ARCHETYPE_DESCRIPTIONS.items()
        }

    def classify(self, text: str) -> dict:
        embedding = self.encoder.encode(text[:1000])

        # Cosine similarity scores (always computed — used as fallback + transparency)
        scores = {}
        for house, arch_emb in self.archetype_embeddings.items():
            score = float(np.dot(embedding, arch_emb) /
                         (np.linalg.norm(embedding) * np.linalg.norm(arch_emb)))
            scores[house] = round(score, 3)

        if self.clf is not None:
            proba = self.clf.predict_proba([embedding])[0]
            house = self.clf.classes_[np.argmax(proba)]
            confidence = float(np.max(proba))
            method = "trained_classifier"
        else:
            house = max(scores, key=scores.get)
            confidence = scores[house]
            method = "cosine_similarity"

        return {
            "house": house,
            "confidence": confidence,
            "method": method,
            "scores": scores,  # full breakdown — this is the auditable "why"
        }
```

### 3b. Title Assignment

Deterministic — no ML needed:

```python
# src/classify/title.py
import spacy

nlp = spacy.load("en_core_web_sm")

# CAMEO actor type codes → individual vs. collective
COLLECTIVE_CAMEO_TYPES = {"GOV", "MIL", "NGO", "IGO", "UNK"}
INDIVIDUAL_CAMEO_TYPES = {"ELITES", "LEADER"}

COLLECTIVE_TITLES = ["The King", "The Queen", "The Knight", "The Army"]
INDIVIDUAL_TITLES = ["The Warlord", "The Assassin", "The Magi", "The Herald", "The Merchant"]

def assign_title(article_text: str, house: str, cameo_actor_type: str = None) -> str:
    doc = nlp(article_text[:500])

    entity_types = [ent.label_ for ent in doc.ents]

    # Determine individual vs. collective from entity type
    has_person = "PERSON" in entity_types
    has_nation = "GPE" in entity_types
    has_org    = "ORG" in entity_types

    # CAMEO actor type overrides if available
    if cameo_actor_type in INDIVIDUAL_CAMEO_TYPES:
        is_individual = True
    elif cameo_actor_type in COLLECTIVE_CAMEO_TYPES:
        is_individual = False
    else:
        # Infer from NER: a named person is individual unless outweighed by org/nation
        is_individual = has_person and not (has_nation and has_org)

    # House-specific title logic
    if house == "High House Shadow":
        return "The Assassin" if is_individual else "The Weaver"
    if house == "High House Coin":
        return "The Merchant" if is_individual else "The Throne"
    if house == "High House War":
        return "The Warlord" if is_individual else "The Army"
    if house == "High House Words":
        return "The Herald" if is_individual else "The Weaver"
    if house == "High House Iron":
        return "The Magi" if is_individual else "The Merchant"
    if house == "High House Life":
        return "The Magi" if is_individual else "The King"
    if house == "High House Chains":
        return "The Assassin" if is_individual else "The Knight"

    return "The Throne"  # fallback
```

### 3c. Reversal Detection

```python
# src/classify/reversal.py
from transformers import pipeline

# Lightweight sentiment model (~67MB)
sentiment = pipeline("sentiment-analysis",
                     model="distilbert-base-uncased-finetuned-sst-2-english")

# House-specific reversal triggers — negative framing within the House's domain
REVERSAL_SIGNALS = {
    "High House Life":   ["weaponized", "suppressed", "denied", "collapse", "extinct", "poison"],
    "High House Words":  ["censored", "silenced", "propaganda", "banned", "suppressed", "misinformation"],
    "High House Coin":   ["crash", "collapse", "sanction", "blockade", "bankrupt", "freeze"],
    "High House Shadow": ["exposed", "leaked", "burned", "failed", "caught", "revealed"],
    "High House War":    ["defeated", "routed", "occupation", "surrender", "siege", "blockade"],
    "High House Iron":   ["banned", "sabotaged", "stolen", "embargo", "backdoor", "compromised"],
    "High House Chains": ["defaulted", "broken", "violated", "collapsed", "defied", "refused"],
}

def detect_reversal(text: str, house: str) -> dict:
    text_lower = text.lower()

    # Check for house-specific shadow signals
    signals = REVERSAL_SIGNALS.get(house, [])
    matched_signals = [s for s in signals if s in text_lower]

    # Overall sentiment of article
    result = sentiment(text[:512])[0]
    is_negative = result["label"] == "NEGATIVE" and result["score"] > 0.75

    reversed_card = bool(matched_signals) or is_negative

    return {
        "reversed": reversed_card,
        "sentiment": result["label"],
        "sentiment_score": round(result["score"], 3),
        "matched_signals": matched_signals,
    }
```

### 3d. Relationship Detection

```python
# src/classify/relationship.py
import numpy as np
from transformers import pipeline

rebel_extractor = pipeline(
    "text2text-generation",
    model="Babelscape/rebel-large",
    tokenizer="Babelscape/rebel-large",
)

def get_gdelt_relationship(actor1: str, actor2: str, events_df) -> dict | None:
    """Aggregate Goldstein scores between two actors from a GDELT events DataFrame."""
    mask = (
        (events_df["Actor1Name"].str.contains(actor1, na=False) &
         events_df["Actor2Name"].str.contains(actor2, na=False)) |
        (events_df["Actor1Name"].str.contains(actor2, na=False) &
         events_df["Actor2Name"].str.contains(actor1, na=False))
    )
    pair = events_df[mask]

    if len(pair) == 0:
        return None

    avg = float(pair["GoldsteinScale"].mean())
    return {
        "relationship": "allied" if avg > 1.5 else "opposed" if avg < -1.5 else "neutral",
        "goldstein_avg": round(avg, 2),
        "event_count": len(pair),
        "confidence": min(0.95, len(pair) / 15),
        "source": "gdelt_goldstein",
    }

def extract_rebel_relations(text: str) -> list[dict]:
    """Extract relation triplets from article text using REBEL."""
    output = rebel_extractor(
        text[:512],
        return_tensors=False,
        return_text=True,
    )
    raw = output[0]["generated_text"]

    # Parse REBEL's linearized triplet format
    relations = []
    for triplet in raw.split("<triplet>"):
        if not triplet.strip():
            continue
        try:
            subj = triplet.split("<subj>")[1].split("</subj>")[0].strip()
            obj  = triplet.split("<obj>")[1].split("</obj>")[0].strip()
            rel  = triplet.split("</obj>")[1].strip()
            relations.append({"subject": subj, "relation": rel, "object": obj})
        except IndexError:
            continue

    return relations

# Relation type → cooperative/conflictual valence mapping
COOPERATIVE_RELATIONS = {
    "member_of", "partner_of", "allied_with", "supported_by", "signed_agreement",
    "cooperated_with", "provided_aid_to", "endorsed", "funded_by",
}
CONFLICTUAL_RELATIONS = {
    "attacked", "sanctioned", "opposed", "criticized", "invaded", "threatened",
    "imposed_embargo", "expelled", "arrested", "blockaded",
}

def classify_relation_valence(relation: str) -> str:
    relation_lower = relation.lower().replace(" ", "_")
    if any(r in relation_lower for r in COOPERATIVE_RELATIONS):
        return "allied"
    if any(r in relation_lower for r in CONFLICTUAL_RELATIONS):
        return "opposed"
    return "neutral"
```

### 3e. Main Pipeline Orchestrator

```python
# src/pipeline.py
import json
from datetime import date
from pathlib import Path
from src.fetch.guardian import fetch_recent
from src.fetch.gdelt import fetch_gdelt_events
from src.classify.house import HouseClassifier
from src.classify.title import assign_title
from src.classify.reversal import detect_reversal
from src.classify.relationship import get_gdelt_relationship

CACHE_PATH = Path("data/cache")
house_clf = HouseClassifier(model_path="data/models/house_classifier.pkl")

def get_reading(force_refresh: bool = False) -> dict:
    cache_file = CACHE_PATH / f"{date.today()}.json"

    if cache_file.exists() and not force_refresh:
        return json.loads(cache_file.read_text())

    articles = fetch_recent(days=2)
    gdelt_events = fetch_gdelt_events(days=30)

    cards = []
    for article in articles[:40]:  # process top 40 articles
        classification = house_clf.classify(article["text"])
        if classification["confidence"] < 0.60:
            continue  # skip low-confidence classifications

        title = assign_title(article["text"], classification["house"])
        reversal = detect_reversal(article["text"], classification["house"])

        cards.append({
            "house": classification["house"],
            "title": title,
            "reversed": reversal["reversed"],
            "confidence": classification["confidence"],
            "scores": classification["scores"],
            "reversal_detail": reversal,
            "article": {
                "title": article["title"],
                "url": article["url"],
            },
        })

    # Deduplicate: keep highest-confidence card per House
    by_house = {}
    for card in cards:
        house = card["house"]
        if house not in by_house or card["confidence"] > by_house[house]["confidence"]:
            by_house[house] = card

    active_cards = list(by_house.values())

    # Build relationship map between active Houses
    relationships = []
    houses_in_play = [c["house"] for c in active_cards]
    for i, h1 in enumerate(houses_in_play):
        for h2 in houses_in_play[i+1:]:
            rel = get_gdelt_relationship(h1, h2, gdelt_events)
            if rel:
                relationships.append({"a": h1, "b": h2, **rel})

    reading = {
        "date": str(date.today()),
        "cards": active_cards,
        "relationships": relationships,
    }

    CACHE_PATH.mkdir(exist_ok=True)
    cache_file.write_text(json.dumps(reading, indent=2))

    return reading
```

---

## Phase 3 — The TUI

### Card Rendering

```python
# src/ui/cards.py
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

HOUSE_COLORS = {
    "High House War":    "red",
    "High House Coin":   "yellow",
    "High House Shadow": "purple",
    "High House Life":   "green",
    "High House Iron":   "blue",
    "High House Words":  "cyan",
    "High House Chains": "dark_orange",
}

HOUSE_SIGILS = {
    "High House War":    "⚔",
    "High House Coin":   "⚖",
    "High House Shadow": "◈",
    "High House Life":   "✦",
    "High House Iron":   "⚙",
    "High House Words":  "◉",
    "High House Chains": "⛓",
}

def render_card(card: dict, width: int = 20) -> Panel:
    house  = card["house"]
    title  = card["title"]
    rev    = card["reversed"]
    conf   = card["confidence"]
    sigil  = HOUSE_SIGILS.get(house, "?")
    color  = HOUSE_COLORS.get(house, "white")
    label  = house.replace("High House ", "")

    if rev:
        body = Text(justify="center")
        body.append(f"\n  {sigil}  \n", style=f"bold {color}")
        body.append(f"▼ {title} ▼\n", style=f"bold {color}")
        body.append(f"~ {label} ~\n", style=f"dim {color}")
        body.append(f"\n[REVERSED]\n", style="dim red")
        body.append(f"\n{conf:.0%}", style="dim")
        border_style = f"dim {color}"
    else:
        body = Text(justify="center")
        body.append(f"\n  {sigil}  \n", style=f"bold {color}")
        body.append(f"{title}\n", style=f"bold {color}")
        body.append(f"~ {label} ~\n", style=color)
        body.append(f"\n{conf:.0%}", style="dim")
        border_style = color

    return Panel(
        Align.center(body),
        width=width,
        border_style=border_style,
        padding=(0, 1),
    )
```

### The Textual App

```python
# src/ui/app.py
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Label, Button
from textual.containers import Horizontal, Vertical, Grid
from rich.columns import Columns
from src.pipeline import get_reading
from src.ui.cards import render_card

class DeckApp(App):
    CSS = """
    Screen { background: #0a0a0a; }
    #layout { align: center middle; height: 100%; }
    #articles { height: auto; margin-top: 1; }
    .article-link { color: $text-muted; }
    #feedback { dock: bottom; height: 3; }
    """

    BINDINGS = [
        ("d", "draw", "Draw"),
        ("r", "refresh", "Refresh"),
        ("c", "confirm", "Confirm reading"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.reading = None
        self.selected_card = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Vertical(
            Static(id="layout"),
            Static(id="articles"),
            id="main",
        )
        yield Footer()

    def action_draw(self):
        self.reading = get_reading()
        self.refresh_display()

    def action_refresh(self):
        self.reading = get_reading(force_refresh=True)
        self.refresh_display()

    def refresh_display(self):
        if not self.reading:
            return

        cards = self.reading["cards"]
        from rich.console import Console
        from rich import print as rprint

        # Render cards side by side
        rendered = [render_card(c) for c in cards]
        layout = self.query_one("#layout", Static)
        layout.update(Columns(rendered, equal=True, expand=True))

        # Article links below
        lines = []
        for card in cards:
            rev_marker = " [reversed]" if card["reversed"] else ""
            lines.append(
                f"[bold]{card['title']}, {card['house'].replace('High House ', '')}[/bold]{rev_marker}\n"
                f"  → {card['article']['title']}\n"
                f"  {card['article']['url']}\n"
            )
        self.query_one("#articles", Static).update("\n".join(lines))

    def action_confirm(self):
        """Save current reading classifications as confirmed training data."""
        if not self.reading:
            return
        from src.train.feedback import save_confirmed
        save_confirmed(self.reading["cards"])
        self.notify("Reading confirmed and saved as training data.")
```

---

## The Feedback Loop

```python
# src/train/feedback.py
import sqlite3
from datetime import datetime

def save_confirmed(cards: list[dict], db_path: str = "data/training.db"):
    conn = sqlite3.connect(db_path)
    for card in cards:
        conn.execute(
            """INSERT OR REPLACE INTO labels
               (article_id, house, title, reversed, confidence, key_signals,
                label_source, labeled_at)
               VALUES (?, ?, ?, ?, ?, '[]', 'user_confirmed', ?)""",
            (card["article"]["url"], card["house"], card["title"],
             int(card["reversed"]), card["confidence"],
             datetime.now().isoformat())
        )
    conn.commit()

def save_correction(article_url: str, correct_house: str, correct_title: str,
                    correct_reversed: bool, db_path: str = "data/training.db"):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT OR REPLACE INTO labels
           (article_id, house, title, reversed, confidence, key_signals,
            label_source, labeled_at)
           VALUES (?, ?, ?, ?, 1.0, '[]', 'user_corrected', ?)""",
        (article_url, correct_house, correct_title,
         int(correct_reversed), datetime.now().isoformat())
    )
    conn.commit()
```

---

## API Keys Required

All stored in `.env` (never commit this file):

```
ANTHROPIC_API_KEY=...      # Phase 1 bootstrap only — console.anthropic.com
GUARDIAN_API_KEY=...       # open-platform.theguardian.com — free, no credit card
NYT_API_KEY=...            # developer.nytimes.com — free, no credit card
WORLDNEWS_API_KEY=...      # worldnewsapi.com — free, no credit card
```

---

## Dependencies

```toml
# pyproject.toml
[project]
name = "deck-of-dragons"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.25.0",           # Phase 1 bootstrap only
    "httpx>=0.27.0",               # all news API calls
    "python-dotenv>=1.0",          # load .env
    "gdelt>=0.1.10",               # GDELT event fetching
    "sentence-transformers>=3.0",  # all-MiniLM-L6-v2
    "scikit-learn>=1.4",           # Logistic regression classifier
    "spacy>=3.7",                  # NER
    "en-core-web-sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl",
    "transformers>=4.40",          # REBEL, StanceBERTa, sentiment
    "torch>=2.2",                  # backend for transformers
    "textual>=0.61",               # TUI framework
    "rich>=13.7",                  # card rendering
]
```

---

## Timeline

| Week | Work |
|---|---|
| 1 | Project setup, Guardian + GDELT fetching, SQLite schema |
| 2 | Bootstrap script → run Claude batch labeling → save ~800 labels |
| 3 | House classifier training + evaluation; title assignment logic |
| 4 | Reversal detection; GDELT relationship pipeline |
| 5 | REBEL relation extraction for non-GDELT entities |
| 6 | Textual TUI — card rendering, layout, article links |
| 7 | Feedback loop UI (confirm/correct keybindings) |
| 8 | Polish, retrain with any accumulated user labels, web deploy test |

---

## Decision Points

**When to move from cosine similarity → trained classifier:**
The Phase 3 `HouseClassifier` automatically uses the trained model if `data/models/house_classifier.pkl` exists. You can start the TUI before Phase 2 is done — it falls back to cosine similarity. Train Phase 2 whenever you have 400+ labeled examples with confidence ≥ 0.80.

**When to retrain:**
Run `python -m src.train.train` any time you've accumulated 50+ new user-confirmed or user-corrected labels. User corrections (disagreements with the model) are worth more than confirmations — they directly address the model's weak spots.

**When to add REBEL:**
REBEL is heavy (~1.5GB). Start without it. Add it in Week 5 once the core House/Title/Reversal pipeline is working. For the first months, GDELT Goldstein covers the most important relationship pairs (nation-states).
