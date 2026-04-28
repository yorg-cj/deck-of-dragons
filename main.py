"""Entry point — run with: python main.py"""


def _prewarm_models():
    """Load all ML models in the main thread before Textual starts.
    Prevents 'bad value(s) in fds_to_keep' errors from PyTorch/spaCy
    forking subprocesses inside worker threads."""
    print("Loading models...", end=" ", flush=True)
    import src.classify.house as _h
    _h.classify("warmup")

    import src.classify.reversal as _r
    _r._get_sentiment()

    import spacy
    try:
        spacy.load("en_core_web_sm")
    except OSError:
        pass

    print("ready.")


if __name__ == "__main__":
    _prewarm_models()
    from src.ui.app import DeckApp
    DeckApp().run()
