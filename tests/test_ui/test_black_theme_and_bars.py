"""Full black theme with a dim chartreuse accent, thin scroll bars, and the taller player bar."""

from __future__ import annotations

from rich.color import Color
from textual.app import App, ComposeResult

from ytm_player.ui.playback_bar import PlaybackBar
from ytm_player.ui.theme import YTM_DARK
from ytm_player.ui.widgets.thin_scrollbar import ThinScrollBarRender


def test_the_theme_is_full_black_with_a_dim_green_accent_and_grey_chrome():
    assert YTM_DARK.background == "#000000" and YTM_DARK.surface == "#000000"
    assert YTM_DARK.primary == "#6aa81e"
    for name in ("border", "scrollbar", "block-cursor-background"):
        assert YTM_DARK.variables[name].startswith("#1") or YTM_DARK.variables[name].startswith("#2")


def test_horizontal_bars_draw_a_thin_line_and_vertical_bars_stay_one_cell():
    segments = ThinScrollBarRender.render_bar(
        size=20, virtual_size=60, window_size=20, position=0, vertical=False,
        back_color=Color.parse("#000000"), bar_color=Color.parse("#2e2e2e")).segments  # fmt: skip
    assert len(segments) == 20
    assert {s.text for s in segments} == {"▃", " "}
    assert sum(s.text == "▃" for s in segments) == 7


class _Host(App):
    def get_css_variables(self) -> dict[str, str]:
        variables = super().get_css_variables()
        for name in ("playback-bar-bg", "progress-filled", "progress-empty", "active-tab",
                     "inactive-tab", "selected-item"):  # fmt: skip
            variables.setdefault(name, "#000000")
        return variables

    def compose(self) -> ComposeResult:
        yield PlaybackBar(id="playback-bar")


async def test_the_player_bar_lays_out_like_the_web_player():
    app = _Host()
    async with app.run_test(size=(140, 20)) as pilot:
        await pilot.pause()
        bar = app.query_one(PlaybackBar)
        assert bar.outer_size.height == 6
        seek = app.query_one("#pb-progress")
        assert seek.region.y == bar.region.y and seek.region.width == bar.region.width
        groups = [app.query_one(s).region for s in ("#pb-left", "#pb-center", "#pb-right")]
        assert [g.x for g in groups] == sorted(g.x for g in groups)
        middles = {g.y + g.height // 2 for g in groups}
        assert len(middles) == 1, "the three groups share one middle row"


async def test_the_time_shows_beside_the_transport_buttons():
    app = _Host()
    async with app.run_test(size=(140, 20)) as pilot:
        app.query_one(PlaybackBar).update_position(75, 225)
        await pilot.pause()
        assert str(app.query_one("#pb-time").render()) == "1:15 / 3:45"


async def test_bar_icons_are_one_cell_greyscale_and_the_theme_colour_when_on():
    from rich.cells import cell_len

    from ytm_player.services.queue import RepeatMode
    from ytm_player.ui.theme import get_theme

    app = _Host()
    async with app.run_test(size=(140, 20)) as pilot:
        bar = app.query_one(PlaybackBar)
        shuffle, repeat = app.query_one("#pb-shuffle"), app.query_one("#pb-repeat")
        off = [shuffle.render(), repeat.render()]
        assert all(cell_len(str(t)) == 1 for t in off)
        assert all(get_theme().primary not in str(t.style) for t in off)
        bar.update_shuffle(True)
        bar.update_repeat(RepeatMode.ALL)
        await pilot.pause()
        on = [shuffle.render(), repeat.render()]
        assert all(get_theme().primary in str(t.style) for t in on)
