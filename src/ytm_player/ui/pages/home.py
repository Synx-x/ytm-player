"""Home page laid out like music.youtube.com: shelves of cover cards.

Each shelf from ``get_home()`` becomes a titled row of cards with real cover
art (see ``ui/widgets/cover.py``). A card plays a song or opens an album,
playlist or artist page through ``navigate_browse_item``, the routing the
Browse page already uses.

Keys: j/k move between shelves, h/l or the arrow keys move along a shelf,
Enter opens the focused card. Each shelf also has ◀ ▶ buttons, and Shift+wheel
or a tilt wheel scrolls it sideways, as on the web.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, cast

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, HorizontalScroll, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import Label, Static

from ytm_player.config.keymap import Action
from ytm_player.config.settings import get_settings
from ytm_player.ui.pages.browse import _clean_shelf_title, navigate_browse_item
from ytm_player.ui.widgets.cover import Cover, best_thumbnail

if TYPE_CHECKING:
    from ytm_player.app._base import YTMHostBase

logger = logging.getLogger(__name__)

CARD_WIDTH = 24
SCROLL_STEP = CARD_WIDTH * 3
FEED_TTL_SECONDS = 600

# The last Home feed, so coming back to Home is instant, as on the web.
# (monotonic time, shelves). The r key always fetches a fresh feed.
_feed_cache: tuple[float, list[dict[str, Any]]] | None = None
_LOAD_FAILED = "Couldn't load your Home feed. Press r to try again."


def relayout_soon(widget: Widget) -> None:
    """Run one full screen layout pass just after a burst of cards mounts.

    Cards mounted after their page sometimes stay unpainted in kitty until the
    user scrolls. A scroll fixes it by laying out the screen again, so do the
    same once the cards exist.
    """
    widget.set_timer(0.15, lambda: widget.screen.refresh(layout=True))


def card_subtitle(item: dict[str, Any]) -> str:
    """Second line under a card, the way the web shows it."""
    artists = ", ".join(a.get("name", "") for a in item.get("artists") or [] if a.get("name"))
    kind = (item.get("resultType") or item.get("type") or "").capitalize()
    if item.get("count") is not None:  # a library playlist
        author = item.get("author")
        owner = author[0].get("name", "") if isinstance(author, list) and author else ""
        count = str(item["count"]).replace(",", "")
        unit = "song" if count == "1" else "songs"
        return " • ".join(p for p in ("Playlist", owner, f"{count} {unit}") if p)
    if artists and kind in ("Album", "Single", "Ep"):
        return f"{kind} • {artists}"
    if artists:
        return artists
    for key in ("description", "subscribers", "year"):
        if item.get(key):
            return str(item[key])
    return kind


class ShelfRow(HorizontalScroll):
    """A sideways-scrolling row of cards.

    Textual already scrolls a horizontal container on Shift+wheel and on a
    tilt wheel, so this class only adds paging for the ◀ ▶ buttons.
    """

    DEFAULT_CSS = """
    ShelfRow { height: 17; scrollbar-size-horizontal: 1; }
    """

    def page(self, direction: int) -> None:
        self.scroll_to(x=max(0, self.scroll_x + direction * SCROLL_STEP), animate=False)


class HomeCard(Vertical, can_focus=True):
    """One cover card. Click or Enter opens it."""

    DEFAULT_CSS = f"""
    HomeCard {{ width: {CARD_WIDTH}; height: 16; margin-right: 2; }}
    HomeCard > Cover {{ width: {CARD_WIDTH - 2}; height: 11; }}
    HomeCard > .card-title {{ width: {CARD_WIDTH - 2}; height: 1; margin-top: 1; text-style: bold;
        text-wrap: nowrap; text-overflow: ellipsis; }}
    HomeCard > .card-sub {{ width: {CARD_WIDTH - 2}; height: 1; color: $text-muted;
        text-wrap: nowrap; text-overflow: ellipsis; }}
    HomeCard:hover > .card-title {{ text-style: bold underline; }}
    HomeCard:focus > .card-title {{ color: $accent; text-style: bold underline; }}
    """

    BINDINGS = [Binding("enter", "open", "Open", show=False)]

    def __init__(self, item: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.item = item

    def compose(self) -> ComposeResult:
        yield Cover(best_thumbnail(self.item))
        yield Label(self.item.get("title", ""), classes="card-title")
        yield Label(card_subtitle(self.item), classes="card-sub")

    def on_click(self, event: events.Click) -> None:
        if event.button != 1:
            return  # a right-click is for the page's actions menu, where it has one
        event.stop()
        self.focus()
        self.action_open()

    def action_open(self) -> None:
        # Opening an album or playlist removes this page, and with it this card.
        # Awaiting that from the card's own handler deadlocks: the removal waits
        # for the handler to finish. So the work runs as a worker on the app.
        self.app.run_worker(_open_item(self.app, self.item), group="home-open", exclusive=True)


async def _open_item(app: Any, item: dict[str, Any]) -> None:
    try:
        await navigate_browse_item(cast("YTMHostBase", app), item)
    except Exception:
        logger.exception("Failed to open home item %s", item.get("title"))
        app.notify("Couldn't open that item.", severity="warning")


class Shelf(Vertical):
    """A titled row of cards with ◀ ▶ scroll buttons."""

    DEFAULT_CSS = """
    Shelf { height: auto; margin-bottom: 1; }
    Shelf > .shelf-head { height: 1; margin-bottom: 1; }
    Shelf .shelf-title { width: 1fr; text-style: bold; }
    Shelf .shelf-arrow { width: 5; content-align: center middle; color: $text-muted; }
    Shelf .shelf-arrow:hover { color: $text; background: $boost; }
    """

    def __init__(self, title: str, items: list[dict[str, Any]], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.title = title
        self.items = items

    def compose(self) -> ComposeResult:
        with Horizontal(classes="shelf-head"):
            yield Label(self.title, classes="shelf-title")
            yield Static("◀", classes="shelf-arrow shelf-prev")
            yield Static("▶", classes="shelf-arrow shelf-next")
        with ShelfRow(classes="shelf-row"):
            for item in self.items:
                yield HomeCard(item)

    def on_click(self, event: events.Click) -> None:
        widget = event.widget
        if widget is None:
            return
        if widget.has_class("shelf-prev"):
            event.stop()
            self.query_one(ShelfRow).page(-1)
        elif widget.has_class("shelf-next"):
            event.stop()
            self.query_one(ShelfRow).page(1)

    def cards(self) -> list[HomeCard]:
        return list(self.query(HomeCard))


class HomePage(Widget):
    """The Home feed as shelves of cover cards."""

    DEFAULT_CSS = """
    HomePage { width: 1fr; height: 1fr; }
    HomePage > #home-scroll { padding: 1 3; }
    HomePage .home-status { color: $text-muted; padding: 2 3; }
    """

    BINDINGS = [Binding("r", "reload", "Reload", show=False)]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._shelves: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="home-scroll"):
            yield Static("Loading your Home…", id="home-status", classes="home-status")

    def on_mount(self) -> None:
        self.run_worker(self._load(), exclusive=True, group="home-load")

    async def action_reload(self) -> None:
        self.run_worker(self._load(fresh=True), exclusive=True, group="home-load")

    async def _load(self, fresh: bool = False) -> None:
        global _feed_cache
        host = cast("YTMHostBase", self.app)
        limit = max(get_settings().ui.home_shelves, 6)
        cached = _feed_cache
        if not fresh and cached and time.monotonic() - cached[0] < FEED_TTL_SECONDS:
            shelves: list[dict[str, Any]] | None = cached[1]
        else:
            try:
                shelves = await host.ytmusic.get_home(limit=limit) if host.ytmusic else None
            except Exception:
                logger.exception("Failed to load the Home feed")
                shelves = None
            if shelves:
                _feed_cache = (time.monotonic(), shelves)
        scroll = self.query_one("#home-scroll", VerticalScroll)
        await scroll.remove_children()
        if not shelves:
            await scroll.mount(Static(_LOAD_FAILED, id="home-status", classes="home-status"))
            return
        self._shelves = [s for s in shelves if s.get("contents")]
        await scroll.mount_all(
            Shelf(_clean_shelf_title(s.get("title", "")), [c for c in s["contents"] if c])
            for s in self._shelves
        )
        relayout_soon(self)

    # ── keyboard ──────────────────────────────────────────────────

    def _focus_position(self) -> tuple[int, int] | None:
        focused = self.app.focused
        for si, shelf in enumerate(self.query(Shelf)):
            for ci, card in enumerate(shelf.cards()):
                if card is focused:
                    return si, ci
        return None

    def _focus_card(self, shelf_index: int, card_index: int) -> None:
        shelves = list(self.query(Shelf))
        if not shelves:
            return
        shelf = shelves[max(0, min(shelf_index, len(shelves) - 1))]
        cards = shelf.cards()
        if not cards:
            return
        card = cards[max(0, min(card_index, len(cards) - 1))]
        card.focus()
        card.scroll_visible(animate=False)

    def on_key(self, event: events.Key) -> None:
        moves = {"left": (0, -1), "right": (0, 1), "h": (0, -1), "l": (0, 1)}
        if event.key in moves and self._focus_position() is not None:
            event.stop()
            si, ci = cast("tuple[int, int]", self._focus_position())
            self._focus_card(si, ci + moves[event.key][1])

    async def handle_action(self, action: Action, count: int = 1) -> None:
        position = self._focus_position()
        si, ci = position if position is not None else (-1, 0)
        if action == Action.MOVE_DOWN:
            self._focus_card(si + count, 0 if position is None else ci)
        elif action == Action.MOVE_UP:
            self._focus_card(max(0, si - count), ci)
        elif action == Action.GO_TOP:
            self._focus_card(0, 0)
        elif action == Action.GO_BOTTOM:
            self._focus_card(len(self.query(Shelf)) - 1, 0)
        elif action == Action.SELECT and position is not None:
            focused = self.app.focused
            if isinstance(focused, HomeCard):
                focused.action_open()

    def get_nav_state(self) -> dict[str, Any]:
        return {}
