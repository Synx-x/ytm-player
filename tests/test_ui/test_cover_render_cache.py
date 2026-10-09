"""Kitty covers encode once per size, and leave kitty when they unmount.

Regression: textual-image re-encoded and re-sent every cover on every render.
A grid re-lays-out per card it mounts, so 20 covers cost about 200 encodes on the
UI thread and the page stayed blank for seconds.
"""

from __future__ import annotations

from types import SimpleNamespace

from ytm_player.ui.widgets.cover import _cached_kitty_image


class _FakeRenderable:
    def __init__(self) -> None:
        self.cleaned = False

    def cleanup(self) -> None:
        self.cleaned = True


class _FakeBase:
    """Stands in for textual-image's widget: render() always builds a new renderable."""

    def __init__(self) -> None:
        self._image = "cover.jpg"
        self._renderable = None
        self.size = SimpleNamespace(width=22, height=11)
        self.builds = 0

    def _get_styled_size(self):
        return ("auto", "auto")

    def render(self):
        if self._renderable:
            self._renderable.cleanup()
        self.builds += 1
        self._renderable = _FakeRenderable()
        return self._renderable


def test_repeated_renders_at_one_size_build_once():
    widget = _cached_kitty_image(_FakeBase)()
    first = widget.render()
    for _ in range(10):
        assert widget.render() is first
    assert widget.builds == 1


def test_a_new_size_builds_again():
    widget = _cached_kitty_image(_FakeBase)()
    widget.render()
    widget.size = SimpleNamespace(width=30, height=15)
    widget.render()
    assert widget.builds == 2


def test_unmount_deletes_the_image_from_kitty():
    widget = _cached_kitty_image(_FakeBase)()
    renderable = widget.render()
    widget.on_unmount()
    assert renderable.cleaned and widget._renderable is None


def test_the_class_still_reads_as_the_kitty_widget():
    assert _cached_kitty_image(_FakeBase).__name__ == "TGPImage"
