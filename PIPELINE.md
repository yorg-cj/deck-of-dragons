# How Deck of Dragons Works: Full Pipeline

## Step 1 — Fetch the News

Every day, the system pulls articles from four sources:

| Source | What it provides | Limit |
|---|---|---|
| **Guardian API** | Full article text, UK/international perspective | 5,000 calls/day |
| **NYT API** | Headlines + abstracts, US perspective | 500 calls/day |
| **WorldNews API** | Geographic diversity across 210 countries | 50 points/day |
| **GDELT** | Free global event database, no API key needed | Unlimited |

Articles are deduplicated by URL. Guardian comes first, so if the same story appears in multiple sources, the Guardian version (with full text) is kept.

---

## Step 2 — Convert Articles to Numbers (Embeddings)

Before any classification can happen, articles need to be converted into a format a computer can compare mathematically.

The model used is **`all-MiniLM-L6-v2`** (from Sentence Transformers). It reads a piece of text and outputs a list of 384 numbers — called an **embedding** or **vector**. Think of it as a point in 384-dimensional space. Articles about similar topics land near each other; articles about unrelated things land far apart.

This is done for every article, and also for each House's description (e.g., "armed conflict, military power, arms trade" for High House War).

---

## Step 3 — Classify Articles into Houses

This is where each article gets assigned to one of the seven High Houses.

Two methods are available, with an automatic quality check:

### Method A — Zero-Shot (always available)
Compare the article's embedding to each House's description embedding using **cosine similarity** — essentially measuring the angle between two vectors in space. An angle of 0° = identical meaning; 90° = completely unrelated. The article goes to whichever House it points closest toward.

No training required. Works out of the box but is less precise.

### Method B — Trained Classifier (used if quality is good enough)
A **Logistic Regression** model is trained on articles that have already been labeled (either by the bootstrap Claude labeling run, or confirmed by the user). Logistic Regression learns a boundary in that 384-dimensional space: "articles on *this* side → War, articles on *that* side → Coin."

**Quality gate:** The trained model is only used if its **cross-validation F1 score** is ≥ 0.75. F1 is a 0–1 score that balances precision (was the prediction correct?) and recall (did it find all the right articles?). Cross-validation means the model is tested on held-out data it never trained on, so the score reflects real-world accuracy rather than just memorization.

If the model scores below 0.75, the system falls back to zero-shot automatically.

---

## Step 4 — Determine Reversal

A reversed card means a House is active but operating in distorted or shadow form (e.g., High House Life reversed = medicine weaponized, humanitarian aid blocked).

Reversal uses **SST-2**, a BERT-based sentiment model originally trained on movie reviews. It reads an article and outputs:
- A label: `POSITIVE` or `NEGATIVE`
- A confidence score: 0.0 to 1.0

**The rule:** A card is reversed only if the sentiment is negative *and* the confidence is above **0.94**. The threshold is set high deliberately — most geopolitical news reads as negative even when a House is operating normally. Only very strong negative signal triggers reversal.

---

## Step 5 — Assign Positions (the Spread)

Each card gets placed in the reading layout:

```
         [ ASCENDING ]
              |
[ WANING ]--[CENTER]--[ EMERGING ]
              |
         [ FOUNDATION ]

[ WILD ]              [ WILD ]
```

Position is determined by two signals from GDELT:

**Volume trends (`timelinevolinfo`):** GDELT tracks how many articles are published about a topic over time. The system compares article volume in the first half of the week vs. the second half. If volume is up >15% → EMERGING. If down >15% → WANING. If flat → stable.

**Actor tone (`timelinetone`):** GDELT scores the emotional tone of articles mentioning two actors together, on a scale from very negative to very positive. Below -1.5 average = opposed. Above +1.0 = allied. This is used to detect tension between Houses.

**Then positions are assigned:**

| Position | Logic |
|---|---|
| **CENTER** | Highest confidence card |
| **ASCENDING** | Opposed to CENTER (via GDELT tone), or second highest confidence |
| **FOUNDATION** | Flattest GDELT trend (most structurally stable), or next highest confidence |
| **WANING** | Falling GDELT volume, or lowest confidence |
| **EMERGING** | Rising GDELT volume, or second lowest confidence |
| **WILD** | Up to 2 remaining cards that don't fit named positions |

If GDELT rate-limits or returns no data, the confidence-based fallbacks ensure all 7 cards still get placed.

---

## Step 6 — Render the Reading

The final reading is a JSON file (`docs/reading.json`) written daily by GitHub Actions. It contains the 7 cards, each with:
- House, title, reversed flag
- Confidence score (shown as the `▓░` bar — how strongly the article matched the House)
- Position in the spread
- The source article that generated it

The static site (`index.html` + `app.js`) fetches this JSON and renders the card layout. No server needed.

---

## The Confidence Bar

```
▓▓▓▓▓░░░  62%
```

This is the raw cosine similarity (or logistic regression probability) turned into a visual. Higher = the article's language strongly matched that House's domain. Lower = a weaker or more ambiguous match. It's not a prediction accuracy score — it's a signal strength indicator for that particular card.
