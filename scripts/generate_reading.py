"""
Generate today's reading and write it to docs/reading.json.
Called by the GitHub Actions daily workflow.

Run locally:
    python3 scripts/generate_reading.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline import get_reading

docs_dir = Path(__file__).parent.parent / "docs"
docs_dir.mkdir(exist_ok=True)

print("Generating reading...")
reading = get_reading(force_refresh=True)

out = docs_dir / "reading.json"
out.write_text(json.dumps(reading, indent=2))
print(f"Written to {out}")
print(f"  date:  {reading['date']}")
print(f"  cards: {len(reading['cards'])}")
