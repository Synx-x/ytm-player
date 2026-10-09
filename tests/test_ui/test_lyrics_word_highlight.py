"""Per-word lyric highlighting: each word of the current line lights when its estimated start time arrives.

YouTube times lines, not words, so the sidebar splits a line's time across its words by word length.
"""

from __future__ import annotations

from types import SimpleNamespace

from textual.app import App, ComposeResult

from ytm_player.ui.sidebars.lyrics_sidebar import LyricsSidebar, lit_length, word_spans


def test_longer_words_get_more_of_the_lines_time():
    spans = word_spans("a wonderful day", 0.0, 10.0)
    starts = [start for _end, start in spans]
    assert starts[0] == 0.0
    # "a" (weight 2) is short, "wonderful" (weight 10) long, so "day" starts late.
    assert starts[1] - starts[0] < starts[2] - starts[1]


def test_lit_length_covers_every_word_that_has_started():
    spans = word_spans("I know, I know", 10.0, 14.0)
    assert lit_length(spans, 9.0) == 0
    assert lit_length(spans, 10.0) == len("I ")
    assert lit_length(spans, 13.99) == len("I know, I know")


def _entry(text: str, start: int, end: int) -> SimpleNamespace:
    return SimpleNamespace(text=text, start_time=start, end_time=end)


class _Host(App):
    def get_css_variables(self) -> dict[str, str]:
        variables = super().get_css_variables()
        for name in ("lyrics-played", "lyrics-current", "lyrics-upcoming"):
            variables.setdefault(name, "#888888")
        return variables

    def compose(self) -> ComposeResult:
        yield LyricsSidebar(id="lyrics-sidebar")


async def test_the_current_line_lights_word_by_word_and_resets_when_it_ends():
    app = _Host()
    async with app.run_test(size=(60, 20)) as pilot:
        sidebar = app.query_one(LyricsSidebar)
        sidebar._process_lyrics({"hasTimestamps": True, "lyrics": [
            _entry("When you said it was over", 0, 4000),
            _entry("You shot right through my heart", 4000, 8000),
        ]})  # fmt: skip
        await pilot.pause()
        first = sidebar._lyric_widgets[0]
        sidebar._on_position_change(0.1)
        await pilot.pause()
        early = first._lit
        sidebar._on_position_change(3.9)
        await pilot.pause()
        assert 0 < early < first._lit == len("When you said it was over")
        sidebar._on_position_change(4.1)
        await pilot.pause()
        assert first._lit == -1, "a finished line goes back to plain text"
        assert sidebar._lyric_widgets[1]._lit > 0
