"""The web app's now-playing view: a large cover on the left, a tabbed pane on the right.

A left click on the player bar's cover or title opens it, and a second click
goes back, as on music.youtube.com. The pane has the web app's three tabs:

- Up next lists the queue from the playing track on, under "Playing from" and
  the playlist name. Each row is a small cover, title over artist, and duration.
  Click a row to play it. The Queue page keeps reordering and removal.
- Lyrics shows the lyrics centred, the sung line bright, with their source.
- Related lists the songs YouTube Music relates to the playing one.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Click
from textual.widget import Widget
from textual.widgets import ContentSwitcher, Label, Static

from ytm_player.config.keymap import Action
from ytm_player.ui.sidebars.lyrics_sidebar import LyricsSidebar
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


class RelatedRow(UpNextRow):
    """A related song. A click plays it without changing the queue."""

    async def _play(self) -> None:
        await cast("YTMHostBase", self.app).play_track(self.track)


class RelatedList(VerticalScroll):
    """Songs related to the playing one, loaded when the tab shows and the track changes."""

    DEFAULT_CSS = """
    RelatedList { height: 1fr; }
    RelatedList .un-empty { color: $text-muted; padding: 1 2; }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._video_id: str | None = None

    def show_for(self, video_id: str) -> None:
        """Load the related songs of *video_id*, unless they are already showing."""
        if not video_id or video_id == self._video_id:
            return
        self._video_id = video_id
        self.remove_children()
        self.mount(Label("Loading related songs...", classes="un-empty"))
        self.run_worker(self._load(video_id), group="related", exclusive=True)

    async def _load(self, video_id: str) -> None:
        from ytm_player.utils.formatting import normalize_tracks

        ytmusic = getattr(self.app, "ytmusic", None)
        songs = await ytmusic.get_related_songs(video_id) if ytmusic else []
        if video_id != self._video_id:
            return
        self.remove_children()
        tracks = normalize_tracks(songs)[:_UP_NEXT_ROWS]
        if not tracks:
            self.mount(Label("No related songs.", classes="un-empty"))
            return
        self.mount(*(RelatedRow(track, index, False) for index, track in enumerate(tracks)))


# The pane's tabs, as the web app labels them, and the widget each one shows.
PANE_TABS = (("up-next", "Up next", "np-queue"), ("lyrics", "Lyrics", "np-lyrics"),
             ("related", "Related", "np-related"))  # fmt: skip


class PaneTabs(Horizontal):
    """UP NEXT, LYRICS and RELATED. The active tab is in the primary colour, underlined."""

    DEFAULT_CSS = """
    PaneTabs { height: 2; padding: 0 1; }
    PaneTabs > .np-tab { width: 1fr; height: 2; content-align: center top; color: $text-muted;
        border-bottom: solid $border; }
    PaneTabs > .np-tab:hover { color: $text; }
    PaneTabs > .np-tab.-active { color: $primary; border-bottom: solid $primary; }
    """

    def compose(self) -> ComposeResult:
        for key, label, _target in PANE_TABS:
            yield Static(label, id=f"np-tab-{key}", classes="np-tab")

    def on_click(self, event: Click) -> None:
        widget = event.widget
        if widget is not None and widget.id and widget.id.startswith("np-tab-"):
            event.stop()
            page = next((a for a in self.ancestors if isinstance(a, NowPlayingPage)), None)
            if page is not None:
                page.show_tab(widget.id.removeprefix("np-tab-"))


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
    NowPlayingPage #np-source { height: 1; padding: 0 2; margin-top: 1; color: $text-muted; }
    NowPlayingPage #np-switch { height: 1fr; }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._shown_id: str | None = None
        self.active_tab = "up-next"

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="np-left"):
                yield Cover(id="np-cover")
                yield Label("Nothing playing", id="np-title")
                yield Label("", id="np-artist")
            with Vertical(id="np-right"):
                yield PaneTabs(id="np-tabs")
                yield Label("", id="np-source")
                with ContentSwitcher(initial="np-queue", id="np-switch"):
                    yield UpNextList(id="np-queue")
                    yield LyricsSidebar(id="np-lyrics", classes="in-pane")
                    yield RelatedList(id="np-related")

    def on_mount(self) -> None:
        self.show_tab(self.active_tab)
        self._follow()
        self.set_interval(_FOLLOW_SECONDS, self._follow)

    def show_tab(self, key: str) -> None:
        """Show the pane tab *key*: "up-next", "lyrics" or "related"."""
        target = next((t for k, _label, t in PANE_TABS if k == key), None)
        if target is None:
            return
        self.active_tab = key
        for tab_key, _label, _target in PANE_TABS:
            self.query_one(f"#np-tab-{tab_key}").set_class(tab_key == key, "-active")
        self.query_one("#np-switch", ContentSwitcher).current = target
        self.query_one("#np-source").display = key == "up-next"
        if key == "lyrics":
            self.query_one("#np-lyrics", LyricsSidebar).activate()
        elif key == "related":
            self.query_one("#np-related", RelatedList).show_for(self._shown_id or "")

    def toggle_lyrics_tab(self) -> None:
        """The header's Lyrics button on this page: switch between Lyrics and Up next."""
        self.show_tab("up-next" if self.active_tab == "lyrics" else "lyrics")

    def _source_name(self) -> str:
        """The name of the playlist the queue plays from, or "" when it is unknown."""
        app = cast("YTMHostBase", self.app)
        queue = getattr(app, "queue", None)
        context = getattr(queue, "current_context_id", None) if queue is not None else None
        if not context:
            return ""
        bare = context.removeprefix("VL")
        from ytm_player.ui.sidebars.playlist_sidebar import LibraryPanel

        for panel in app.query(LibraryPanel):
            for item in getattr(panel, "_items", []):
                ids = {
                    item.get("playlistId") or "",
                    (item.get("browseId") or "").removeprefix("VL"),
                }
                if bare in ids:
                    return item.get("title") or ""
        return ""

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
        source = self._source_name()
        self.query_one("#np-source", Label).update(f"Playing from  {source}" if source else "")
        track = self._playing()
        video_id = (track or {}).get("video_id") or ""
        if video_id == self._shown_id:
            return
        self._shown_id = video_id
        if self.active_tab == "related":
            self.query_one("#np-related", RelatedList).show_for(video_id)
        self.query_one("#np-cover", Cover).url = _cover_url(track)
        self.query_one("#np-title", Label).update((track or {}).get("title") or "Nothing playing")
        self.query_one("#np-artist", Label).update(extract_artist(track) if track else "")

    async def handle_action(self, action: Action, count: int = 1) -> None:
        if self.active_tab == "lyrics":
            await self.query_one("#np-lyrics", LyricsSidebar).handle_action(action, count)
            return
        scroll = self.query_one("#np-related" if self.active_tab == "related" else "#np-queue")
        if action == Action.MOVE_DOWN:
            scroll.scroll_relative(y=3 * count, animate=False)
        elif action == Action.MOVE_UP:
            scroll.scroll_relative(y=-3 * count, animate=False)

    def get_nav_state(self) -> dict[str, Any]:
        return {}
