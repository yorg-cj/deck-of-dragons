# The Classifier Approach — An Alternative to LLM Analysis

## Why This Document Exists

The default plan uses Claude API to read the news and decide which cards are in play. This document explores a different path: building a **local classifier pipeline** that makes those decisions without sending anything to an external AI. The reasons to care about this:

1. **Learning**: understanding how classification actually works, mechanically
2. **Environment**: local inference costs a fraction of the energy of LLM API calls
3. **Transparency**: a classifier's decisions are auditable in a way LLM output genuinely is not

---

## What a Classifier Is (Plain Terms)

A classifier is a function that takes text as input and outputs a category label. Given the sentence *"NATO allies have agreed to deploy additional troops to the eastern flank,"* a classifier should output something like `High House War`.

The difference between classifier types is *how* they make that decision:

- **Rule-based**: if the text contains the word "troops" → War. Simple, brittle.
- **Statistical (TF-IDF + Logistic Regression)**: learned weights for thousands of words; words like "troops," "deployed," "flank" have high positive weight toward War. Fully transparent.
- **Semantic (Sentence Transformers)**: converts text to a point in high-dimensional space; measures which House archetype description is geometrically closest to that point.
- **Zero-shot (BART-NLI)**: reframes classification as a true/false question: "Does this text entail that it is about armed conflict?" Yes/no confidence score drives the label.

Each trades off interpretability, accuracy, training data requirements, and compute differently.

---

## The Four Approaches, Compared

### Approach 1: TF-IDF + Logistic Regression

**What it does:** Converts each article into a bag of weighted word counts (TF-IDF), then applies learned coefficients to predict a House.

**How transparent it is:** Maximally transparent. You can literally print the top features per class:

```
High House War — top positive features:
  troops: +3.21
  military: +2.87
  deployed: +2.44
  ceasefire: +2.11
  ...

High House War — top negative features (things that push away from War):
  inflation: -1.92
  earnings: -1.74
```

This is a genuine mechanical explanation. Not a story — actual coefficients.

**Limitations:**
- Cannot understand context. "The government supports conflict resolution" and "Conflict erupted at the government summit" both score similarly because the words overlap.
- Word order is invisible to it. Bag-of-words.
- Geopolitical language is messy. Financial sanctions and military sanctions look the same.
- Needs ~200-500 labeled examples per class to be reliable.

**Compute:** Runs on any CPU instantly. Inference takes microseconds.

---

### Approach 2: Sentence Transformers + Cosine Similarity

**What it does:** Uses a pre-trained neural model (22MB, runs on CPU) to convert text into a 384-dimensional vector. You also convert your archetype descriptions into vectors. The article is assigned to whichever House description it's geometrically closest to.

**What "geometrically closest" means:** Imagine all possible text meaning-space collapsed into a sphere. Articles about military conflict cluster near each other. Articles about financial markets cluster near each other. The sentence transformer learned this geometry from millions of examples. You don't train it — you just use the geometry it already knows.

**How transparent it is:** You get a similarity score between 0 and 1 for each House. "This article is 0.87 similar to High House War, 0.41 similar to High House Coin, 0.23 similar to High House Words." The score is a genuine geometric measurement, not generated text. You can see *by how much* it preferred one House over another.

**What you control:** The archetype descriptions. If you write "High House War: armed conflict, military mobilization, weapons trade, troop deployment, defense alliances" — that description is what the comparison is measured against. You can tune these descriptions.

**Accuracy with zero training data:** 80-85%. Improves to 85-90% if you add a thin logistic regression layer on top (trained on ~200 examples).

**Recommended model:** `all-MiniLM-L6-v2` — 22MB, runs on CPU, fast enough for real-time use.

**Compute:** CPU-friendly. Inference takes milliseconds per article.

---

### Approach 3: Zero-Shot Classification (BART-MNLI)

**What it does:** Frames classification as a Natural Language Inference problem. For each candidate label, it asks: does this article *entail* that it is about "armed conflict and military power"? The model was trained to detect textual entailment and returns a confidence that the entailment holds.

**How transparent it is:** You get confidence scores per label. Similar to sentence transformers in what's visible to you. The difference is the underlying mechanism — entailment detection rather than geometric similarity.

