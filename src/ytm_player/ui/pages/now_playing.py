"""The web app's now-playing view: a large cover on the left, Up next on the right.

A left click on the player bar's cover or title opens it, and a second click
goes back, as on music.youtube.com. Up next lists the queue from the playing
track on, each row a small cover, title over artist, and duration. Click a row
to play it. The Queue page keeps reordering and removal.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Click
from textual.widget import Widget
from textual.widgets import Label

from ytm_player.config.keymap import Action
from ytm_player.ui.theme import get_theme
from ytm_player.ui.widgets.cover import Cover, track_thumbnail
from ytm_player.utils.formatting import extract_artist, format_duration

if TYPE_CHECKING:
    from ytm_player.app._base import YTMHostBase

# Seconds between checks for a track change. The bar has its own updates, and
# this page only needs to follow them while it is showing.
_FOLLOW_SECONDS = 0.5
# Rows under the cover: a gap, the title, the artist, and padding.
_TEXT_ROWS = 5


def _cover_url(track: dict[str, Any] | None) -> str:
    if not track:
        return ""
    url = track_thumbnail(track)
    # Player thumbnails are small. lh3 URLs carry their size, so ask for a large copy.
    return re.sub(r"=w\d+-h\d+", "=w544-h544", url, count=1)


# Rows the Up next list shows: the playing track and those after it.
_UP_NEXT_ROWS = 60


# Columns the duration takes at the right of a row.
_TIME_COLUMNS = 7


class UpNextText(Widget):
    """Title over artist, with the duration at the right of the title line.

    One widget draws all three. A scroll step repaints every visible widget,
    so a row of three widgets costs about half of the six it used to be.
    """

    DEFAULT_CSS = """
    UpNextText { width: 1fr; height: 2; }
    """

    def __init__(self, title: str, artist: str, duration: str, current: bool) -> None:
        super().__init__()
        self.title = title
        self.artist = artist
        self.duration = duration
        self.current = current

    def render(self) -> Text:
        theme = get_theme()
        text_width = max(0, self.size.width - _TIME_COLUMNS)
        title = Text(self.title, style=theme.primary if self.current else theme.foreground)
        title.truncate(text_width, overflow="ellipsis", pad=True)
        artist = Text(self.artist, style=theme.muted_text)
        artist.truncate(text_width, overflow="ellipsis")
        time = Text(self.duration.rjust(_TIME_COLUMNS), style=theme.muted_text)
        return Text.assemble(title, time, "\n", artist, no_wrap=True)


class UpNextRow(Horizontal):
    """One queue entry as the web lists it: small cover, title over artist, duration on the right."""

    DEFAULT_CSS = """
    UpNextRow { height: 3; padding: 0 1; margin: 0 2 0 1; border-bottom: solid $border; }
    UpNextRow:hover { background: $boost; }
    UpNextRow > Cover { width: 4; height: 2; margin-right: 2; }
    """

    def __init__(self, track: dict[str, Any], index: int, current: bool) -> None:
        super().__init__(classes="-current" if current else "")
        self.track = track
        self.index = index
        self.current = current

    def compose(self) -> ComposeResult:
        yield Cover(track_thumbnail(self.track))
        duration = self.track.get("duration")
        yield UpNextText(
            self.track.get("title") or "",
            extract_artist(self.track) or "",
            format_duration(int(duration)) if duration else "",
            self.current,
        )

    def on_click(self, event: Click) -> None:
        if event.button != 1:
            return
        event.stop()
        self.app.run_worker(self._play(), group="up-next-play", exclusive=True)

    async def _play(self) -> None:
        app = cast("YTMHostBase", self.app)
        track = app.queue.jump_to(self.index)
        if track:
            await app.play_track(track)


class UpNextList(VerticalScroll):
    """The queue from the playing track onward, rebuilt when the queue changes."""

    DEFAULT_CSS = """
    /* No scroll bar (set in the app's CSS): the dividers end in open space, as
       floating lines. The list still scrolls by wheel and keys. */
    UpNextList { height: 1fr; }
    UpNextList .un-empty { color: $text-muted; padding: 1 2; }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._shown: tuple[Any, ...] | None = None

    def on_mount(self) -> None:
        self.refresh_rows()
        self.set_interval(_FOLLOW_SECONDS, self.refresh_rows)

    def refresh_rows(self) -> None:
        queue = getattr(self.app, "queue", None)
        if queue is None:
            return
        tracks = list(queue.tracks)
        current = max(0, queue.real_index) if tracks else -1
        signature = (queue.generation, len(tracks), current)
        if signature == self._shown:
            return
        self._shown = signature
        self.remove_children()
        if not tracks:
            self.mount(Label("Queue is empty.", classes="un-empty"))
            return
        rows = [
            UpNextRow(track, index, index == current)
            for index, track in enumerate(tracks[current : current + _UP_NEXT_ROWS], start=current)
        ]
        self.mount(*rows)


