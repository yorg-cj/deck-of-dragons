# Deck of Dragons — Project Brief

## Concept

A real-world political oracle inspired by the Malazan Deck of Dragons. Fetches current news events, maps them to archetypal cards via AI, and renders an ASCII card reading in a terminal interface. Cards never name specific entities — they show only archetypes (e.g., "The Warlord, High House War"). Accompanying article links provide context for why each card appeared.

The core mechanic is **role-mapping**: the same card slot is filled by whoever is currently playing that role in world events.

---

## Design Decisions (Resolved)

| Question | Decision |
|---|---|
| Scope | Global reading only (for now) |
| Refresh | Live fetch every draw; minimum daily cache |
| Card text | Clearly labeled archetype name — the puzzle is identifying who fills the role |
| Reversed cards | Yes — indicates a House active in distorted/blocked/shadow form |
| Cards per reading | 7 (one per House; only active Houses appear) |
| Master of the Deck | No (deferred) |
| Deployment target | Local first, web deployment planned |

---

## The Deck Structure

### Seven High Houses

| House | Domain |
|---|---|
| High House War | Armed conflict, military power, arms trade |
| High House Coin | Financial power, economic coercion, sanctions |
| High House Shadow | Intelligence, covert ops, disinformation |
| High House Life | Health, environment, humanitarian action |
| High House Iron | Technology, industry, infrastructure |
| High House Words | Media, narrative control, diplomacy |
| High House Chains | Debt, binding agreements, occupation, control |

### Titles Within Each House

| Title | Archetype | Type |
|---|---|---|
| The Throne | Apex power in the domain | Either |
| The King / The Queen | Sovereign collective (nation, bloc) | Collective |
| The Knight | Military/enforcement arm | Collective |
| The Warlord | Aggressive individual commander | Individual |
| The Merchant | Corporate or trade actor | Either |
| The Assassin | Covert individual operator | Individual |
| The Herald | Voice, media, spokesperson | Either |
| The Weaver | Narrative manipulator, spin | Either |
| The Army | Massed organized force | Collective |
| The Magi | Technocrat, expert, hidden advisor | Individual |

**Collectives** (Nations, Orgs, Corporations) map to collective titles.
**Individuals** map to individual titles.

### Reversed Cards

A reversed card means the House is active but operating in a distorted, blocked, or shadow form.

Examples:
- High House Life reversed: medicine weaponized, environmental destruction, humanitarian aid denied
- High House Words reversed: censorship, propaganda victory, narrative collapse
- High House Coin reversed: sanctions, financial blockade, market crash
- High House Shadow reversed: intelligence failure, exposed operation, whistleblower moment

Visual indicator: `▼` marker on card frame; flavor text shifts to reflect shadow meaning.

### Unaligned Cards

Forces outside the house structure: pandemics, natural disasters, viral movements, singular contrarians, technologies reshaping power without belonging to any house. Appear as wild influences at the edges of the reading.

---

## Reading Layout

A 7-card spread. Only Houses currently "in play" appear — a quiet week may show 4 cards; a turbulent week all 7.

Cards are arranged spatially. Proximity = alliance; opposition = conflict.

```
         [ ASCENDING ]
              |
[ WANING ]--[CENTER]--[ EMERGING ]
              |
         [ FOUNDATION ]

[ WILD ]              [ WILD ]
```

- **Center**: The dominant House right now
- **Crossing/Ascending**: The primary opposing force
- **Waning**: A House whose influence is fading
- **Emerging**: A House rising in relevance
- **Foundation**: The underlying structural force
- **Wild slots**: Unaligned cards, if any

Cards from opposing Houses placed across from each other = in tension.
Cards from allied Houses placed near each other = coordinated.

---

## Technical Stack

| Component | Tool |
|---|---|
| Language | Python 3.11+ |
| TUI Framework | Textual (supports web mode — same codebase for terminal and browser) |
| Terminal Styling | Rich |
| News — primary | Guardian API (full text, UK/center-left, 5,000 calls/day) |
| News — secondary | NYT API (headlines + abstract, US perspective, 500 calls/day, free) |
| News — tertiary | World News API (210 countries, geographic diversity, 50 points/day, free) |
| Events + relationships | GDELT (Goldstein scale, CAMEO coding, free, no key) |
| House classification | Sentence Transformers + Logistic Regression (local, no API) |
| Relationship detection | GDELT Goldstein aggregate + REBEL relation extraction (local) |
| Bootstrap labeling | Claude API — Haiku, used once to generate training data (~$0.06) |
| Card Art | ASCII via Rich panels |
| Caching | Local JSON/SQLite cache; one global reading refreshed daily |

### Data Flow

```
User: draw
  → Check cache (is today's reading fresh?)
    → If yes: render cached reading
    → If no:
        → Fetch headlines (Guardian API + GDELT)
        → Send to Claude: map events → Houses/Titles/relationships → JSON
        → Parse: cards[], reversed[], articles[], relationships[]
        → Cache result
        → Render ASCII card layout in Textual TUI
        → Display article links per card
```

### Cost Model

Claude Sonnet pricing makes caching essential:
- One reading ≈ ~2,000 tokens in + ~1,000 out ≈ $0.009
- Daily personal use: ~$3/year
- Deployed app: cache one global reading per day; all users share it — cost stays fixed at ~$3/year regardless of user count

### Web Deployment Path

Textual has a built-in web serve mode (`textual serve`). The same Python codebase renders in the browser as a terminal-aesthetic interface. No separate frontend rewrite needed for initial web deployment. Scale beyond that would move to FastAPI backend + xterm.js or custom frontend.

---

## API Keys Required

- `ANTHROPIC_API_KEY` — console.anthropic.com (used once for bootstrap; new accounts get free credits)
- `GUARDIAN_API_KEY` — open-platform.theguardian.com (free, no credit card, 5,000 calls/day)
- `NYT_API_KEY` — developer.nytimes.com (free, no credit card, 500 calls/day)
- `WORLDNEWS_API_KEY` — worldnewsapi.com (free, no credit card, 50 points/day)
- GDELT — no key required (fully open)

---

## Project Status

Design phase complete. Ready to begin implementation.

### Next Steps
1. Set up project structure and dependencies
2. Implement news fetching (Guardian + GDELT)
3. Design Claude prompt for House/Title/relationship mapping
4. Build card rendering (ASCII art via Rich panels)
5. Build Textual TUI layout with spatial card arrangement
6. Add caching layer
7. Add article links display
8. Web deployment via Textual serve mode
