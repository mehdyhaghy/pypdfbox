"""Pure-text search backend for the text-searcher panel.

Ported from ``org.apache.pdfbox.debugger.ui.textsearcher.SearchEngine``.

The original class operated on a Swing ``Document``/``Highlighter`` pair.
This port replaces that with a plain "text + add-highlight callback"
interface so the engine remains usable both from the Tkinter panel
(:class:`pypdfbox.debugger.ui.textsearcher.SearchPanel`) and from pure-logic
tests. Each match is returned as a :class:`Highlight` record carrying the
``[start, end)`` offsets and the painter tag with which the panel should
render it.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class Highlight:
    """Inclusive-start / exclusive-end character offset for one match.

    The :attr:`painter` field mirrors the upstream
    ``Highlighter.HighlightPainter`` reference; we use an opaque string tag
    name so the panel can map it onto whatever rendering tag it wants to
    apply.
    """

    start_offset: int
    end_offset: int
    painter: str

    # ``Highlighter.Highlight`` exposes the offsets via getter methods;
    # keep camelCase-to-snake_case parity for source-level familiarity.
    def get_start_offset(self) -> int:
        return self.start_offset

    def get_end_offset(self) -> int:
        return self.end_offset

    def get_painter(self) -> str:
        return self.painter


# A callback ``add_highlight(start, end, painter) -> None`` (e.g. a
# ``tk.Text`` ``tag_add``) plus a ``remove_all_highlights()`` callback are
# all the engine needs to talk to the surrounding widget.
AddHighlight = Callable[[int, int, str], None]
RemoveAllHighlights = Callable[[], None]
GetText = Callable[[], str]


class SearchEngine:
    """Search a text component for occurrences of a search key."""

    def __init__(
        self,
        get_text: GetText,
        add_highlight: AddHighlight,
        remove_all_highlights: RemoveAllHighlights,
        painter: str,
    ) -> None:
        """Wire the engine to its text source and highlight sink.

        :param get_text: callable returning the current document text.
        :param add_highlight: callable that adds one painted highlight span.
        :param remove_all_highlights: callable that removes every highlight.
        :param painter: opaque painter token forwarded with each
            :class:`Highlight` so callers can map it to a rendering tag.
        """
        self._get_text = get_text
        self._add_highlight = add_highlight
        self._remove_all_highlights = remove_all_highlights
        self._painter = painter

    def search(
        self,
        search_key: str | None,
        is_case_sensitive: bool,
    ) -> list[Highlight]:
        """Search for ``search_key`` and return one :class:`Highlight` per match.

        :param search_key: the literal substring to look up. ``None`` returns
            an empty list (matching upstream behavior); an empty string
            clears existing highlights and returns an empty list.
        :param is_case_sensitive: when ``False`` the comparison is performed
            on the lower-cased document and key (mirrors upstream).
        :return: a list of highlights in document order.
        """
        highlights: list[Highlight] = []

        if search_key is None:
            return highlights

        self._remove_all_highlights()

        if search_key == "":
            return highlights

        try:
            text_content = self._get_text()
        except Exception:  # pragma: no cover - mirrors upstream BadLocationException
            LOG.exception("failed to read document text")
            return highlights

        if not is_case_sensitive:
            text_content = text_content.lower()
            search_key = search_key.lower()

        search_key_length = len(search_key)
        if search_key_length == 0:
            return highlights

        start_at = 0
        while True:
            offset = text_content.find(search_key, start_at)
            if offset == -1:
                break
            end = offset + search_key_length
            self._add_highlight(offset, end, self._painter)
            highlights.append(Highlight(offset, end, self._painter))
            start_at = end
        return highlights

    # ------------------------------------------------------------------
    # Project extension: regex mode.
    #
    # The PRD allows behavioral *extensions* as long as upstream parity
    # for documented behavior is preserved. The Tkinter panel exposes a
    # "regex" checkbox, so the engine grows a sibling method that uses
    # Python's stdlib ``re`` for matching.
    # ------------------------------------------------------------------

    def search_regex(
        self,
        pattern: str | None,
        is_case_sensitive: bool,
    ) -> list[Highlight]:
        """Search for matches of ``pattern`` interpreted as a regex."""
        highlights: list[Highlight] = []
        if pattern is None:
            return highlights
        self._remove_all_highlights()
        if pattern == "":
            return highlights
        try:
            text_content = self._get_text()
        except Exception:  # pragma: no cover
            LOG.exception("failed to read document text")
            return highlights
        flags = 0 if is_case_sensitive else re.IGNORECASE
        try:
            compiled = re.compile(pattern, flags)
        except re.error:
            return highlights
        for match in compiled.finditer(text_content):
            start, end = match.span()
            if start == end:
                # Skip zero-width matches to avoid infinite loops and to
                # match upstream's "non-empty key" expectation.
                continue
            self._add_highlight(start, end, self._painter)
            highlights.append(Highlight(start, end, self._painter))
        return highlights
