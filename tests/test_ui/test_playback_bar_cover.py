"""The playback bar shows a real cover when the terminal draws images, half-blocks otherwise."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from ytm_player.ui import playback_bar
from ytm_player.ui.playback_bar import PlaybackBar
from ytm_player.ui.widgets import cover
from ytm_player.ui.widgets.album_art import AlbumArt
from ytm_player.ui.widgets.cover import Cover

TRACK = {"title": "BLUE SKY", "artists": [{"name": "Kid Cudi"}], "thumbnail_url": "https://img/1"}


class _Host(App):
    def get_css_variables(self) -> dict[str, str]:
        variables = super().get_css_variables()
        for name in ("playback-bar-bg", "progress-filled", "progress-empty", "active-tab",
                     "inactive-tab", "selected-item"):  # fmt: skip
            variables.setdefault(name, "#222222")
        return variables

    def compose(self) -> ComposeResult:
        yield PlaybackBar(id="playback-bar")


@pytest.fixture(autouse=True)
def _offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cover, "fetch_thumbnail", lambda url: None)


async def test_real_images_put_a_cover_in_the_bar_and_track_changes_update_it(monkeypatch):
    monkeypatch.setattr(playback_bar, "has_real_images", lambda: True)
    app = _Host()
    async with app.run_test(size=(120, 8)) as pilot:
        bar = app.query_one(PlaybackBar)
        art = app.query_one("#pb-art")
        assert isinstance(art, Cover)
        bar.update_track(TRACK)
        await pilot.pause()
        assert art.url == "https://img/1"
        bar.update_track(None)
        await pilot.pause()
        assert art.url == ""


async def test_no_real_images_keeps_the_half_block_art(monkeypatch):
    monkeypatch.setattr(playback_bar, "has_real_images", lambda: False)
    app = _Host()
    async with app.run_test(size=(120, 8)):
        art = app.query_one("#pb-art")
        assert isinstance(art, AlbumArt)
        app.query_one(PlaybackBar).update_track(TRACK)
        assert art.thumbnail_url == "https://img/1"
