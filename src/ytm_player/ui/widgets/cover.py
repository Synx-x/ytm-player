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

        _image_widget = TGPImage if AutoRenderable is TGPRenderable else HalfcellImage
    except Exception:
        logger.debug("textual-image unavailable, covers use half-blocks", exc_info=True)
        _image_widget = None


def image_widget() -> type | None:
    """The textual-image widget class to use, or None for the half-block fallback."""
    if not _primed:
        prime_image_support()
    return _image_widget


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

    def _load(self, url: str) -> None:
        self._token += 1
        token = self._token
        self.run_worker(self._fetch_and_show(url, token), exclusive=True, group="cover")

    async def _fetch_and_show(self, url: str, token: int) -> None:
        path = await asyncio.to_thread(fetch_thumbnail, url) if url else None
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
            await self.mount(widget_cls(str(path), classes="cover-image"))
        except Exception:
            logger.debug("Cover render failed: %s", url, exc_info=True)
            await self.mount(Static("♫", classes="cover-placeholder"))
