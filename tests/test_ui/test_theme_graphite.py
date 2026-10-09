"""Graphite theme: primary follows the Caelestia wallpaper scheme."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock

import pytest
from textual.color import Color

from ytm_player.app._app import YTMPlayerApp
from ytm_player.config.settings import Settings
from ytm_player.ui.theme import (
    GRAPHITE_NAME,
    YOUTUBE_RED,
    build_graphite_theme,
    caelestia_primary,
    caelestia_scheme_path,
)


@pytest.fixture
def state_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    return tmp_path


def _write_scheme(state_home, primary) -> None:
    scheme = state_home / "caelestia" / "scheme.json"
    scheme.parent.mkdir(parents=True, exist_ok=True)
    scheme.write_text(json.dumps({"name": "dynamic", "colours": {"primary": primary}}))


def test_scheme_path_follows_xdg_state_home(state_home):
    assert caelestia_scheme_path() == state_home / "caelestia" / "scheme.json"


def test_reads_primary_without_hash(state_home):
    _write_scheme(state_home, "F8B6B6")
    assert caelestia_primary() == "#f8b6b6"


def test_reads_primary_with_hash(state_home):
    _write_scheme(state_home, "#3a7bd5")
    assert caelestia_primary() == "#3a7bd5"


@pytest.mark.parametrize("bad", ["", "f8b6b", "zzzzzz", 123, None])
def test_rejects_invalid_primary(state_home, bad):
    _write_scheme(state_home, bad)
    assert caelestia_primary() is None


def test_missing_scheme_returns_none(state_home):
    assert caelestia_primary() is None


def test_unparseable_scheme_returns_none(state_home):
    scheme = state_home / "caelestia" / "scheme.json"
    scheme.parent.mkdir(parents=True)
    scheme.write_text("{not json")
    assert caelestia_primary() is None


def test_falls_back_to_youtube_red(state_home):
    assert build_graphite_theme().primary == YOUTUBE_RED


def test_uses_wallpaper_primary(state_home):
    _write_scheme(state_home, "3a7bd5")
    theme = build_graphite_theme()
    assert theme.name == GRAPHITE_NAME
    assert theme.primary == "#3a7bd5"
    assert theme.variables["progress-filled"] == "#3a7bd5"


def test_highlights_derive_from_primary(state_home):
    red = build_graphite_theme("#ff0000")
    blue = build_graphite_theme("#0000ff")
    assert red.variables["selected-item"] != blue.variables["selected-item"]
    assert red.accent != blue.accent
    assert red.variables["lyrics-current"] == red.accent
    # The selection tint stays a dark tone near the panel colour.
    assert Color.parse(red.variables["selected-item"]).brightness < 0.25


def test_border_is_a_hairline_not_primary(state_home):
    variables = build_graphite_theme("#ff0000").variables
    assert variables["border"] == "#1e1e23"
    assert variables["border-blurred"] == "#1e1e23"


def test_playlist_box_frame_is_transparent(state_home):
    assert build_graphite_theme("#ff0000").variables["panel-frame"] == "transparent"


def _app(monkeypatch, theme_name: str) -> YTMPlayerApp:
    settings = Settings()
    settings.ui.theme = theme_name
    monkeypatch.setattr("ytm_player.app._app.get_settings", lambda: settings)
    monkeypatch.setattr("ytm_player.app._app.get_keymap", MagicMock())
    monkeypatch.setattr("ytm_player.app._app.get_theme", MagicMock())
    return YTMPlayerApp()


def _graphite(app: YTMPlayerApp):
    theme = app.get_theme(GRAPHITE_NAME)
    assert theme is not None
    return theme


def test_app_registers_graphite(state_home, monkeypatch):
    app = _app(monkeypatch, GRAPHITE_NAME)
    assert app.theme == GRAPHITE_NAME
    assert _graphite(app).primary == YOUTUBE_RED


def test_poll_rebuilds_graphite_when_scheme_changes(state_home, monkeypatch):
    app = _app(monkeypatch, GRAPHITE_NAME)
    app._graphite_scheme_mtime = app._caelestia_scheme_mtime()
    app.watch_theme = MagicMock()

    _write_scheme(state_home, "3a7bd5")
    app._poll_caelestia_scheme()

    assert _graphite(app).primary == "#3a7bd5"
    app.watch_theme.assert_called_once_with(GRAPHITE_NAME)


def test_poll_skips_unchanged_scheme(state_home, monkeypatch):
    _write_scheme(state_home, "3a7bd5")
    app = _app(monkeypatch, GRAPHITE_NAME)
    app._graphite_scheme_mtime = app._caelestia_scheme_mtime()
    app.watch_theme = MagicMock()

    app._poll_caelestia_scheme()

    app.watch_theme.assert_not_called()


def test_poll_updates_graphite_but_keeps_other_theme_active(state_home, monkeypatch):
    app = _app(monkeypatch, "ytm-dark")
    app._graphite_scheme_mtime = app._caelestia_scheme_mtime()
    app.watch_theme = MagicMock()

    _write_scheme(state_home, "3a7bd5")
    scheme = caelestia_scheme_path()
    os.utime(scheme, (1, 1))
    app._poll_caelestia_scheme()

    assert app.theme == "ytm-dark"
    assert _graphite(app).primary == "#3a7bd5"
    app.watch_theme.assert_not_called()


def test_panel_frame_defaults_to_secondary_on_other_themes(state_home, monkeypatch):
    app = _app(monkeypatch, "ytm-dark")
    variables = app.get_css_variables()
    assert variables["panel-frame"] == variables["secondary"]


def test_panel_frame_is_transparent_on_graphite(state_home, monkeypatch):
    app = _app(monkeypatch, GRAPHITE_NAME)
    assert app.get_css_variables()["panel-frame"] == "transparent"
