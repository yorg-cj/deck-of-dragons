'use strict';

const HOUSE_COLORS = {
  "High House War":    "var(--war)",
  "High House Coin":   "var(--coin)",
  "High House Shadow": "var(--shadow)",
  "High House Life":   "var(--life)",
  "High House Iron":   "var(--iron)",
  "High House Words":  "var(--words)",
  "High House Chains": "var(--chains)",
};

const HOUSE_SIGILS = {
  "High House War":    "⚔",
  "High House Coin":   "⚖",
  "High House Shadow": "◈",
  "High House Life":   "✦",
  "High House Iron":   "⚙",
  "High House Words":  "◉",
  "High House Chains": "⛓",
};

const POSITION_LABELS = {
  "CENTER":     "THE DOMINANT",
  "ASCENDING":  "THE OPPOSING",
  "FOUNDATION": "THE FOUNDATION",
  "WANING":     "IN RETREAT",
  "EMERGING":   "RISING",
  "WILD":       "UNALIGNED",
};

const POSITION_CSS_CLASS = {
  "CENTER":     "pos-center",
  "ASCENDING":  "pos-ascending",
  "FOUNDATION": "pos-foundation",
  "WANING":     "pos-waning",
  "EMERGING":   "pos-emerging",
};

function confidenceBar(confidence, width = 8) {
  const filled = Math.round(confidence * width);
  return "▓".repeat(filled) + "░".repeat(width - filled);
}

function formatDate(dateStr) {
  const d = new Date(dateStr + "T12:00:00Z");
  return d.toLocaleDateString("en-GB", {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
    timeZone: "UTC",
  });
}

function buildCard(card) {
  const house   = card.house;
  const color   = HOUSE_COLORS[house] || "var(--text)";
  const sigil   = HOUSE_SIGILS[house]  || "?";
  const label   = house.replace("High House ", "").toUpperCase();
  const pos     = card.position || "WILD";
  const posLabel = POSITION_LABELS[pos] || pos;
  const conf    = card.confidence || 0;
  const rev     = card.reversed;

  const el = document.createElement("div");
  el.className = "card" + (rev ? " reversed" : "");
  el.style.setProperty("--house-color", color);

  el.innerHTML = `
    <div class="card-reversed-label">${rev ? "▼ REVERSED ▼" : ""}</div>
    <span class="card-sigil">${sigil}</span>
    <div class="card-title">${escHtml(card.title || "")}</div>
    <div class="card-house">~ ${label} ~</div>
    <div class="card-confidence">
      <span class="conf-bar">${confidenceBar(conf)}</span>&nbsp;${Math.round(conf * 100)}%
    </div>
    <div class="card-pos-label">${posLabel}</div>
  `;

  return el;
}

function buildSourceItem(card) {
  const house  = card.house;
  const color  = HOUSE_COLORS[house] || "var(--text)";
  const label  = house.replace("High House ", "");
  const rev    = card.reversed ? " [R]" : "";
  const art    = card.article || {};
  const title  = art.title  || "";
  const url    = art.url    || "#";

  const el = document.createElement("div");
  el.className = "source-item";
  el.innerHTML = `
    <div class="source-card-name" style="color:${color}">
      ${escHtml(card.title || "")}, ${escHtml(label)}${rev}
    </div>
    <div class="source-article-title">${escHtml(title.slice(0, 80))}</div>
    <div class="source-url"><a href="${escHtml(url)}" target="_blank" rel="noopener">${escHtml(url)}</a></div>
  `;
  return el;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderReading(reading) {
  // Date
  document.getElementById("reading-date").textContent =
    "The reading for " + formatDate(reading.date);

  const grid    = document.getElementById("reading-grid");
  const sources = document.getElementById("sources-list");
  grid.innerHTML    = "";
  sources.innerHTML = "";

  const cards    = reading.cards || [];
  const wildCards = cards.filter(c => c.position === "WILD");
  let wildIdx = 0;

  for (const card of cards) {
    const pos = card.position || "WILD";
    const cardEl = buildCard(card);

    if (pos === "WILD") {
      const slot = wildIdx < 2 ? `pos-wild-${wildIdx}` : null;
      if (slot) cardEl.classList.add(slot);
      wildIdx++;
    } else {
      const cssClass = POSITION_CSS_CLASS[pos];
      if (cssClass) cardEl.classList.add(cssClass);
    }

    grid.appendChild(cardEl);
    sources.appendChild(buildSourceItem(card));
  }
}

async function load() {
  const loadingEl = document.getElementById("loading");
  const errorEl   = document.getElementById("error");
  const readingEl = document.getElementById("reading");

  try {
    const resp = await fetch("reading.json?t=" + Date.now());
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const reading = await resp.json();

    loadingEl.hidden = true;
    renderReading(reading);
    readingEl.hidden = false;
  } catch (err) {
    loadingEl.hidden = true;
    errorEl.hidden   = false;
    errorEl.textContent = "Could not load the reading. The deck is silent today.";
    console.error(err);
  }
}

load();
