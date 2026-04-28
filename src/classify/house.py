"""
House classification using sentence transformer cosine similarity.
Falls back to cosine similarity if no trained model exists yet (Phase 2+).
Every classification returns the full score breakdown — this is the auditable 'why'.
"""
import pickle
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

_MODEL_PATH = Path(__file__).parent.parent.parent / "data" / "models" / "house_classifier.pkl"

# Archetype descriptions define the semantic centre of each House.
# Tuning these strings is how you adjust classification behaviour.
ARCHETYPES: dict[str, str] = {
    "High House War": (
        "armed conflict military mobilization troops deployment warfare combat operations "
        "military strikes battle siege insurgency terrorism weapons trade arms deals "
        "defense alliances naval operations air strikes ground forces casualties"
    ),
    "High House Coin": (
        "financial markets economic sanctions trade war central banking corporate mergers "
        "investment flows currency manipulation debt inflation stock market hedge funds "
        "IMF World Bank tariffs commerce economic policy GDP recession fiscal monetary"
    ),
    "High House Shadow": (
        "intelligence operations covert action espionage disinformation propaganda "
        "black budgets assassination cyber operations surveillance secret services "
        "whistleblowers leaks dark money influence operations psyops hacking spies"
    ),
    "High House Life": (
        "public health medicine pandemic environment climate change humanitarian aid "
        "food security ecology vaccines WHO biodiversity pollution renewable energy "
        "disaster relief famine disease outbreak clean water poverty health crisis"
    ),
    "High House Iron": (
        "technology dominance AI development semiconductor supply chains infrastructure "
        "manufacturing energy systems industrial capacity tech giants innovation automation "
        "robotics data centers chips patents space technology digital transformation industry"
    ),
    "High House Words": (
        "media narratives diplomatic statements censorship information warfare "
        "international law treaty negotiations public perception journalism propaganda "
        "press freedom social media UN speeches cultural influence soft power narrative "
        "misinformation rhetoric discourse communication"
    ),
    "High House Chains": (
        "sovereign debt IMF conditions military occupation binding agreements sanctions "
        "regimes legal constraints colonial legacy reparations war crimes tribunals ICC "
        "WTO disputes trade agreements occupation territory controlled annexed blockade"
    ),
}

HOUSES = list(ARCHETYPES.keys())


class HouseClassifier:
    def __init__(self):
        self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
        self._trained_clf = None
        self._archetype_embeddings: dict[str, np.ndarray] = {}

        # Pre-compute archetype embeddings once at startup
        texts = list(ARCHETYPES.values())
        embeddings = self._encoder.encode(texts, show_progress_bar=False)
        for house, emb in zip(ARCHETYPES.keys(), embeddings):
            self._archetype_embeddings[house] = emb

        self._label_encoder = None
        _QUALITY_GATE = 0.75  # minimum CV F1 macro to prefer trained model over zero-shot

        # Load trained classifier if available and above quality threshold (Phase 2+)
        if _MODEL_PATH.exists():
            try:
                with open(_MODEL_PATH, "rb") as f:
                    bundle = pickle.load(f)
                cv_f1 = bundle.get("cv_f1_macro", 0.0)
                if cv_f1 >= _QUALITY_GATE:
                    self._trained_clf   = bundle["classifier"]
                    self._label_encoder = bundle["label_encoder"]
                    print(f"HouseClassifier: using trained model (CV F1={cv_f1:.3f}).")
                else:
                    print(f"HouseClassifier: trained model CV F1={cv_f1:.3f} below {_QUALITY_GATE} gate — using zero-shot.")
            except Exception:
                pass

    def classify(self, text: str) -> dict:
        """
        Returns:
            house       — assigned House name
            confidence  — score for the assigned house (0-1)
            scores      — full {house: score} breakdown for all 7 houses
            method      — 'trained_classifier' or 'cosine_similarity'
        """
        embedding = self._encoder.encode(text[:800], show_progress_bar=False)

        # Always compute cosine similarity scores (transparency + fallback)
        scores: dict[str, float] = {}
        for house, arch_emb in self._archetype_embeddings.items():
            norm = np.linalg.norm(embedding) * np.linalg.norm(arch_emb)
            scores[house] = round(float(np.dot(embedding, arch_emb) / norm), 3) if norm else 0.0

        if self._trained_clf is not None and self._label_encoder is not None:
            try:
                proba = self._trained_clf.predict_proba([embedding])[0]
                house = self._label_encoder.inverse_transform([int(np.argmax(proba))])[0]
                confidence = round(float(np.max(proba)), 3)
                return {"house": house, "confidence": confidence, "scores": scores, "method": "trained_classifier"}
            except Exception:
                pass  # fall through to cosine similarity

        house = max(scores, key=scores.get)
        return {"house": house, "confidence": scores[house], "scores": scores, "method": "cosine_similarity"}


# Module-level singleton — loaded once, reused across all classifications
_classifier: HouseClassifier | None = None


def classify(text: str) -> dict:
    global _classifier
    if _classifier is None:
        _classifier = HouseClassifier()
    return _classifier.classify(text)
