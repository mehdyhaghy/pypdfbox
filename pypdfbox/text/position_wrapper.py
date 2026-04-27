from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .text_position import TextPosition


class PositionWrapper:
    """Wraps a :class:`TextPosition` for line-detection bookkeeping.

    Mirrors ``org.apache.pdfbox.text.PositionWrapper`` from upstream
    PDFBox 3.0.x. ``PDFTextStripper.writePage`` builds a list of these
    wrappers when ``sortByPosition`` is true (or whenever paragraph
    boundaries need to be inferred) and toggles the boolean flags as it
    walks the sorted text. Each flag is then consumed when emitting line
    or paragraph separators.

    Upstream exposes the wrapped position through ``getTextPosition()``
    and the four boolean predicates listed below — keeping the API
    surface in lockstep so a port of ``PDFTextStripper`` can use these
    wrappers without adapter shims.
    """

    __slots__ = (
        "_position",
        "_line_start",
        "_paragraph_start",
        "_page_break",
        "_hanging_indent",
        "_article_start",
    )

    def __init__(self, position: TextPosition) -> None:
        self._position: TextPosition = position
        self._line_start: bool = False
        self._paragraph_start: bool = False
        self._page_break: bool = False
        self._hanging_indent: bool = False
        self._article_start: bool = False

    # ------------------------------------------------------------------
    # Wrapped position
    # ------------------------------------------------------------------

    def get_text_position(self) -> TextPosition:
        """Return the wrapped :class:`TextPosition`."""
        return self._position

    # ------------------------------------------------------------------
    # Line start
    # ------------------------------------------------------------------

    def is_line_start(self) -> bool:
        """True when this wrapper represents the first run of a line."""
        return self._line_start

    def set_line_start(self) -> None:
        """Mark this wrapper as a line start.

        Upstream's setter is a no-arg ``setLineStart()`` that flips the
        flag to ``true`` — there is no companion ``clear``. We preserve
        that asymmetry intentionally.
        """
        self._line_start = True

    # ------------------------------------------------------------------
    # Paragraph start
    # ------------------------------------------------------------------

    def is_paragraph_start(self) -> bool:
        """True when this wrapper begins a new paragraph."""
        return self._paragraph_start

    def set_paragraph_start(self) -> None:
        """Mark this wrapper as a paragraph start."""
        self._paragraph_start = True

    # ------------------------------------------------------------------
    # Page break
    # ------------------------------------------------------------------

    def is_page_break(self) -> bool:
        """True when this wrapper sits across a page boundary."""
        return self._page_break

    def set_page_break(self) -> None:
        """Mark this wrapper as a page break."""
        self._page_break = True

    # ------------------------------------------------------------------
    # Hanging indent
    # ------------------------------------------------------------------

    def is_hanging_indent(self) -> bool:
        """True when this wrapper participates in a hanging indent."""
        return self._hanging_indent

    def set_hanging_indent(self) -> None:
        """Mark this wrapper as a hanging indent."""
        self._hanging_indent = True

    # ------------------------------------------------------------------
    # Article start
    # ------------------------------------------------------------------

    def is_article_start(self) -> bool:
        """True when this wrapper begins a new article (bead)."""
        return self._article_start

    def set_article_start(self) -> None:
        """Mark this wrapper as an article start."""
        self._article_start = True


__all__ = ["PositionWrapper"]
