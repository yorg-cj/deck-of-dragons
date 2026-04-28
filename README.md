# Deck of Dragons

A real-world political oracle inspired by the Malazan Book of the Fallen. Fetches current news, maps events to archetypal cards using local ML models, and renders a seven-card spread — one per High House. Cards never name specific people or nations. They show only the role: *The Warlord, High House War*. The puzzle is identifying who plays it today.

Live site: **[yorg-cj.github.io/deck-of-dragons](https://yorg-cj.github.io/deck-of-dragons)**

The reading updates daily via GitHub Actions. The web frontend is a static site — no server required.

---

## Running Locally (Terminal App)

**Requirements:** Python 3.11+

```bash
# Install dependencies
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-deploy.txt
python -m spacy download en_core_web_sm

# Set API keys (copy and fill in)
cp .env.example .env

# Run
python main.py
```

Type `draw` at the prompt to generate a reading.

### API Keys

| Key | Where to get it | Required |
|---|---|---|
| `GUARDIAN_API_KEY` | open-platform.theguardian.com | Yes |
| `NYT_API_KEY` | developer.nytimes.com | Optional |
| `WORLDNEWS_API_KEY` | worldnewsapi.com | Optional |
| `ANTHROPIC_API_KEY` | console.anthropic.com | Optional (bootstrap/AI review only) |

---

## How It Works

See [PIPELINE.md](PIPELINE.md) for a plain-language explanation of the full pipeline: news fetching, embeddings, house classification, reversal detection, and position assignment.

---

## The Seven High Houses

| House | Domain |
|---|---|
| High House War | Armed conflict, military power, arms trade |
| High House Coin | Financial power, economic coercion, sanctions |
| High House Shadow | Intelligence, covert ops, disinformation |
| High House Life | Health, environment, humanitarian action |
| High House Iron | Technology, industry, infrastructure |
| High House Words | Media, narrative control, diplomacy |
| High House Chains | Debt, binding agreements, occupation, control |
