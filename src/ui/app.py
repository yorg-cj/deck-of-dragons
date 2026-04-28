"""
Textual TUI for the Deck of Dragons.
Type 'draw' at the prompt to pull a reading from current world events.
"""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input, Label
from textual.containers import VerticalScroll, Vertical
from textual.binding import Binding
from textual import work
from rich.align import Align
from rich.text import Text
from rich.rule import Rule


SPLASH = """[dim]
    ╔══════════════════════════════════════════════╗
    ║          D E C K   O F   D R A G O N S      ║
    ║                                              ║
    ║   The cards reveal what forces move unseen.  ║
    ║   What hand is played, what debt is owed.    ║
    ║                                              ║
    ║          type  [bold white]draw[/bold white]  to begin                ║
    ╚══════════════════════════════════════════════╝
[/dim]"""


class DeckApp(App):
    CSS = """
    Screen {
        background: #0d0d0d;
    }

    #main {
        height: 1fr;
        overflow-y: auto;
    }

    #reading-panel {
        height: auto;
        padding: 1 2;
        align: center top;
    }

    #sources-panel {
        height: auto;
        padding: 0 2 1 2;
        border-top: solid #333333;
    }

    #prompt-bar {
        height: auto;
        padding: 0 2;
        border-top: solid #333333;
        background: #0d0d0d;
    }

    #command-input {
        background: #0d0d0d;
        border: none;
        color: #cccccc;
        padding: 0 1;
        width: 100%;
    }

    #command-input:focus {
        border: none;
    }

    #status {
        color: #555555;
        padding: 0 1;
        height: 1;
    }
    """

    BINDINGS = [
        Binding("d",      "draw",    "Draw",    show=True),
        Binding("r",      "refresh", "Refresh", show=True),
        Binding("c",      "confirm", "Confirm", show=True),
        Binding("ctrl+c", "quit",    "Quit",    show=True),
    ]

    def __init__(self):
        super().__init__()
        self._reading = None
        self._loading = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, name="DECK OF DRAGONS")

        with Vertical(id="main"):
            yield Static(SPLASH, id="reading-panel")
            yield Static("", id="sources-panel")

        with Vertical(id="prompt-bar"):
            yield Label("", id="status")
            yield Input(placeholder="> draw", id="command-input")

        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#command-input").focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip().lower()
        self.query_one("#command-input").clear()

        if cmd in ("draw", "d"):
            self.action_draw()
        elif cmd in ("refresh", "r"):
            self.action_refresh()
        elif cmd in ("confirm", "c"):
            self.action_confirm()
        elif cmd in ("quit", "q", "exit"):
            self.action_quit()
        elif cmd:
            self._set_status(f"Unknown command: '{cmd}'  —  try: draw  refresh  confirm  quit")

    def action_draw(self) -> None:
        if self._loading:
            return
        self._set_status("Drawing from the deck...")
        self._loading = True
        self._do_draw(force_refresh=False)

    def action_refresh(self) -> None:
        if self._loading:
            return
        self._set_status("Refreshing from current events...")
        self._loading = True
        self._do_draw(force_refresh=True)

    def action_confirm(self) -> None:
        if not self._reading:
            self._set_status("Nothing to confirm — draw a reading first.")
            return
        if self._loading:
            return
        self._set_status("Confirming reading...")
        self._do_confirm()

    @work(thread=True)
    def _do_draw(self, force_refresh: bool = False) -> None:
        try:
            from src.pipeline import get_reading
            self._reading = get_reading(force_refresh=force_refresh)
            self.call_from_thread(self._render_reading)
            self.call_from_thread(
                self._set_status,
                f"{self._reading['date']}  —  "
                f"{len(self._reading['cards'])} houses in play  —  "
                "[dim]press [bold]r[/bold] to refresh[/dim]"
            )
        except Exception as e:
            self.call_from_thread(self._set_status, f"[red]Error: {e}[/red]")
        finally:
            self._loading = False

    @work(thread=True)
    def _do_confirm(self) -> None:
        try:
            from src.feedback import confirm_reading
            n = confirm_reading(self._reading)
            self.call_from_thread(
                self._set_status,
                f"[green]Confirmed {n} card{'s' if n != 1 else ''} as training labels.[/green]"
                "  [dim]Re-run src.train.train to update the classifier.[/dim]"
            )
        except Exception as e:
            self.call_from_thread(self._set_status, f"[red]Confirm error: {e}[/red]")

    def _render_reading(self) -> None:
        if not self._reading:
            return

        from src.ui.cards import render_reading_grid, render_sources

        grid   = render_reading_grid(self._reading["cards"])
        source = render_sources(self._reading["cards"])

        self.query_one("#reading-panel", Static).update(
            Align.center(grid)
        )
        self.query_one("#sources-panel", Static).update(
            Text.from_markup(f"\n[dim]── SOURCES ──[/dim]\n\n{source}")
        )

    def _set_status(self, msg: str) -> None:
        self.query_one("#status", Label).update(msg)
