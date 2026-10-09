"""The web app's now-playing view: a large cover on the left, Up next on the right.

A left click on the player bar's cover or title opens it, and a second click
goes back, as on music.youtube.com. Up next is the Queue page, embedded, so its
keys, menus and reordering work here too.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Label

from ytm_player.config.keymap import Action
from ytm_player.ui.pages.queue import QueuePage
from ytm_player.ui.widgets.cover import Cover
from ytm_player.utils.formatting import extract_artist

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
    url = track.get("thumbnail_url") or ""
    # Player thumbnails are small. lh3 URLs carry their size, so ask for a large copy.
    return re.sub(r"=w\d+-h\d+", "=w544-h544", url, count=1)


class NowPlayingPage(Widget):
    """Large cover, title and artist of the playing track, beside Up next."""

    DEFAULT_CSS = """
    NowPlayingPage { width: 1fr; height: 1fr; }
    NowPlayingPage > Horizontal { height: 1fr; }
    NowPlayingPage #np-left { width: 1fr; height: 1fr; align: center middle; padding: 1 2; }
    NowPlayingPage #np-cover { width: 60; height: 30; }
    NowPlayingPage #np-title { width: 60; margin-top: 1; text-style: bold; content-align: center top; }
    NowPlayingPage #np-artist { width: 60; color: $text-muted; content-align: center top; }
    NowPlayingPage #np-right { width: 1fr; height: 1fr; border-left: solid $border; }
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
                yield QueuePage(id="np-queue")

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
        await self.query_one("#np-queue", QueuePage).handle_action(action, count)

    def get_nav_state(self) -> dict[str, Any]:
        return {}
