"""A track row the cursor rests on gets its stream resolved before the click, as on the web app."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from textual.app import App, ComposeResult

from ytm_player.app import _playback
from ytm_player.app._playback import PlaybackMixin
from ytm_player.ui.widgets.track_table import TrackTable

TRACKS = [
    {"video_id": f"vid{i}", "title": f"Song {i}", "artist": "A", "duration": 200} for i in range(6)
]


class _Resolver:
    def __init__(self) -> None:
        self.prefetched: list[str] = []

    async def prefetch(self, video_id: str) -> None:
        self.prefetched.append(video_id)


class _Host(App):
    on_track_table_track_highlighted = PlaybackMixin.on_track_table_track_highlighted
    _speculate = PlaybackMixin._speculate

    async def _warm(self, video_ids: list[str]) -> None:
        for video_id in video_ids:
            await self.stream_resolver.prefetch(video_id)

    def __init__(self, playing: dict | None = None) -> None:
        super().__init__()
        self.stream_resolver = _Resolver()
        self.player = SimpleNamespace(current_track=playing)

    def get_css_variables(self) -> dict[str, str]:
        variables = super().get_css_variables()
        variables.setdefault("selected-item", "#3a3a3a")
        return variables

    def compose(self) -> ComposeResult:
        yield TrackTable(id="t")

    def on_mount(self) -> None:
        table = self.query_one(TrackTable)
        table.load_tracks(TRACKS)
        table.focus()


@pytest.fixture(autouse=True)
def _short_dwell(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_playback, "SPECULATE_DWELL", 0.2)


async def test_a_row_the_cursor_rests_on_is_resolved_ahead():
    app = _Host()
    async with app.run_test(size=(100, 20)) as pilot:
        await pilot.pause(0.4)
        await pilot.press("down", "down")
        await pilot.pause(0.4)
        assert app.stream_resolver.prefetched[-1] == "vid2"


async def test_rows_the_cursor_only_passes_over_are_not_resolved():
    app = _Host()
    async with app.run_test(size=(100, 20)) as pilot:
        await pilot.pause(0.4)
        app.stream_resolver.prefetched.clear()
        await pilot.press("down", "down", "down")
        await pilot.pause(0.4)
        assert app.stream_resolver.prefetched == ["vid3"]


async def test_the_first_row_of_a_new_list_is_resolved_for_play_all():
    app = _Host()
    async with app.run_test(size=(100, 20)) as pilot:
        await pilot.pause(0.4)
        assert app.stream_resolver.prefetched == ["vid0"]


async def test_the_playing_track_is_not_resolved_again():
    app = _Host(playing=TRACKS[0])
    async with app.run_test(size=(100, 20)) as pilot:
        await pilot.pause(0.4)
        assert app.stream_resolver.prefetched == []
