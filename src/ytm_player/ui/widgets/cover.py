"""Cover art drawn as a real image where the terminal supports one.

The widget downloads a thumbnail once into a disk cache, then mounts a
textual-image widget. Under kitty that draws the full-resolution picture
through the kitty graphics protocol. Without textual-image, or in a terminal
with no graphics protocol, it falls back to the half-block renderer.

textual-image has to query the terminal before Textual takes over stdin, so
``prime_image_support()`` must run before ``App.run()``. The CLI does that.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from pathlib import Path
from urllib.request import Request, urlopen

from textual.app import ComposeResult
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import Static

from ytm_player.config.paths import CACHE_DIR

logger = logging.getLogger(__name__)

THUMB_DIR = CACHE_DIR.parent / "covers"  # CACHE_DIR is the audio cache
_TIMEOUT = 8
_FIRST_PAINT_DELAY = 0.12  # seconds: several frames at Textual's 60 fps
_IMAGE_GAP = 0.03  # seconds between kitty images: about two frames
_image_lock: asyncio.Lock | None = None


def _image_turn() -> asyncio.Lock:
    """The lock that lets one cover at a time mount its kitty image."""
    global _image_lock
    if _image_lock is None:
        _image_lock = asyncio.Lock()
    return _image_lock
_image_widget: type | None = None
_primed = False


def prime_image_support() -> None:
    """Import textual-image while the terminal can still answer its queries."""
    global _image_widget, _primed
    _primed = True
    try:
        from textual_image.renderable import Image as AutoRenderable
        from textual_image.renderable.tgp import Image as TGPRenderable
        from textual_image.widget import HalfcellImage, TGPImage

        use_kitty = AutoRenderable is TGPRenderable and os.environ.get("YTM_COVERS") != "halfcell"
        _image_widget = _cached_kitty_image(TGPImage) if use_kitty else HalfcellImage
        _route_kitty_messages_through_textual()
    except Exception:
        logger.debug("textual-image unavailable, covers use half-blocks", exc_info=True)
        _image_widget = None


def _cached_kitty_image(base: type) -> type:
    """A kitty image widget that encodes and sends its picture once per size.

    textual-image builds a new renderable on every render: it rescales the
    picture, encodes it and sends it to kitty again. A grid re-lays-out once per
    card it mounts, so 20 covers cost about 200 encodes on the UI thread, and
    the page stayed blank for seconds. This keeps the renderable while the
    widget's size is unchanged, and deletes the image from kitty on unmount,
    which textual-image never does.
    """

    class CachedKittyImage(base):  # type: ignore[valid-type, misc]
        _render_key: object = None

        def render(self):  # type: ignore[no-untyped-def]
            if not self._image:
                return ""
            key = (self._get_styled_size(), self.size)
            if self._renderable is not None and key == self._render_key:
                return self._renderable
            self._render_key = key
            return super().render()

        def on_unmount(self) -> None:
            if self._renderable is not None:
                self._renderable.cleanup()
                self._renderable = None

    CachedKittyImage.__name__ = "TGPImage"  # has_real_images() checks this name
    return CachedKittyImage


def _route_kitty_messages_through_textual() -> None:
    """Send textual-image's kitty graphics messages through Textual's driver.

    It also narrows the library's image deletes to the one image meant.

    textual-image writes each image straight to ``sys.__stdout__`` while it
    renders, but Textual writes its frames from a separate writer thread. With
    many covers rendering at once the two writers interleave, which corrupts
    the frame: covers and the text around them stay blank. Writing through the
    driver queues each image message in order, just before the frame that
    shows it.
    """
    from textual._context import active_app
    from textual_image.renderable import tgp

    if getattr(tgp._send_tgp_message, "_routed", False):
        return
    direct = tgp._send_tgp_message

    def routed(*, payload: str | None = None, **kwargs: int | str | None) -> None:
        if kwargs.get("a") == "d" and "d" not in kwargs and kwargs.get("I") is not None:
            # textual-image cleans up with ``a=d,I=<id>``. In the kitty protocol a
            # delete with no ``d`` key removes every image on screen, and ``I`` is
            # an image number, not the id it transmitted with. So leaving one page
            # wiped the next page's covers. Delete only this image, and free it.
            kwargs = {"a": "d", "d": "I", "i": kwargs["I"], "q": 2}
        app = active_app.get(None)
        driver = getattr(app, "_driver", None)
        if driver is None:  # no running app: the library's own direct write
            direct(payload=payload, **kwargs)
            return
        sequence = "".join(
            [
                tgp._TGP_MESSAGE_START,
                ",".join(f"{k}={v}" for k, v in kwargs.items() if v is not None),
                f";{payload}" if payload else "",
                tgp._TGP_MESSAGE_END,
            ]
        )
        driver.write(tgp.prepare_terminal_sequence(sequence))

    routed._routed = True  # type: ignore[attr-defined]
    tgp._send_tgp_message = routed


def image_widget() -> type | None:
    """The textual-image widget class to use, or None for the half-block fallback."""
    if not _primed:
        prime_image_support()
    return _image_widget


def has_real_images() -> bool:
    """True when covers draw as real images (kitty graphics), not half-blocks."""
    widget = image_widget()
    return widget is not None and widget.__name__ == "TGPImage"


def best_thumbnail(item: dict, min_width: int = 226) -> str:
    """URL of the smallest thumbnail at least *min_width* wide, else the largest."""
    thumbs = item.get("thumbnails") or item.get("thumbnail") or []
    if isinstance(thumbs, dict):
        thumbs = thumbs.get("thumbnails", [])
    if not thumbs:
        return ""
    ranked = sorted(thumbs, key=lambda t: t.get("width") or 0)
    for thumb in ranked:
        if (thumb.get("width") or 0) >= min_width:
            return thumb.get("url", "")
    return ranked[-1].get("url", "")


def cached_path(url: str) -> Path:
    return THUMB_DIR / (hashlib.sha1(url.encode()).hexdigest() + ".img")


def fetch_thumbnail(url: str) -> Path | None:
    """Download *url* into the cover cache once. Blocking. Run it in a thread."""
    path = cached_path(url)
    if path.exists() and path.stat().st_size > 0:
        return path
    try:
        THUMB_DIR.mkdir(parents=True, exist_ok=True)
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=_TIMEOUT) as resp:  # noqa: S310 - YouTube image host
            data = resp.read()
        tmp = path.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(path)
        return path
    except Exception:
        logger.debug("Cover download failed: %s", url, exc_info=True)
        return None


def shrink_to_cells(path: Path, cols: int, rows: int) -> Path:
    """A copy of *path* sized for *cols* x *rows* terminal cells, cached beside it.

    Blocking; run it in a thread. Returns *path* unchanged when the cell size
    is unknown or the copy cannot be made.
    """
    try:
        from PIL import Image
        from textual_image._terminal import get_cell_size

        cell = get_cell_size()
        width, height = max(1, cols) * cell.width, max(1, rows) * cell.height
        target = path.with_name(f"{path.stem}.{width}x{height}.png")
        if not target.exists():
            with Image.open(path) as image:
                image = image.convert("RGB")
                image.thumbnail((width, height), Image.LANCZOS)
                tmp = target.with_suffix(".part")
                image.save(tmp, format="PNG")
                tmp.replace(target)
        return target
    except Exception:
        logger.debug("Could not shrink cover %s", path, exc_info=True)
        return path


class Cover(Container):
    """A fixed-size cover that shows a placeholder until the image arrives."""

    DEFAULT_CSS = """
    Cover {
        width: 22;
        height: 11;
        background: $surface;
    }
    Cover > .cover-placeholder {
        width: 1fr;
        height: 1fr;
        content-align: center middle;
        color: $text-muted;
    }
    Cover > .cover-image {
        width: 1fr;
        height: 1fr;
    }
    """

    url: reactive[str] = reactive("", init=False)

    def __init__(self, url: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_reactive(Cover.url, url)
        self._token = 0

    def compose(self) -> ComposeResult:
        yield Static("♫", classes="cover-placeholder")

    def on_mount(self) -> None:
        if self.url:
            self._load(self.url)

    def watch_url(self, url: str) -> None:
        self._load(url)

    # Same interface as AlbumArt, so the playback bar can hold either.
    def set_track(self, thumbnail_url: str = "") -> None:
        self.url = thumbnail_url

    def clear_track(self) -> None:
        self.url = ""

    def _load(self, url: str) -> None:
        self._token += 1
        token = self._token
        self.run_worker(self._fetch_and_show(url, token), exclusive=True, group="cover")

    async def _fetch_and_show(self, url: str, token: int) -> None:
        path = await asyncio.to_thread(fetch_thumbnail, url) if url else None
        if path is not None and has_real_images():
            # Shrink the picture to this cover's pixel size off the UI thread,
            # so the kitty encode that runs while drawing stays cheap.
            path = await asyncio.to_thread(shrink_to_cells, path, self.size.width, self.size.height)
        # Let the page paint its text before any kitty image arrives. A cover
        # already on disk otherwise renders in the same frame as the page's
        # first paint, and kitty then shows neither the covers nor the text
        # around them until something redraws the screen.
        await asyncio.sleep(_FIRST_PAINT_DELAY)
        if token != self._token or not self.is_attached:
            return
        await self.remove_children()
        widget_cls = image_widget()
        if path is None:
            await self.mount(Static("♫", classes="cover-placeholder"))
            return
        if widget_cls is None:
            from ytm_player.ui.widgets.album_art import AlbumArt

            art = AlbumArt(classes="cover-image")
            await self.mount(art)
            art.set_track(url)
            return
        try:
            # One kitty image at a time, with a short gap. A burst of cached
            # covers rendering together left the page blank in kitty, while
            # covers that arrived one by one from the network always drew.
            async with _image_turn():
                if token != self._token or not self.is_attached:
                    return
                await self.mount(widget_cls(str(path), classes="cover-image"))
                await asyncio.sleep(_IMAGE_GAP)
        except Exception:
            logger.debug("Cover render failed: %s", url, exc_info=True)
            await self.mount(Static("♫", classes="cover-placeholder"))
            return
