"""
Train a Logistic Regression classifier on bootstrap labels.

Run:
    python3 -m src.train.train

Saves model to: data/models/house_classifier.pkl
Reports cross-validation accuracy and per-class breakdown.
"""
import json
import pickle
import sqlite3
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import LabelEncoder

_DB_PATH    = Path(__file__).parent.parent.parent / "data" / "training.db"
_MODEL_DIR  = Path(__file__).parent.parent.parent / "data" / "models"
_OUT_PATH   = _MODEL_DIR / "house_classifier.pkl"
_ENCODER    = "all-MiniLM-L6-v2"


def _load_labeled_articles(conn: sqlite3.Connection) -> tuple[list[str], list[str]]:
    rows = conn.execute("""
        SELECT a.text, l.house
        FROM labels l
        JOIN articles a ON a.id = l.article_id
        WHERE l.house != 'None'
          AND a.text IS NOT NULL
          AND a.text != ''
    """).fetchall()
    texts  = [r[0] for r in rows]
    labels = [r[1] for r in rows]
    return texts, labels


def run() -> None:
    conn = sqlite3.connect(_DB_PATH)
    texts, labels = _load_labeled_articles(conn)
    conn.close()

    print(f"Loaded {len(texts)} labeled examples across {len(set(labels))} Houses")

    print(f"Encoding with {_ENCODER}...")
    encoder = SentenceTransformer(_ENCODER)
    X = encoder.encode(texts, show_progress_bar=True, batch_size=64)
    y = np.array(labels)

    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    print("\nCross-validating (5-fold stratified)...")
    clf = LogisticRegression(max_iter=1000, C=4.0, class_weight="balanced")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(clf, X, y_enc, cv=cv, scoring="f1_macro")
    print(f"  F1 macro: {scores.mean():.3f} ± {scores.std():.3f}")

    print("\nFitting final model on all data...")
    clf.fit(X, y_enc)

    print("\nPer-class report:")
    y_pred = clf.predict(X)
    print(classification_report(y_enc, y_pred, target_names=le.classes_, digits=2))

    cv_f1 = round(float(scores.mean()), 3)

    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    bundle = {
        "classifier":    clf,
        "label_encoder": le,
        "encoder_name":  _ENCODER,
        "cv_f1_macro":   cv_f1,
        "n_examples":    len(texts),
    }
    with open(_OUT_PATH, "wb") as f:
        pickle.dump(bundle, f)

    print(f"Model saved → {_OUT_PATH}  (CV F1: {cv_f1:.3f})")


if __name__ == "__main__":
    run()
