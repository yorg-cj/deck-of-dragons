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
  const house    = card.house;
  const color    = HOUSE_COLORS[house] || "var(--text)";
  const sigil    = HOUSE_SIGILS[house]  || "?";
  const label    = house.replace("High House ", "").toUpperCase();
  const pos      = card.position || "WILD";
  const posLabel = POSITION_LABELS[pos] || pos;
  const conf     = card.confidence || 0;
  const rev      = card.reversed;

  // Outer wrap holds the card border + position subtitle below it
  const wrap = document.createElement("div");
  wrap.className = "card-wrap";

  const cardEl = document.createElement("div");
  cardEl.className = "card" + (rev ? " reversed" : "");
  cardEl.style.setProperty("--house-color", color);
  cardEl.innerHTML = `
    <div class="card-reversed-label">${rev ? "▼ REVERSED ▼" : ""}</div>
    <span class="card-sigil">${sigil}</span>
    <div class="card-title">${escHtml(card.title || "")}</div>
    <div class="card-house">~ ${label} ~</div>
    <div class="card-confidence">
      <span class="conf-bar">${confidenceBar(conf)}</span>&nbsp;${Math.round(conf * 100)}%
    </div>
  `;

  const labelEl = document.createElement("div");
  labelEl.className = "card-pos-label";
  labelEl.textContent = posLabel;

  wrap.appendChild(cardEl);
  wrap.appendChild(labelEl);
  return wrap;
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
  document.getElementById("reading-date").textContent =
    "The reading for " + formatDate(reading.date);

  const grid    = document.getElementById("reading-grid");
  const sources = document.getElementById("sources-list");
  grid.innerHTML    = "";
  sources.innerHTML = "";

  const cards   = reading.cards || [];
  let wildIdx   = 0;

  for (const card of cards) {
    const pos   = card.position || "WILD";
    const wrap  = buildCard(card);

    if (pos === "WILD") {
      if (wildIdx < 2) wrap.classList.add(`pos-wild-${wildIdx}`);
      wildIdx++;
    } else {
      const cssClass = POSITION_CSS_CLASS[pos];
      if (cssClass) wrap.classList.add(cssClass);
    }

    grid.appendChild(wrap);
    sources.appendChild(buildSourceItem(card));
  }
}

// Fetch the reading immediately in the background; reveal on "draw"
let readingData  = null;
let fetchError   = false;

async function prefetch() {
  try {
    const resp = await fetch("reading.json?t=" + Date.now());
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    readingData = await resp.json();
  } catch (err) {
    fetchError = true;
    console.error(err);
  }
}

function reveal() {
  const errorEl   = document.getElementById("error");
  const readingEl = document.getElementById("reading");
  const promptEl  = document.getElementById("prompt-area");

  promptEl.remove();

  if (fetchError) {
    errorEl.hidden = false;
    errorEl.textContent = "The deck is silent today.";
    return;
  }

  if (!readingData) {
    errorEl.hidden = false;
    errorEl.textContent = "Drawing from the deck...";
    setTimeout(reveal, 300);
    return;
  }

  errorEl.hidden = true;
  renderReading(readingData);
  readingEl.hidden = false;
}

function init() {
  prefetch();

  const input    = document.getElementById("prompt-input");
  const bufferEl = document.getElementById("buffer-display");
  let buffer = "";

  function submit() {
    const cmd = buffer.trim().toLowerCase();
    buffer = "";
    input.value = "";
    bufferEl.textContent = "";
    if (cmd === "draw" || cmd === "d") reveal();
  }

  // Mobile: tap anywhere in prompt area to focus input and pop up keyboard
  document.getElementById("prompt-area").addEventListener("click", () => input.focus());

  // Mobile: sync what the keyboard types into the visual buffer
  input.addEventListener("input", () => {
    buffer = input.value;
    bufferEl.textContent = buffer;
  });

  // Mobile: Enter key via keyboard
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") submit();
  });

  // Desktop: capture keystrokes without requiring a tap first
  document.addEventListener("keydown", (e) => {
    if (!document.getElementById("prompt-area")) return;
    if (document.activeElement === input) return; // mobile input is handling it

    if (e.key === "Enter") {
      submit();
    } else if (e.key === "Backspace") {
      e.preventDefault();
      buffer = buffer.slice(0, -1);
      input.value = buffer;
      bufferEl.textContent = buffer;
    } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      buffer += e.key;
      input.value = buffer;
      bufferEl.textContent = buffer;
    }
  });
}

init();
