"""Draw every character in the terminal font's regular face.

kitty draws bold and italic text with separate font faces, so a screen that
mixes them looks like it uses several fonts. This filter removes both at
render time. It covers CSS text-style, inline Rich styles and Textual's own
widgets. Colour and dim still mark emphasis.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

from rich.segment import Segment
from rich.style import Style
from textual.color import Color
from textual.filter import LineFilter

_REGULAR = Style(bold=False, italic=False)


@lru_cache(1024)
def _regular(style: Style) -> Style:
    return style + _REGULAR


class RegularWeight(LineFilter):
    """Replace bold and italic with the regular face."""

    def apply(self, segments: list[Segment], background: Color) -> list[Segment]:
        return [
            Segment(segment.text, _regular(segment.style), segment.control)
            if segment.style is not None and (segment.style.bold or segment.style.italic)
            else segment
            for segment in segments
        ]


_FILTER = RegularWeight()


class RegularWeightMixin:
    """App mixin that adds RegularWeight after Textual's own line filters."""

    def get_line_filters(self) -> Sequence[LineFilter]:
        return [*super().get_line_filters(), _FILTER]  # type: ignore[misc]
