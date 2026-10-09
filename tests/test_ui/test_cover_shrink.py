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

    assert out.name == "big.176x176.r.png"
    with Image.open(out) as image:
        assert image.size == (176, 176)
    stamp = out.stat().st_mtime_ns
    assert cover.shrink_to_cells(src, 22, 11) == out
    assert out.stat().st_mtime_ns == stamp, "the cached copy was rebuilt"


def test_a_broken_image_falls_back_to_the_original(tmp_path):
    src = tmp_path / "broken.img"
    src.write_bytes(b"not an image")
    assert cover.shrink_to_cells(src, 22, 11) == src


def test_the_same_cover_shrunk_twice_at_once_gives_both_the_copy(tmp_path, monkeypatch):
    """Regression: two covers with one URL shared a temp name, and the second rename failed."""
    from concurrent.futures import ThreadPoolExecutor

    import textual_image._terminal as terminal

    monkeypatch.setattr(terminal, "get_cell_size", lambda: SimpleNamespace(width=8, height=16))
    src = tmp_path / "big.img"
    Image.new("RGB", (576, 576), "red").save(src, format="JPEG")

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda _: cover.shrink_to_cells(src, 22, 11), range(8)))

    assert {r.name for r in results} == {"big.176x176.r.png"}
    assert not list(tmp_path.glob("*.part"))


def test_covers_get_softly_rounded_transparent_corners(tmp_path, monkeypatch):
    import textual_image._terminal as terminal

    monkeypatch.setattr(terminal, "get_cell_size", lambda: SimpleNamespace(width=8, height=16))
    src = tmp_path / "big.img"
    Image.new("RGB", (576, 576), "red").save(src, format="JPEG")
    with Image.open(cover.shrink_to_cells(src, 22, 11)) as out:
        assert out.mode == "RGBA"
        assert out.getpixel((0, 0))[3] == 0, "corner is transparent"
        assert out.getpixel((88, 88))[3] == 255, "middle is solid"
        assert out.getpixel((88, 0))[3] == 255, "edge midpoints are not cut"
