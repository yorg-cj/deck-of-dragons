"""
ASCII card rendering using Rich panels.
Each card is a fixed-width Rich renderable that can be placed in a grid.
"""
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.align import Align
from rich.box import HEAVY, MINIMAL
from rich import box as rich_box

CARD_WIDTH = 24

HOUSE_COLORS: dict[str, str] = {
    "High House War":    "red",
    "High House Coin":   "yellow",
    "High House Shadow": "magenta",
    "High House Life":   "green",
    "High House Iron":   "blue",
    "High House Words":  "cyan",
    "High House Chains": "dark_orange",
}

HOUSE_SIGILS: dict[str, str] = {
    "High House War":    "⚔",
    "High House Coin":   "⚖",
    "High House Shadow": "◈",
    "High House Life":   "✦",
    "High House Iron":   "⚙",
    "High House Words":  "◉",
    "High House Chains": "⛓",
}

POSITION_LABELS: dict[str, str] = {
    "CENTER":     "THE DOMINANT",
    "ASCENDING":  "THE OPPOSING",
    "FOUNDATION": "THE FOUNDATION",
    "WANING":     "IN RETREAT",
    "EMERGING":   "RISING",
    "WILD":       "UNALIGNED",
}


def _confidence_bar(confidence: float, width: int = 8) -> str:
    filled = round(confidence * width)
    return "▓" * filled + "░" * (width - filled)


def render_card(card: dict) -> Panel:
    house  = card["house"]
    title  = card["title"]
    rev    = card["reversed"]
    conf   = card["confidence"]
    color  = HOUSE_COLORS.get(house, "white")
    sigil  = HOUSE_SIGILS.get(house, "?")
    label  = house.replace("High House ", "").upper()
    pos    = card.get("position", "WILD")

    body = Text(justify="center")

    if rev:
        body.append("▼ REVERSED ▼\n", style=f"dim {color}")
    else:
        body.append("\n")

    body.append(f"\n{sigil}\n\n", style=f"bold {color}")
    body.append(f"{title.upper()}\n", style=f"bold {color}")
    body.append(f"~ {label} ~\n", style=color)
    body.append(f"\n{_confidence_bar(conf)}  {conf:.0%}", style="dim")

    border_style = f"dim {color}" if rev else color

    pos_label = POSITION_LABELS.get(pos, pos)
    return Panel(
        Align.center(body, vertical="middle"),
        width=CARD_WIDTH,
        border_style=border_style,
        subtitle=f"[dim]{pos_label}[/dim]",
        padding=(0, 1),
    )


def render_empty_slot(label: str = "") -> Panel:
    """Transparent placeholder for empty grid positions."""
    body = Text(" ", justify="center")
    return Panel(
        Align.center(body, vertical="middle"),
        width=CARD_WIDTH,
        border_style="black",
        subtitle=f"[dim]{label}[/dim]" if label else "",
        padding=(0, 1),
        box=rich_box.MINIMAL,
    )


def render_reading_grid(cards: list[dict]) -> Table:
    """
    Arrange cards into the cross layout:

          [ ASCENDING  ]
          |
[WANING]--[  CENTER  ]--[EMERGING]
          |
          [FOUNDATION]

    [WILD]              [WILD]
    """
    by_pos: dict[str, dict] = {}
    wild_cards: list[dict] = []

    for card in cards:
        pos = card.get("position", "WILD")
        if pos == "WILD":
            wild_cards.append(card)
        else:
            by_pos[pos] = card

    def slot(pos: str) -> Panel:
        return render_card(by_pos[pos]) if pos in by_pos else render_empty_slot()

    wild_a = render_card(wild_cards[0]) if len(wild_cards) > 0 else render_empty_slot()
    wild_b = render_card(wild_cards[1]) if len(wild_cards) > 1 else render_empty_slot()

    grid = Table.grid(padding=(0, 2))
    grid.add_column(width=CARD_WIDTH)
    grid.add_column(width=CARD_WIDTH)
    grid.add_column(width=CARD_WIDTH)

    grid.add_row(render_empty_slot(), slot("ASCENDING"),  render_empty_slot())
    grid.add_row(slot("WANING"),      slot("CENTER"),     slot("EMERGING"))
    grid.add_row(render_empty_slot(), slot("FOUNDATION"), render_empty_slot())
    grid.add_row(wild_a,              render_empty_slot(), wild_b)

    return grid


def render_sources(cards: list[dict]) -> str:
    """Build a plain-text sources list for display below the grid."""
    lines = []
    for card in cards:
        rev = " [R]" if card["reversed"] else ""
        house_short = card["house"].replace("High House ", "")
        art = card["article"]
        lines.append(
            f"[bold {HOUSE_COLORS.get(card['house'], 'white')}]"
            f"{card['title']}, {house_short}{rev}[/bold "
            f"{HOUSE_COLORS.get(card['house'], 'white')}]"
        )
        lines.append(f"  [dim]{art['title'][:72]}[/dim]")
        lines.append(f"  [dim blue underline]{art['url']}[/dim blue underline]")
        lines.append("")
    return "\n".join(lines)
