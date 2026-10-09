"""Covers are shrunk to their cell size off the UI thread, and the copy is reused."""

from __future__ import annotations

from types import SimpleNamespace

from PIL import Image

from ytm_player.ui.widgets import cover


def test_shrinks_to_the_cells_pixel_box_and_caches(tmp_path, monkeypatch):
    import textual_image._terminal as terminal

    monkeypatch.setattr(terminal, "get_cell_size", lambda: SimpleNamespace(width=8, height=16))
    src = tmp_path / "big.img"
    Image.new("RGB", (576, 576), "red").save(src, format="JPEG")

    out = cover.shrink_to_cells(src, 22, 11)

    assert out.name == "big.176x176.png"
    with Image.open(out) as image:
        assert image.size == (176, 176)
    stamp = out.stat().st_mtime_ns
    assert cover.shrink_to_cells(src, 22, 11) == out
    assert out.stat().st_mtime_ns == stamp, "the cached copy was rebuilt"


def test_a_broken_image_falls_back_to_the_original(tmp_path):
    src = tmp_path / "broken.img"
    src.write_bytes(b"not an image")
    assert cover.shrink_to_cells(src, 22, 11) == src
