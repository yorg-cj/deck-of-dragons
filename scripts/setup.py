"""
First-run setup: download all required models so the first `draw` doesn't hang silently.
Run once after `pip install -e .`
"""
import sys


def download_spacy():
    print("Downloading spaCy model (en_core_web_sm)...")
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "spacy", "download", "en_core_web_sm"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr}")
    else:
        print("  Done.")


def download_sentence_transformer():
    print("Downloading sentence transformer (all-MiniLM-L6-v2, ~22MB)...")
    from sentence_transformers import SentenceTransformer
    SentenceTransformer("all-MiniLM-L6-v2")
    print("  Done.")


def download_sentiment_model():
    print("Downloading sentiment model (distilbert SST-2, ~67MB)...")
    from transformers import pipeline
    pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
    print("  Done.")


def download_rebel():
    # REBEL is ~1.5GB — skip by default, download explicitly when ready
    print("Skipping REBEL download (1.5GB). Run with --rebel to include it.")


if __name__ == "__main__":
    include_rebel = "--rebel" in sys.argv

    download_spacy()
    download_sentence_transformer()
    download_sentiment_model()

    if include_rebel:
        print("Downloading REBEL relation extractor (Babelscape/rebel-large, ~1.5GB)...")
        from transformers import pipeline
        pipeline("text2text-generation", model="Babelscape/rebel-large")
        print("  Done.")
    else:
        download_rebel()

    print("\nSetup complete. Run `python scripts/init_db.py` next.")