class NowPlayingPage(Widget):
    """Large cover, title and artist of the playing track, beside Up next."""

    DEFAULT_CSS = """
    NowPlayingPage { width: 1fr; height: 1fr; }
    NowPlayingPage > Horizontal { height: 1fr; }
    NowPlayingPage #np-left { width: 1fr; height: 1fr; align: center middle; padding: 1 2; }
    NowPlayingPage #np-cover { width: 60; height: 30; }
    NowPlayingPage #np-title { width: 60; margin-top: 1; text-style: bold; content-align: center top; }
    NowPlayingPage #np-artist { width: 60; color: $text-muted; content-align: center top; }
    /* Up next sits centred in its half, at most 90% of it, clear of the edges. */
    NowPlayingPage #np-right { width: 1fr; height: 1fr; align-horizontal: center; }
    NowPlayingPage #np-right > * { width: 100%; max-width: 90%; }
    NowPlayingPage #np-upnext-title { height: 1; padding: 0 1; text-style: bold; }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._shown_id: str | None = None

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="np-left"):
                yield Cover(id="np-cover")
                yield Label("Nothing playing", id="np-title")
                yield Label("", id="np-artist")
            with Vertical(id="np-right"):
                yield Label("Up next", id="np-upnext-title")
                yield UpNextList(id="np-queue")

    def on_mount(self) -> None:
        self._follow()
        self.set_interval(_FOLLOW_SECONDS, self._follow)

    def on_resize(self) -> None:
        """Fit the square cover in the left half, leaving rows for the title and artist."""
        left = self.query_one("#np-left")
        rows = max(6, min(30, left.size.height - _TEXT_ROWS, (left.size.width - 4) // 2))
        cover = self.query_one("#np-cover", Cover)
        cover.styles.width, cover.styles.height = rows * 2, rows
        for label in self.query("#np-title, #np-artist"):
            label.styles.width = rows * 2

    def _playing(self) -> dict[str, Any] | None:
        app = cast("YTMHostBase", self.app)
        player = getattr(app, "player", None)
        if player is not None and player.current_track:
            return player.current_track
        queue = getattr(app, "queue", None)
        return queue.current_track if queue is not None else None

    def _follow(self) -> None:
        track = self._playing()
        video_id = (track or {}).get("video_id") or ""
        if video_id == self._shown_id:
            return
        self._shown_id = video_id
        self.query_one("#np-cover", Cover).url = _cover_url(track)
        self.query_one("#np-title", Label).update((track or {}).get("title") or "Nothing playing")
        self.query_one("#np-artist", Label).update(extract_artist(track) if track else "")

    async def handle_action(self, action: Action, count: int = 1) -> None:
        scroll = self.query_one("#np-queue", UpNextList)
        if action == Action.MOVE_DOWN:
            scroll.scroll_relative(y=3 * count, animate=False)
        elif action == Action.MOVE_UP:
            scroll.scroll_relative(y=-3 * count, animate=False)

    def get_nav_state(self) -> dict[str, Any]:
        return {}