**Critical weakness — prompt brittleness:** Research shows accuracy can swing by more than 10 percentage points based on minor label wording changes. "High House War" vs. "armed conflict" vs. "military action" can produce meaningfully different results for the same article. This means you'd need to carefully engineer and test label descriptions, and your results depend on those choices in ways that are hard to predict.

**Model size:** 406MB. Requires more compute than sentence transformers.

**Verdict for this project:** The brittleness problem makes this less reliable than sentence transformers for our use case. More compute for less reliability.

---

### Approach 4: GDELT's Built-In Classification (Free Pre-Labeled Data)

This isn't a classifier you build — it's a classification system that already exists and is free.

**What GDELT does:** Every 15 minutes, GDELT scans global news coverage and codes each event using the **CAMEO system** — a framework used by political scientists to categorize international events. Events get codes like:

- `190` — Use of conventional military force
- `172` — Impose economic sanctions
- `036` — Express intent to cooperate
- `051` — Demonstrate or rally
- `1724` — Impose embargo, boycott, or trade restriction

GDELT also tags **who** the actors are: Government, Military, Political Opposition, NGO, and so on. And it distinguishes whether Actor1 is a nation-state, a sub-national entity, or an organization.

**Why this matters for us:** GDELT has been coding events since 1979. There are over a billion coded event records, updated every 15 minutes, completely free. This is effectively **pre-labeled training data** for geopolitical classification that we didn't have to create.

**CAMEO → Houses mapping (rough):**

| CAMEO codes | Maps to |
|---|---|
| 18-19 (coerce, fight, military force) | High House War |
| 16-17 (reduce relations, impose embargo) | High House Chains |
| 061-063 (economic cooperation, aid) | High House Coin |
| 040-046 (diplomatic engagement) | High House Words |
| 012-014 (appeals on health, environment) | High House Life |

**The actor type fields** (`Actor1Type1Code`, `Actor2Type1Code`) distinguish:
- `GOV` — Government
- `MIL` — Military
- `NGO` — Non-governmental organization
- `BUS` — Business (corporation)
- `COP` — Political opposition
- `REB` — Rebel / insurgent group

This is our individual vs. collective signal. A `MIL` actor → collective title. A named individual (person name in `Actor1Name`) → individual title.

---

## The Recommended Pipeline for This Project

Rather than picking one approach, combine them:

```
News Article
     │
     ▼
[spaCy NER]
Extract named entities:
- GPE (country/nation) → collective signal
- ORG (organization) → collective signal
- PERSON (individual) → individual signal
     │
     ▼
[GDELT lookup]
Does GDELT already have this event coded?
- If yes: use CAMEO code as primary House signal
- If no: proceed to classification
     │
     ▼
[Sentence Transformer — all-MiniLM-L6-v2]
Compute cosine similarity to each House archetype description
Return ranked scores with similarity values
     │
     ▼
[Title Assignment]
Combine entity type (individual/collective) + House
to select the appropriate Title within the House
     │
     ▼
[Reversal Detection]
Sentiment analysis on the article tone:
- Negative/destructive framing → consider reversed card
- Example: "Life reversed" if health article is about
  weaponization, suppression, or system collapse
     │
     ▼
[Relationship Detection]
Which entities appear in the same articles?
Which GDELT Actor1/Actor2 pairs show conflict vs. cooperation?
Build an adjacency map: entity → House → ally/opposed
     │
     ▼
Output: cards[], reversed[], relationships[], source_articles[]
```

---

## What "Why" Looks Like With This Pipeline vs. LLM

**With Claude:**
> "This article maps to High House War because it describes military mobilization by a major power, which represents the archetypal Warlord energy — an individual commanding force being projected across borders."

This is generated text. It's plausible, it sounds right, but it is the output of a next-token predictor. There is no verified logical chain. You can't audit it.

**With this pipeline:**
```
Article: "NATO commanders ordered additional troops to Poland"

spaCy NER:
  - NATO → ORG (collective)
  - Poland → GPE (nation/place)

GDELT lookup:
  - Event coded: 192 (Use of conventional military force)
  - Actor1Type: MIL (military)

Sentence Transformer scores:
  - High House War:    0.91
  - High House Chains: 0.34
  - High House Words:  0.22
  - (others < 0.20)

Assigned: The Army of High House War (collective title, military actor)
Confidence: 0.91

Reasoning chain:
  - Entity type: ORG/MIL → collective title
  - GDELT CAMEO 192: military force event
  - Semantic similarity to War archetype: 0.91
  - Similarity gap to next-closest House: 0.57
```

