"""The web app's now-playing view: large cover beside Up next, opened from the player bar."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from textual.app import App, ComposeResult

from ytm_player.services.queue import QueueManager
from ytm_player.ui import playback_bar
from ytm_player.ui.pages.now_playing import NowPlayingPage
from ytm_player.ui.playback_bar import PlaybackBar
from ytm_player.ui.widgets import cover
from ytm_player.ui.widgets.cover import Cover
from ytm_player.ui.widgets.track_table import TrackTable


def _track(video_id: str, title: str) -> dict:
    return {"video_id": video_id, "title": title, "artist": "Kid Cudi", "artists": [{"name": "Kid Cudi"}],
            "album": "", "album_id": None, "duration": 120, "is_video": False,
            "thumbnail_url": "https://lh3.googleusercontent.com/x=w120-h120-l90-rj"}  # fmt: skip


class _FakePlayer:
    current_track: dict | None = None

    def on(self, *_args: Any) -> None: ...

    def off(self, *_args: Any) -> None: ...


class _Host(App):
    def __init__(self, page: str) -> None:
        super().__init__()
        self.page = page
        self.queue = QueueManager()
        self.queue.add_multiple([_track("a", "BLUE SKY"), _track("b", "Opiate"), _track("c", "Ladders")])
        self.player = _FakePlayer()
        self.player.current_track = self.queue.tracks[0]
        self.navigate_to = AsyncMock()
        self._current_page = "home"

    def get_css_variables(self) -> dict[str, str]:
        variables = super().get_css_variables()
        for name in ("selected-item", "playback-bar-bg", "progress-filled", "progress-empty",
                     "active-tab", "inactive-tab"):  # fmt: skip
            variables.setdefault(name, "#333333")
        return variables

    def compose(self) -> ComposeResult:
        if self.page == "now_playing":
            yield NowPlayingPage(id="page-now_playing")
        else:
            yield PlaybackBar(id="playback-bar")


@pytest.fixture(autouse=True)
def _offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cover, "fetch_thumbnail", lambda url: None)


async def test_the_view_shows_the_playing_track_large_beside_up_next():
    app = _Host("now_playing")
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause(0.2)
        assert str(app.query_one("#np-title").render()) == "BLUE SKY"
        assert str(app.query_one("#np-artist").render()) == "Kid Cudi"
        big = app.query_one("#np-cover", Cover)
        assert big.url.endswith("=w544-h544-l90-rj") and big.size == (60, 30)
        titles = [t["title"] for t in app.query_one(TrackTable).visible_tracks]
        assert titles == ["BLUE SKY", "Opiate", "Ladders"]


async def test_the_view_follows_a_track_change():
    app = _Host("now_playing")
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause(0.2)
        app.player.current_track = app.queue.tracks[1]
        await pilot.pause(0.8)
        assert str(app.query_one("#np-title").render()) == "Opiate"


@pytest.mark.parametrize(("current", "expected"), [("home", "now_playing"), ("now_playing", "back")])
async def test_clicking_the_bar_title_opens_the_view_and_clicking_again_goes_back(
    monkeypatch, current: str, expected: str
):
    monkeypatch.setattr(playback_bar, "has_real_images", lambda: True)
    app = _Host("bar")
    app._current_page = current
    async with app.run_test(size=(120, 8)) as pilot:
        app.query_one(PlaybackBar).update_track(app.queue.tracks[0])
        await pilot.pause()
        await pilot.click("#pb-track-info")
        for _ in range(3):
            await pilot.pause()
        app.navigate_to.assert_awaited_once_with(expected)


async def test_clicking_the_bar_cover_opens_the_view(monkeypatch):
    monkeypatch.setattr(playback_bar, "has_real_images", lambda: True)
    app = _Host("bar")
    async with app.run_test(size=(120, 8)) as pilot:
        await pilot.click("#pb-art")
        for _ in range(3):
            await pilot.pause()
        app.navigate_to.assert_awaited_once_with("now_playing")


async def test_the_cover_shrinks_so_title_and_artist_stay_on_screen():
    app = _Host("now_playing")
    async with app.run_test(size=(160, 26)) as pilot:
        await pilot.pause(0.3)
        big = app.query_one("#np-cover", Cover)
        artist = app.query_one("#np-artist")
        assert big.size.height < 30 and big.size.width == 2 * big.size.height
        assert artist.region.bottom <= app.query_one(NowPlayingPage).region.bottom
