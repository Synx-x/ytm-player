"""Scroll bars that show only while the pointer is over their list.

The app's stylesheet draws every scroll thumb in the background colour, so it
is invisible. This mixin gives the ``-scroll-hover`` class to each scrolling
container under the pointer, and the stylesheet shows the thumb there. The bars
keep their width, so nothing moves when a thumb appears.

Textual's ``:hover`` applies only to the widget directly under the pointer, not
to the list that holds it, so the class is set from the bubbling Enter event.
"""

from __future__ import annotations

from textual import events
from textual.containers import ScrollableContainer
from textual.dom import DOMNode
from textual.scroll_view import ScrollView

HOVER_CLASS = "-scroll-hover"


def scrolling_ancestors(node: DOMNode | None) -> set[DOMNode]:
    """*node* and its ancestors that scroll."""
    if node is None:
        return set()
    return {n for n in node.ancestors_with_self if isinstance(n, (ScrollableContainer, ScrollView))}


class AutoHideScrollbarsMixin:
    """App mixin that marks the scrolling containers under the pointer."""

    _scroll_hovered: set[DOMNode] = set()

    def _mark_scroll_hover(self, node: DOMNode | None) -> None:
        now = scrolling_ancestors(node)
        for gone in self._scroll_hovered - now:
            gone.remove_class(HOVER_CLASS)
        for new in now - self._scroll_hovered:
            new.add_class(HOVER_CLASS)
        self._scroll_hovered = now

    def on_enter(self, event: events.Enter) -> None:
        self._mark_scroll_hover(event.node)

    def on_leave(self, event: events.Leave) -> None:
        # The pointer left the window: Textual clears mouse_over before this arrives.
        if getattr(self, "mouse_over", None) is None:
            self._mark_scroll_hover(None)