The second explanation is a ledger, not a narrative. Every step is checkable. You can disagree with any individual step and trace it. This is what the user meant about Claude's "why" being predictive text — even when Claude gives reasons, those reasons are themselves generated, not computed from inspectable state.

---

## Relationship Detection — How It Works Locally

Relationship detection is three operations chained together:

1. **Entity pair identification** — which two entities are in a relationship?
2. **Relation type extraction** — what *is* the relationship? (armed conflict, signed treaty, sanctions, supply deal)
3. **Valence** — is that relationship cooperative (+) or conflictual (−)?

Claude does all three in one pass using its attention mechanism and patterns learned from training. Here's how to reproduce each step locally.

### Step 1: GDELT Goldstein Scale (Nation-State Pairs)

The **Goldstein scale** is a pre-computed valence score attached to every GDELT event, from −10 (maximum conflict) to +10 (maximum cooperation). Every event record already has `Actor1`, `Actor2`, and a relationship polarity baked in.

```python
# Pseudocode
events = gdelt.query(actor1="USA", actor2="CHN", days=30)
relationship_score = average(e.goldstein for e in events)
# -3.2 → primarily conflictual  →  opposed cards in layout
# +1.8 → net cooperative       →  allied cards in layout
```

For nation-state relationships, this is largely solved. GDELT has been computing it every 15 minutes since 1979. You're reading a measurement, not generating an inference.

**Limitation:** Goldstein is event-type-only — a 10-person protest and a 10,000-person protest get the same score. And GDELT skews toward political/military/diplomatic events; financial or technological relationships are underrepresented.

### Step 2: REBEL (For Corporations, Individuals, Non-GDELT Events)

REBEL (`Babelscape/rebel-large`) is a Seq2Seq model that extracts relation triples from raw text. It recognizes 200+ relation types derived from Wikidata.

```python
from transformers import pipeline

extractor = pipeline('text2text-generation', model='Babelscape/rebel-large')
text = "Elon Musk's company secured a $1.4B defense contract with the Pentagon."
# REBEL output:
# (Elon Musk's company, awarded_contract, Pentagon)
```

REBEL won't output "allied" directly. It outputs the factual relation ("awarded_contract," "signed_agreement," "supported," "sanctioned"). You map those to your ally/opposed taxonomy:

```
awarded_contract → cooperative
sanctioned       → conflictual
signed_agreement → cooperative
attacked         → conflictual
```

**Benchmarks:** 76.65 F1 on CoNLL04, 93.4 F1 on NYT. State-of-the-art for relation extraction.

### Step 3: Valence Check (StanceBERTa)

When REBEL's relation type is ambiguous, use a stance model to confirm polarity:

```python
from transformers import pipeline

stance = pipeline("text-classification", model="eevvgg/StanceBERTa")
result = stance("Elon Musk's company secured a $1.4B defense contract with the Pentagon.")
# → {'label': 'positive', 'score': 0.87}
# positive = cooperative = ally signal
```

### Full Relationship Pipeline

```
Entity pair (from NER)
        │
        ├── Both are nations/states?
        │     → GDELT Goldstein aggregate (reliable, pre-computed)
        │
        └── At least one is org/individual?
              → REBEL relation extraction on article text
              → Map relation type → (allied / opposed / neutral)
              → If ambiguous: StanceBERTa valence check
              → Aggregate across N articles for that pair
```

**Output per entity pair:**
```json
{
  "entity_a": "High House War",
  "entity_b": "High House Coin",
  "relationship": "allied",
  "confidence": 0.82,
  "signal_source": "gdelt_goldstein",
  "goldstein_avg": 3.4,
  "event_count": 14
}
```

### What Still Can't Be Replicated Cleanly

**Multi-hop inference.** Claude can read ten articles and conclude: "A arms B, B fights C, C is allied with D, therefore A and D are de facto opposed." REBEL extracts sentence-level triplets. Chaining those into indirect relationships requires additional graph logic that adds real engineering complexity.

