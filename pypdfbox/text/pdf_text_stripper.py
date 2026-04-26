from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSName, COSNumber, COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser

from .text_position import TextPosition

if TYPE_CHECKING:
    from pypdfbox.cos import COSBase

    from pypdfbox.pdmodel import PDDocument, PDPage


class PDFTextStripper:
    """Lite single-column text extractor.

    Mirrors the public surface of
    ``org.apache.pdfbox.text.PDFTextStripper`` for the subset that
    pypdfbox supports today: page-range selection, configurable line and
    word separators, and a per-page extraction hook (``process_page``).
    Layout reconstruction, multi-column reading-order sorting, font-width-
    based word spacing, ``/MarkInfo`` semantic awareness, ``/ToUnicode``
    CMap decoding, and paragraph detection are deliberately deferred —
    see ``CHANGES.md`` for the consolidated diverge list.

    The walk parses each page's content stream via :class:`PDFStreamParser`
    directly rather than going through
    :class:`pypdfbox.contentstream.operator.OperatorRegistry`. The
    registry is for typed, side-effecting dispatch (graphics-state mutation
    during rendering); the stripper just needs to fold operator tuples
    into a small text-state machine.
    """

    # Heuristic threshold (in multiples of the current font size) above
    # which a horizontal advance counts as a word break rather than a
    # tight glyph-to-glyph step. Loose because lite-mode lacks real
    # glyph-width metrics, but tight enough that two ``Tj`` calls on the
    # same line emit a single space when they're visibly apart.
    _WORD_GAP_FACTOR: float = 1.5

    def __init__(self) -> None:
        self._start_page: int = 1
        self._end_page: int = sys.maxsize
        self._should_separate_by_beads: bool = True  # no-op for lite
        self._paragraph_start: str = ""
        self._paragraph_end: str = "\n"
        self._page_start: str = ""
        self._page_end: str = "\n"
        self._word_separator: str = " "
        self._line_separator: str = "\n"

    # ---------- configuration accessors ----------

    def set_start_page(self, page: int) -> None:
        self._start_page = int(page)

    def get_start_page(self) -> int:
        return self._start_page

    def set_end_page(self, page: int) -> None:
        self._end_page = int(page)

    def get_end_page(self) -> int:
        return self._end_page

    def set_word_separator(self, separator: str) -> None:
        self._word_separator = separator

    def get_word_separator(self) -> str:
        return self._word_separator

    def set_line_separator(self, separator: str) -> None:
        self._line_separator = separator

    def get_line_separator(self) -> str:
        return self._line_separator

    def set_paragraph_start(self, value: str) -> None:
        self._paragraph_start = value

    def get_paragraph_start(self) -> str:
        return self._paragraph_start

    def set_paragraph_end(self, value: str) -> None:
        self._paragraph_end = value

    def get_paragraph_end(self) -> str:
        return self._paragraph_end

    def set_page_start(self, value: str) -> None:
        self._page_start = value

    def get_page_start(self) -> str:
        return self._page_start

    def set_page_end(self, value: str) -> None:
        self._page_end = value

    def get_page_end(self) -> str:
        return self._page_end

    def set_should_separate_by_beads(self, value: bool) -> None:
        self._should_separate_by_beads = bool(value)

    def get_should_separate_by_beads(self) -> bool:
        return self._should_separate_by_beads

    # ---------- public API ----------

    def get_text(self, document: PDDocument) -> str:
        """Walk pages from ``start_page`` (1-based, inclusive) through
        ``min(end_page, page_count)`` and return the concatenated
        extracted text. Each page is wrapped in
        ``page_start`` / ``page_end``.
        """
        pages = list(document.get_pages())
        total = len(pages)
        first = max(1, self._start_page)
        last = min(self._end_page, total)
        if first > last:
            return ""
        out: list[str] = []
        for one_based in range(first, last + 1):
            page = pages[one_based - 1]
            out.append(self._page_start)
            out.append(self.process_page(page))
            out.append(self._page_end)
        return "".join(out)

    def process_page(self, page: PDPage) -> str:
        """Extract text from a single page. Subclasses may override to
        plug in custom layout logic without re-implementing the parser
        loop. Mirrors upstream's ``PDFTextStripper.processPage`` hook.
        """
        body = page.get_contents()
        if not body:
            return ""
        positions = self._extract_positions(body)
        return self._format_positions(positions)

    # ---------- parser walk ----------

    def _extract_positions(self, body: bytes) -> list[TextPosition]:
        """Run the content stream through :class:`PDFStreamParser` and
        emit a flat list of :class:`TextPosition`. Operands are buffered
        in a list and flushed when an operator token is seen — mirroring
        upstream's ``processOperator(operator, operands)`` pattern.
        """
        positions: list[TextPosition] = []
        operands: list[COSBase] = []

        # Text-state machine — flat, no nested graphics-state stack.
        # ``q``/``Q`` graphics-state stacking would matter for CTM-aware
        # extraction; lite mode ignores the CTM entirely and tracks the
        # text matrix flat. See CHANGES.md.
        state = _TextState()

        with RandomAccessReadBuffer(body) as src:
            parser = PDFStreamParser(src)
            for token in parser.tokens():
                if isinstance(token, Operator):
                    self._dispatch(token.get_name(), operands, state, positions)
                    operands = []
                else:
                    operands.append(token)

        return positions

    def _dispatch(
        self,
        op: str,
        operands: list[COSBase],
        state: _TextState,
        positions: list[TextPosition],
    ) -> None:
        if op == "BT":
            # Begin text object — reset text matrix and line matrix to
            # identity (PDF 1.7 §9.4.1).
            state.text_x = 0.0
            state.text_y = 0.0
            state.line_x = 0.0
            state.line_y = 0.0
        elif op == "ET":
            # End text object — nothing to flush in lite mode; positions
            # are emitted as Tj/TJ/'/" operators run.
            return
        elif op == "Tf":
            if len(operands) >= 2:
                name = operands[0]
                size = operands[1]
                if isinstance(name, COSName):
                    state.font_name = name.get_name()
                if isinstance(size, COSNumber):
                    state.font_size = size.float_value()
        elif op == "TL":
            if operands and isinstance(operands[0], COSNumber):
                state.leading = operands[0].float_value()
        elif op == "Td":
            tx, ty = _two_numbers(operands)
            # Translate the line matrix by (tx, ty), then reset the text
            # matrix to the new line origin (PDF 1.7 §9.4.2).
            state.line_x += tx
            state.line_y += ty
            state.text_x = state.line_x
            state.text_y = state.line_y
        elif op == "TD":
            tx, ty = _two_numbers(operands)
            # ``TD`` = ``-ty TL`` then ``tx ty Td``.
            state.leading = -ty
            state.line_x += tx
            state.line_y += ty
            state.text_x = state.line_x
            state.text_y = state.line_y
        elif op == "Tm":
            # ``a b c d e f Tm`` — set both text matrix and line matrix to
            # the supplied 3x3 affine. Lite mode tracks just the
            # translation components (e, f); rotation/scale would only
            # matter once we move to glyph-aware extraction.
            if len(operands) >= 6 and all(
                isinstance(o, COSNumber) for o in operands[:6]
            ):
                e = operands[4].float_value()  # type: ignore[union-attr]
                f = operands[5].float_value()  # type: ignore[union-attr]
                state.line_x = e
                state.line_y = f
                state.text_x = e
                state.text_y = f
        elif op == "T*":
            # Move to start of next line — equivalent to ``0 -leading Td``.
            state.line_y -= state.leading
            state.text_x = state.line_x
            state.text_y = state.line_y
        elif op == "Tj":
            if operands and isinstance(operands[0], COSString):
                self._emit(operands[0], state, positions)
        elif op == "TJ":
            if operands and isinstance(operands[0], COSArray):
                self._emit_tj_array(operands[0], state, positions)
        elif op == "'":
            # Move to next line then show string.
            state.line_y -= state.leading
            state.text_x = state.line_x
            state.text_y = state.line_y
            if operands and isinstance(operands[0], COSString):
                self._emit(operands[0], state, positions)
        elif op == '"':
            # ``aw ac string "`` — set word + char spacing, next line, show.
            if (
                len(operands) >= 3
                and isinstance(operands[0], COSNumber)
                and isinstance(operands[1], COSNumber)
                and isinstance(operands[2], COSString)
            ):
                state.word_spacing = operands[0].float_value()
                state.char_spacing = operands[1].float_value()
                state.line_y -= state.leading
                state.text_x = state.line_x
                state.text_y = state.line_y
                self._emit(operands[2], state, positions)
        elif op == "Tc":
            if operands and isinstance(operands[0], COSNumber):
                state.char_spacing = operands[0].float_value()
        elif op == "Tw":
            if operands and isinstance(operands[0], COSNumber):
                state.word_spacing = operands[0].float_value()
        # Other operators (graphics state, paths, colour, marked content,
        # etc.) are intentionally ignored — they have no effect on the
        # lite text stream.

    # ---------- emission ----------

    def _emit(
        self,
        s: COSString,
        state: _TextState,
        positions: list[TextPosition],
    ) -> None:
        text = s.get_string()
        if not text:
            return
        positions.append(
            TextPosition(
                text=text,
                x=state.text_x,
                y=state.text_y,
                font_size=state.font_size,
                font_name=state.font_name,
            )
        )
        # Advance the text origin by a coarse approximation of the run
        # width. We have no glyph metrics in lite mode; using
        # ``len(text) * font_size * 0.5`` gives a decent monospace-ish
        # estimate that keeps successive Tj's on the same line distinct
        # for the word-gap heuristic in ``_format_positions``.
        state.text_x += len(text) * state.font_size * 0.5

    def _emit_tj_array(
        self,
        arr: COSArray,
        state: _TextState,
        positions: list[TextPosition],
    ) -> None:
        for entry in arr:
            if isinstance(entry, COSString):
                self._emit(entry, state, positions)
            elif isinstance(entry, COSNumber):
                # ``TJ`` numeric adjustments are in thousandths of an em,
                # subtracted (negative = move forward). Lite mode only
                # uses this to nudge the text-x cursor so the word-gap
                # heuristic can detect spacing inserted via ``TJ``.
                state.text_x -= entry.float_value() * state.font_size / 1000.0

    # ---------- formatting ----------

    def _format_positions(self, positions: list[TextPosition]) -> str:
        """Walk ``positions`` in emission order and stitch them into a
        single string using the configured line and word separators.

        Heuristic (single-column reading order):
          - If ``y`` differs from the previous position's ``y`` by more
            than half the font size, emit a line separator.
          - Otherwise, if ``x`` jumps by more than ``_WORD_GAP_FACTOR``
            times the font size from the previous position's right edge,
            emit a word separator.
        """
        if not positions:
            return ""
        out: list[str] = []
        prev: TextPosition | None = None
        for pos in positions:
            if prev is not None:
                if abs(pos.y - prev.y) > max(prev.font_size, 0.1) * 0.5:
                    out.append(self._line_separator)
                else:
                    # Approximate previous run's right edge using the same
                    # 0.5-em-per-char estimate used in ``_emit``.
                    prev_right = prev.x + len(prev.text) * prev.font_size * 0.5
                    gap = pos.x - prev_right
                    if gap > prev.font_size * self._WORD_GAP_FACTOR:
                        out.append(self._word_separator)
            out.append(pos.text)
            prev = pos
        return "".join(out)


class _TextState:
    """Mutable text-state bag shared by the dispatcher and emitters."""

    __slots__ = (
        "text_x",
        "text_y",
        "line_x",
        "line_y",
        "leading",
        "font_size",
        "font_name",
        "char_spacing",
        "word_spacing",
    )

    def __init__(self) -> None:
        self.text_x: float = 0.0
        self.text_y: float = 0.0
        self.line_x: float = 0.0
        self.line_y: float = 0.0
        self.leading: float = 0.0
        self.font_size: float = 0.0
        self.font_name: str | None = None
        self.char_spacing: float = 0.0
        self.word_spacing: float = 0.0


def _two_numbers(operands: list[COSBase]) -> tuple[float, float]:
    """Pull two numeric operands; default to 0.0 on malformed input."""
    if len(operands) < 2:
        return 0.0, 0.0
    a, b = operands[0], operands[1]
    if not (isinstance(a, COSNumber) and isinstance(b, COSNumber)):
        return 0.0, 0.0
    return a.float_value(), b.float_value()


__all__ = ["PDFTextStripper"]
