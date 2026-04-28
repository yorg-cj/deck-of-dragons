"""
Reversal detection — determines if a House card should appear reversed.
A reversed card means the House is active but distorted, blocked,
suppressed, or operating in shadow form.

Uses two signals:
  1. House-specific shadow keywords in the article text  (primary gate)
  2. Overall article sentiment (secondary boost only, very high threshold)

Keyword match is required to trigger reversal at normal confidence.
Sentiment alone can only trigger at an extremely high threshold (>0.94),
since SST-2 (movie-review model) reads most journalistic news as negative.
"""
from transformers import pipeline as hf_pipeline

_sentiment = None


def _get_sentiment():
    global _sentiment
    if _sentiment is None:
        # Note: this model was trained on movie reviews (SST-2).
        # It handles obvious negative framing but is weak on neutral
        # journalistic tone. The keyword signals carry more weight here.
        _sentiment = hf_pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            truncation=True,
            max_length=512,
        )
    return _sentiment


# Shadow signals per House — words that suggest the House energy is
# distorted, blocked, weaponised, or collapsing
_SHADOW_SIGNALS: dict[str, list[str]] = {
    "High House War": [
        "war crime", "atrocity", "massacre", "occupation", "siege", "blockade",
        "cluster munition", "chemical weapon", "civilian casualty", "scorched earth",
    ],
    "High House Coin": [
        "crash", "collapse", "default", "bankrupt", "freeze", "seizure",
        "ponzi", "fraud", "manipulation", "embezzle", "sanction", "blockade",
    ],
    "High House Shadow": [
        "exposed", "leaked", "burned", "blown cover", "caught", "revealed",
        "intelligence failure", "whistleblower", "defector", "double agent",
    ],
    "High House Life": [
        "weaponized", "denied", "suppressed", "blockade", "famine", "genocide",
        "extinct", "ecocide", "poisoned", "contaminated", "outbreak uncontrolled",
    ],
    "High House Iron": [
        "banned", "sabotaged", "stolen", "embargo", "backdoor", "compromised",
        "monopoly", "patent troll", "surveillance", "addiction", "outage",
    ],
    "High House Words": [
        "censored", "silenced", "banned", "propaganda", "misinformation",
        "disinformation", "press freedom", "journalist killed", "blackout",
    ],
    "High House Chains": [
        "defaulted", "violated", "collapsed", "defied", "refused", "expelled",
        "sanctions broken", "occupation resistance", "uprising", "revolt",
    ],
}


def detect(text: str, house: str) -> dict:
    """
    Returns:
        reversed         — bool
        confidence       — 0.0 to 1.0
        matched_signals  — list of triggered shadow keywords
        sentiment        — 'POSITIVE' | 'NEGATIVE'
        sentiment_score  — model confidence
    """
    text_lower = text.lower()
    signals = _SHADOW_SIGNALS.get(house, [])
    matched = [s for s in signals if s in text_lower]

    sentiment_result = _get_sentiment()(text[:512])[0]
    sentiment_negative = sentiment_result["label"] == "NEGATIVE"
    sentiment_score    = sentiment_result["score"]

    # Sentiment alone only triggers at very high confidence to avoid
    # the SST-2 bias toward marking all news articles as negative.
    strong_negative = sentiment_negative and sentiment_score > 0.94

    reversed_card = bool(matched) or strong_negative

    # Confidence scales with how many signals fired
    if matched and sentiment_negative:
        confidence = min(0.95, 0.60 + len(matched) * 0.10)
    elif matched:
        confidence = min(0.85, 0.50 + len(matched) * 0.10)
    elif strong_negative:
        confidence = round(sentiment_score * 0.55, 3)   # capped — sentiment alone is weak signal
    else:
        confidence = 0.0

    return {
        "reversed": reversed_card,
        "confidence": round(confidence, 3),
        "matched_signals": matched,
        "sentiment": sentiment_result["label"],
        "sentiment_score": round(sentiment_score, 3),
    }