For this project's use case — placing cards as allied or opposed in the reading layout — the coarseness is probably acceptable. The cases where multi-hop matters (a hedge fund indirectly financing a conflict through a chain of intermediaries) are exactly the cases where the article links alongside the card carry the most weight. The reader does the inference.

---

## Environmental Comparison (Honest Numbers)

| Approach | Energy per 100 articles | Relative cost |
|---|---|---|
| Claude API (Sonnet) | ~300 Wh | Baseline |
| Local BART zero-shot | ~10-50 Wh | ~10-30x cheaper |
| Sentence Transformers (CPU) | ~0.5-2 Wh | ~150-600x cheaper |
| TF-IDF + Logistic Regression | <0.1 Wh | ~3,000x cheaper |
| GDELT lookup (no inference) | ~0.01 Wh | ~30,000x cheaper |

For personal use (a few draws per day), the environmental difference between Claude API and sentence transformers is small in absolute terms. For a deployed web app serving thousands of users, it becomes significant.

The larger environmental argument for classifiers: **locality**. The energy for your local inference comes from wherever your laptop/server is powered. You can choose green energy. LLM API energy comes from data center infrastructure you don't control.

---

## Training Data: Where It Comes From

You don't have to label thousands of articles by hand. Several bootstrapping strategies:

**Option 1 — GDELT as ground truth (recommended starting point)**
Pull GDELT events with CAMEO codes, map CAMEO → Houses per the table above, use those as labeled examples. You can have thousands of training examples from day one without labeling anything manually.

**Option 2 — Active learning feedback loop**
Build a simple confirm/correct interface into the terminal app. When a card is drawn, you can press `c` to confirm the classification or enter a correction. These corrections become training examples. Over time the model learns your specific judgments.

**Option 3 — Bootstrap via LLM once (not ongoing)**
Use Claude to generate ~500 synthetic labeled examples at project start ("here are 500 news headlines, assign each a House and Title"). Use those to fine-tune a local classifier. After that one-time use, the LLM is no longer in the loop. The cost is a few cents, done once.

---

## What You're Building, Concretely

| Component | What It Is | Size | Cost |
|---|---|---|---|
| `all-MiniLM-L6-v2` | Sentence transformer model | 22MB | Free |
| `en_core_web_sm` | spaCy NER model | ~12MB | Free |
| GDELT API | Pre-labeled event data | Cloud, free | Free |
| Guardian API | Full article text | Cloud, free | Free |
| Scikit-learn | TF-IDF + LR (interpretability layer) | Small | Free |
| SQLite | Cache + training data store | Tiny | Free |

Total: ~35MB of models, no ongoing API costs, runs on any modern laptop.

---

## Honest Summary of Tradeoffs

| | Classifier Pipeline | Claude API |
|---|---|---|
| **House/Title accuracy** | 82-90% | 90-95% |
| **Relationship detection** | Hard, incomplete | Easy |
| **Explanation quality** | Mechanical, auditable | Narrative, generated |
| **Setup time** | 2-3 weeks | 2-3 days |
| **Ongoing cost** | $0 | ~$3/year with caching |
| **Environmental** | Very low | Moderate (with caching) |
| **Privacy** | Complete (local) | Headlines sent to Anthropic |
| **Improvable over time** | Yes (active learning) | Requires prompt tuning |
| **Relationship detection** | Weak without extra work | Strong |

The classifier path takes longer to build and does some things worse. What it does better — interpretability, privacy, environmental cost, and the philosophical honesty of *not* dressing up statistics as insight — are real advantages that depend on what you value in the project.

---

## Suggested Implementation Order

1. Set up GDELT + Guardian API fetching
2. Implement spaCy NER for entity extraction
3. Implement sentence transformer House classification with archetype descriptions
4. Map CAMEO codes as a cross-check signal
5. Build title assignment logic (individual vs. collective from NER + CAMEO actor type)
6. Add reversal detection (sentiment on article framing)
7. Add relationship detection (GDELT Actor1/Actor2 pairs with event valence)
8. Add feedback loop UI (confirm/correct → training data)
9. Periodically retrain with accumulated labeled data
