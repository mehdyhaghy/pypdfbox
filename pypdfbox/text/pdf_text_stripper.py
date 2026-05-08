from __future__ import annotations

import re
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSNumber, COSStream, COSString
from pypdfbox.fontbox.cmap import CMap, CMapParser
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser

from .text_position import TextPosition

if TYPE_CHECKING:
    from pypdfbox.cos import COSBase
    from pypdfbox.pdmodel import PDDocument, PDPage
    from pypdfbox.pdmodel.font import PDFont
    from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item import (
        PDOutlineItem,
    )


class _TextWriter(Protocol):
    def write(self, text: str) -> object: ...


class PDFTextStripper:
    """Lite single-column text extractor.

    Mirrors the public surface of
    ``org.apache.pdfbox.text.PDFTextStripper`` for the subset that
    pypdfbox supports today: page-range selection, configurable line and
    word separators, a per-page extraction hook (``process_page``),
    ``/ToUnicode`` CMap decoding, ``/Differences``-based glyph→unicode
    decoding for simple fonts without ``/ToUnicode``, and font-width-
    based word-gap heuristics when the font carries a ``/Widths``
    array. Layout reconstruction, multi-column reading-order sorting,
    ``/MarkInfo`` semantic awareness, and paragraph detection are
    deliberately deferred — see ``CHANGES.md`` for the consolidated
    diverge list.

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

    # Regex source list mirroring upstream's private
    # ``LIST_ITEM_EXPRESSIONS`` array — common bullet/number/letter list
    # markers (e.g. ``1.``, ``[2]``, ``A)``, ``iv.``). Consulted by
    # ``get_list_item_patterns`` when no caller-supplied list has been
    # set via ``set_list_item_patterns``. Order matters: most specific
    # patterns come first so ``match_pattern`` finds the tightest fit.
    LIST_ITEM_EXPRESSIONS: tuple[str, ...] = (
        r"\.",
        r"\d+\.",
        r"\[\d+\]",
        r"\d+\)",
        r"[A-Z]\.",
        r"[a-z]\.",
        r"[A-Z]\)",
        r"[a-z]\)",
        r"[IVXL]+\.",
        r"[ivxl]+\.",
    )

    def __init__(self) -> None:
        # Upstream defaults end_page to ``Integer.MAX_VALUE`` (2**31 - 1);
        # pypdfbox keeps ``sys.maxsize`` for backward compatibility with
        # the existing lite stripper API. The practical effect is the
        # same — both sentinels are clamped to ``len(pages)`` in
        # ``get_text``.
        self._start_page: int = 1
        self._end_page: int = sys.maxsize
        self._should_separate_by_beads: bool = True
        self._suppress_duplicate_overlapping_text: bool = True  # inert holder
        self._sort_by_position: bool = False
        # Y-axis up vs Y-axis down. Upstream PDFBox flips the axes via
        # ``setShouldFlipAxes`` so that a rotated-90 page can be extracted
        # as if it were portrait. Lite mode mirrors the flag and applies it
        # at the formatting layer: when ``True`` the line-break heuristic
        # treats *X* as the line-stepping axis and *Y* as the word-flow
        # axis (transposing the role of the two coordinates).
        self._flip_axes: bool = False
        self._paragraph_start: str = ""
        # Note: pypdfbox keeps the existing ``"\n"`` default for
        # ``paragraph_end`` for backward compatibility with the lite
        # extractor. Upstream PDFBox defaults this to ``""`` and emits
        # the line terminator separately; we collapse the two until the
        # stripper grows real paragraph detection.
        self._paragraph_end: str = "\n"
        self._page_start: str = ""
        self._page_end: str = "\n"
        self._word_separator: str = " "
        self._line_separator: str = "\n"
        # Article delimiters — emitted around every "article" (one
        # ``/StructTreeRoot/Article`` bead chain in upstream, but the
        # lite stripper treats the whole page body as a single article
        # so these wrap the same span as ``page_start`` / ``page_end``
        # when ``setShouldSeparateByBeads(true)`` is in effect.
        self._article_start: str = ""
        self._article_end: str = ""
        # Bookmark-bounded extraction range. ``start_bookmark`` (when
        # set) clamps ``start_page`` to the page the bookmark resolves
        # to; ``end_bookmark`` does the same for ``end_page``. Either
        # may be ``None``. Per upstream, when both are set the bookmark
        # range overrides the explicit page range.
        self._start_bookmark: PDOutlineItem | None = None
        self._end_bookmark: PDOutlineItem | None = None
        # Inert layout-tuning holders preserved for upstream API parity.
        # The lite extraction loop doesn't yet consume these; they exist
        # so callers can configure a stripper exactly as they would in
        # Java PDFBox without having to branch on which subset is wired.
        self._drop_threshold: float = 2.5
        self._indent_threshold: float = 2.0
        self._spacing_tolerance: float = 0.5
        self._average_char_tolerance: float = 0.3
        self._add_more_formatting: bool = False
        self._lenient_stream_parsing: bool = True
        # Inert holder mirroring upstream's
        # ``setIgnoreContentStreamSpaceGlyphs`` (added on 3.x). When
        # ``True``, the upstream extractor drops space glyphs found in
        # the content stream and relies purely on the gap heuristic for
        # word breaks. The lite stripper exposes the flag so callers
        # can configure it identically; the formatting layer doesn't
        # currently consume it because the lite walk doesn't materialise
        # individual space glyphs separately from their host runs.
        self._ignore_content_stream_space_glyphs: bool = False
        # 1-based current-page cursor. Upstream ``getCurrentPageNo``
        # exposes this for subclasses that want to disambiguate the
        # active page within ``processPage`` / ``startPage`` /
        # ``endPage`` hooks. Reset at the start of every ``get_text``
        # walk; updated by ``process_page`` once we know the page index.
        self._current_page_no: int = 0
        # Per-page CMap cache + active page handle for /ToUnicode lookup.
        # ``_cmap_cache`` keys are font resource names (the same ones the
        # ``Tf`` operator names); the value is the parsed ``CMap`` or
        # ``None`` when the font has no ``/ToUnicode`` entry. The cache
        # lifetime is one ``process_page`` invocation — we reset it on
        # entry so a fresh page's ``/Resources`` chain is consulted from
        # scratch (font dicts may be re-defined per page).
        self._cmap_cache: dict[str, CMap | None] = {}
        # Per-page typed-font cache. Lazily populated on ``Tf`` so the
        # glyph-decoder path (``/Differences`` lookup) and the width-based
        # word-gap heuristic can both consult ``PDFont.get_widths`` /
        # ``PDSimpleFont.decode`` without reparsing the font dict for
        # every show-text operator.
        self._font_cache: dict[str, PDFont | None] = {}
        self._active_page: PDPage | None = None
        self._active_cmap: CMap | None = None
        self._active_font: PDFont | None = None
        # Per-glyph advance for the active font in user-space units (i.e.
        # already multiplied by ``font_size`` and divided by 1000). When
        # ``None`` we fall back to the legacy 0.5-em estimate so unknown
        # fonts still produce monotonic text-x advances.
        self._active_avg_advance: float | None = None
        # Output writer captured by ``write_text`` (the lite stripper
        # otherwise routes everything through ``get_text``'s in-memory
        # sink). Mirrors upstream's protected ``output`` field; exposed
        # via ``get_output`` so subclasses that override hooks like
        # ``write_string`` can write directly to the active stream when
        # the caller drives extraction through ``write_text``.
        self._output: object | None = None
        # Per-page list of articles (each article is a list of
        # ``TextPosition``). Mirrors upstream's protected
        # ``charactersByArticle`` field. Lite mode treats every page as
        # a single article so the outer list is always length 1 after
        # ``process_page`` runs (cleared on entry to ``get_text``).
        self._characters_by_article: list[list[TextPosition]] = []
        # Lazily-populated list of compiled regex patterns matching
        # common list-item prefixes. Mirrors upstream's private
        # ``listOfPatterns`` field; exposed via
        # ``get_list_item_patterns`` / ``set_list_item_patterns``.
        self._list_of_patterns: list[re.Pattern[str]] | None = None

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

    def is_should_separate_by_beads(self) -> bool:
        # Upstream PDFBox exposes this as ``isShouldSeparateByBeads`` as
        # well as the ``getShouldSeparateByBeads`` alias on some 3.x
        # branches. Mirror both so callers can pick either spelling.
        return self._should_separate_by_beads

    def get_separate_by_beads(self) -> bool:
        # Upstream's primary getter on 3.x is the abbreviated
        # ``getSeparateByBeads`` (no ``Should`` infix); the longer
        # ``getShouldSeparateByBeads`` is the alias. Mirror the
        # primary spelling explicitly so direct ports of upstream
        # snippets work without rewriting the call site.
        return self._should_separate_by_beads

    def set_sort_by_position(self, value: bool) -> None:
        self._sort_by_position = bool(value)

    def is_sort_by_position(self) -> bool:
        return self._sort_by_position

    def get_sort_by_position(self) -> bool:
        # Upstream PDFBox 3.0.x exposes ``getSortByPosition`` as a
        # boolean alias of ``isSortByPosition``. Mirror both spellings
        # so callers can pick either.
        return self._sort_by_position

    def set_suppress_duplicate_overlapping_text(self, value: bool) -> None:
        self._suppress_duplicate_overlapping_text = bool(value)

    def is_suppress_duplicate_overlapping_text(self) -> bool:
        return self._suppress_duplicate_overlapping_text

    def get_suppress_duplicate_overlapping_text(self) -> bool:
        # Same alias situation as ``get_sort_by_position``.
        return self._suppress_duplicate_overlapping_text

    def set_drop_threshold(self, value: float) -> None:
        self._drop_threshold = float(value)

    def get_drop_threshold(self) -> float:
        return self._drop_threshold

    def set_indent_threshold(self, value: float) -> None:
        self._indent_threshold = float(value)

    def get_indent_threshold(self) -> float:
        return self._indent_threshold

    def set_spacing_tolerance(self, value: float) -> None:
        self._spacing_tolerance = float(value)

    def get_spacing_tolerance(self) -> float:
        return self._spacing_tolerance

    def set_average_char_tolerance(self, value: float) -> None:
        self._average_char_tolerance = float(value)

    def get_average_char_tolerance(self) -> float:
        return self._average_char_tolerance

    def set_add_more_formatting(self, value: bool) -> None:
        self._add_more_formatting = bool(value)

    def get_add_more_formatting(self) -> bool:
        return self._add_more_formatting

    def set_lenient_stream_parsing(self, value: bool) -> None:
        self._lenient_stream_parsing = bool(value)

    def is_lenient_stream_parsing(self) -> bool:
        return self._lenient_stream_parsing

    def set_ignore_content_stream_space_glyphs(self, value: bool) -> None:
        """Mirror upstream's ``setIgnoreContentStreamSpaceGlyphs``.

        When ``True`` the extractor is asked to ignore literal space
        glyphs encoded in the content stream and rely solely on the gap
        heuristic for word breaks. The lite stripper stores the flag for
        API parity; see CHANGES.md for the consumer-side gap.
        """
        self._ignore_content_stream_space_glyphs = bool(value)

    def get_ignore_content_stream_space_glyphs(self) -> bool:
        return self._ignore_content_stream_space_glyphs

    def set_should_flip_axes(self, value: bool) -> None:
        """Toggle axis-flipped extraction (transposes the role of X and Y
        in the line-break / word-gap heuristic). Mirrors upstream
        ``PDFTextStripper.setShouldFlipAxes`` (added in 3.x for sideways
        text on rotated pages)."""
        self._flip_axes = bool(value)

    def is_should_flip_axes(self) -> bool:
        return self._flip_axes

    def get_should_flip_axes(self) -> bool:
        # Upstream exposes both spellings on the 3.x branch.
        return self._flip_axes

    def set_article_start(self, value: str) -> None:
        self._article_start = value

    def get_article_start(self) -> str:
        return self._article_start

    def set_article_end(self, value: str) -> None:
        self._article_end = value

    def get_article_end(self) -> str:
        return self._article_end

    def set_start_bookmark(self, bookmark: PDOutlineItem | None) -> None:
        self._start_bookmark = bookmark

    def get_start_bookmark(self) -> PDOutlineItem | None:
        return self._start_bookmark

    def set_end_bookmark(self, bookmark: PDOutlineItem | None) -> None:
        self._end_bookmark = bookmark

    def get_end_bookmark(self) -> PDOutlineItem | None:
        return self._end_bookmark

    def get_current_page_no(self) -> int:
        """Return the 1-based index of the page currently being
        processed by ``process_page`` (or ``0`` outside a walk).

        Mirrors upstream's protected ``getCurrentPageNo`` accessor —
        exposed publicly here because Python lacks Java's package /
        protected distinction and subclasses outside the package would
        otherwise have no way to consult it.
        """
        return self._current_page_no

    def get_output(self) -> object | None:
        """Return the active output writer, or ``None`` when no walk is
        in progress / when extraction is being driven through
        ``get_text`` (which collects into an in-memory list rather than
        a stream).

        Mirrors upstream's protected ``getOutput`` accessor — exposed
        publicly here since Python has no package-private visibility.
        Subclasses overriding write hooks may consult this when a caller
        drives extraction via ``write_text(doc, writer)``.
        """
        return self._output

    def get_characters_by_article(self) -> list[list[TextPosition]]:
        """Return the per-article list of :class:`TextPosition` objects
        for the page most recently walked. The outer list groups by
        article (one entry per ``/Beads`` chain in upstream PDFBox); the
        inner lists hold the glyph-positions in extraction order.

        Mirrors upstream's protected ``getCharactersByArticle``
        accessor. Lite mode emits a single article per page so the
        outer list is length 1 after every successful ``process_page``.
        Returns an empty list when called outside a walk.
        """
        return self._characters_by_article

    def set_list_item_patterns(
        self, patterns: list[re.Pattern[str]] | None
    ) -> None:
        """Override the list-item regex patterns used by
        ``match_pattern``. Pass ``None`` to revert to the defaults
        derived from :attr:`LIST_ITEM_EXPRESSIONS` on the next call to
        ``get_list_item_patterns``.

        Mirrors upstream's protected ``setListItemPatterns`` — exposed
        publicly here since Python lacks Java's protected visibility.
        """
        self._list_of_patterns = patterns

    def get_list_item_patterns(self) -> list[re.Pattern[str]]:
        """Return the list of compiled regex patterns matching common
        list-item starts (``"1."``, ``"[2]"``, ``"A)"``, ``"iv."`` ...).

        Lazily compiles :attr:`LIST_ITEM_EXPRESSIONS` on first access if
        no caller-supplied list has been installed via
        :meth:`set_list_item_patterns`. Mirrors upstream's protected
        ``getListItemPatterns`` accessor.
        """
        if self._list_of_patterns is None:
            self._list_of_patterns = [
                re.compile(expr) for expr in self.LIST_ITEM_EXPRESSIONS
            ]
        return self._list_of_patterns

    @staticmethod
    def match_pattern(
        string: str, patterns: list[re.Pattern[str]]
    ) -> re.Pattern[str] | None:
        """Return the first pattern in ``patterns`` whose
        :py:meth:`~re.Pattern.fullmatch` matches ``string``, or
        ``None`` when none match.

        Mirrors upstream's protected static ``matchPattern`` helper.
        Upstream's ``Matcher.matches()`` is anchored at both ends, so we
        use ``fullmatch`` (not ``search`` / ``match``) for parity.
        """
        for pattern in patterns:
            if pattern.fullmatch(string) is not None:
                return pattern
        return None

    # ---------- public API ----------

    def get_text(self, document: PDDocument) -> str:
        """Walk pages from ``start_page`` (1-based, inclusive) through
        ``min(end_page, page_count)`` and return the concatenated
        extracted text. Each page is wrapped in
        ``page_start`` / ``page_end``; the whole page body is also
        wrapped in ``article_start`` / ``article_end`` (lite stripper
        treats the page as a single article).

        When ``start_bookmark`` / ``end_bookmark`` are set, the
        resolved bookmark page numbers further clamp the range — see
        ``_resolve_bookmark_page``. This mirrors upstream's
        ``setStartBookmark`` / ``setEndBookmark`` behaviour.
        """
        pages = list(document.get_pages())
        total = len(pages)
        first = max(1, self._start_page)
        last = min(self._end_page, total)
        # Mirror upstream's ``resetEngine`` — clear the per-walk
        # ``charactersByArticle`` accumulator so a fresh walk doesn't
        # leak state from the previous one (subclasses introspecting via
        # ``get_characters_by_article`` rely on this).
        self._characters_by_article = []
        # Bookmark clamping. Upstream takes the bookmark range as
        # authoritative when set, but only narrows (never widens) the
        # explicit page range.
        if self._start_bookmark is not None:
            bm_first = self._resolve_bookmark_page(self._start_bookmark, document)
            if bm_first is not None:
                first = max(first, bm_first)
        if self._end_bookmark is not None:
            bm_last = self._resolve_bookmark_page(self._end_bookmark, document)
            if bm_last is not None:
                last = min(last, bm_last)
        if first > last:
            return ""
        chunks: list[str] = []

        def _sink(piece: str) -> None:
            chunks.append(piece)

        # Mirror upstream's ``startDocument`` / ``endDocument`` hooks —
        # invoked once per ``get_text`` walk around the page loop. The
        # base implementations are no-ops; subclasses override.
        self.start_document(document)
        try:
            for one_based in range(first, last + 1):
                page = pages[one_based - 1]
                self._current_page_no = one_based
                self.start_page(page)
                self.write_page_start(_sink)
                if self._article_start:
                    self.write_article_start(_sink)
                chunks.append(self.process_page(page))
                if self._article_end:
                    self.write_article_end(_sink)
                self.write_page_end(_sink)
                self.end_page(page)
        finally:
            self.end_document(document)
            self._current_page_no = 0
        return "".join(chunks)

    def write_text(self, document: PDDocument, output: _TextWriter) -> None:
        """Write extracted text to ``output``.

        Mirrors upstream ``PDFTextStripper.writeText(PDDocument, Writer)``:
        the supplied writer is exposed through :meth:`get_output` while
        document/page/string hooks run, and is cleared when the walk
        completes or raises.
        """
        previous_output = self._output
        self._output = output
        try:
            output.write(self.get_text(document))
        finally:
            self._output = previous_output

    @staticmethod
    def _resolve_bookmark_page(
        bookmark: PDOutlineItem, document: PDDocument
    ) -> int | None:
        """Return the 1-based page number that ``bookmark`` resolves to
        within ``document``, or ``None`` when the destination can't be
        resolved within the lite outline surface (named-destination
        resolution is deferred — see ``PDOutlineItem.find_destination_page``).
        """
        target = bookmark.find_destination_page(document)
        if target is None:
            return None
        for idx, page in enumerate(document.get_pages(), start=1):
            if page.get_cos_object() is target:
                return idx
        return None

    def process_page(self, page: PDPage) -> str:
        """Extract text from a single page. Subclasses may override to
        plug in custom layout logic without re-implementing the parser
        loop. Mirrors upstream's ``PDFTextStripper.processPage`` hook.
        """
        body = page.get_contents()
        if not body:
            return ""
        # Bind the page so ``Tf`` handlers can reach ``/Resources`` for
        # ``/ToUnicode`` and typed-font lookup, and clear the per-page
        # caches.
        self._active_page = page
        self._cmap_cache = {}
        self._font_cache = {}
        self._active_cmap = None
        self._active_font = None
        self._active_avg_advance = None
        try:
            positions = self._extract_positions(body)
            # Stash the per-article TextPositions so subclasses /
            # ``get_characters_by_article`` can introspect the same
            # data the formatter consumed. Lite mode treats the whole
            # page body as a single article (PDFTextStripper-compatible
            # behaviour when ``setShouldSeparateByBeads(false)`` or no
            # beads are present).
            self._characters_by_article = [list(positions)]
            return self._format_positions(positions)
        finally:
            self._active_page = None
            self._active_cmap = None
            self._active_font = None
            self._active_avg_advance = None

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
            state.tm_a = 1.0
            state.tm_b = 0.0
            state.tm_c = 0.0
            state.tm_d = 1.0
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
                    # Resolve and cache the /ToUnicode CMap (if any) so
                    # Tj/TJ/'/" emitters can decode glyph codes; also
                    # resolve the typed PDFont so the /Differences-based
                    # glyph→unicode fallback and the font-width-based
                    # word-gap heuristic both have something to consult.
                    self._active_cmap = self._get_cmap_for_font(state.font_name)
                    self._active_font = self._get_font_for(state.font_name)
                if isinstance(size, COSNumber):
                    state.font_size = size.float_value()
                # Recompute the per-glyph advance whenever the font OR
                # the size changes (Tf carries both — even Tf with the
                # same name re-anchors the size).
                self._active_avg_advance = self._compute_avg_advance(
                    self._active_font, state.font_size
                )
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
            # the supplied 3x3 affine. We track translation (e, f) for
            # the position cursor and the scale/shear components
            # (a, b, c, d) so emitted runs can report their text-matrix
            # rotation (used by ``FilteredTextStripper`` /
            # ``AngleCollector`` for ``-rotationMagic``).
            values = _six_numbers(operands)
            if values is not None:
                a, b, c, d, e, f = values
                state.tm_a = a
                state.tm_b = b
                state.tm_c = c
                state.tm_d = d
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
        text = self._decode_show_text(s.get_bytes())
        if not text:
            return
        font = self._active_font
        resolved_font_name = font.get_name() if font is not None else None
        per_char = self._active_avg_advance
        if per_char is None:
            per_char = state.font_size * 0.5
        width_of_space = self._compute_width_of_space(
            font, state.font_size, fallback=per_char
        )
        if self._ignore_content_stream_space_glyphs:
            self._emit_ignoring_space_glyphs(
                text,
                state,
                positions,
                font,
                resolved_font_name,
                per_char,
                width_of_space,
            )
            return

        run_width = len(text) * per_char
        positions.append(
            TextPosition(
                text=text,
                x=state.text_x,
                y=state.text_y,
                font_size=state.font_size,
                font_name=state.font_name,
                font=font,
                resolved_font_name=resolved_font_name,
                width=run_width,
                width_of_space=width_of_space,
                char_spacing=state.char_spacing,
                word_spacing=state.word_spacing,
                text_matrix=[
                    state.tm_a,
                    state.tm_b,
                    state.tm_c,
                    state.tm_d,
                    state.text_x,
                    state.text_y,
                ],
            )
        )
        # Advance the text origin by an approximation of the run width.
        # If the active font has a ``/Widths`` array, we use its average
        # glyph advance (already scaled to user-space units in
        # ``_compute_avg_advance``); otherwise fall back to the legacy
        # 0.5-em-per-char monospace estimate so unknown fonts still
        # produce monotonic advances for the word-gap heuristic.
        state.text_x += run_width

    def _emit_ignoring_space_glyphs(
        self,
        text: str,
        state: _TextState,
        positions: list[TextPosition],
        font: PDFont | None,
        resolved_font_name: str | None,
        per_char: float,
        width_of_space: float,
    ) -> None:
        """Emit non-space chunks while preserving the original text advance."""
        cursor_x = state.text_x
        chunk_start_x = cursor_x
        chunk: list[str] = []

        def flush_chunk() -> None:
            nonlocal chunk_start_x
            if not chunk:
                return
            chunk_text = "".join(chunk)
            positions.append(
                TextPosition(
                    text=chunk_text,
                    x=chunk_start_x,
                    y=state.text_y,
                    font_size=state.font_size,
                    font_name=state.font_name,
                    font=font,
                    resolved_font_name=resolved_font_name,
                    width=len(chunk_text) * per_char,
                    width_of_space=width_of_space,
                    char_spacing=state.char_spacing,
                    word_spacing=state.word_spacing,
                    text_matrix=[
                        state.tm_a,
                        state.tm_b,
                        state.tm_c,
                        state.tm_d,
                        chunk_start_x,
                        state.text_y,
                    ],
                )
            )
            chunk.clear()
            chunk_start_x = cursor_x

        for char in text:
            if char == " ":
                flush_chunk()
            else:
                if not chunk:
                    chunk_start_x = cursor_x
                chunk.append(char)
            cursor_x += per_char
        flush_chunk()
        state.text_x = cursor_x

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

    # ---------- /ToUnicode CMap helpers ----------

    def _get_cmap_for_font(self, font_resource_name: str | None) -> CMap | None:
        """Resolve and cache the parsed ``/ToUnicode`` CMap for the
        font registered as ``font_resource_name`` in the active page's
        ``/Resources/Font`` subdictionary.

        Returns ``None`` (and caches the negative result) when:
          - no page is active, or
          - the resources don't list this font, or
          - the font dict has no ``/ToUnicode`` entry, or
          - ``/ToUnicode`` isn't a stream.

        ``Encoding`` / ``Differences`` based glyph→unicode resolution for
        fonts without ``/ToUnicode`` is handled by the typed-font decode
        path after this lookup returns ``None``.
        """
        if font_resource_name is None or self._active_page is None:
            return None
        cached = self._cmap_cache.get(font_resource_name)
        if font_resource_name in self._cmap_cache:
            return cached
        cmap: CMap | None = None
        try:
            resources = self._active_page.get_resources()
            font_entry = resources.get_font(COSName.get_pdf_name(font_resource_name))
            if font_entry is not None:
                font_dict = (
                    font_entry
                    if isinstance(font_entry, COSDictionary)
                    else font_entry.get_cos_object()
                )
                to_unicode = font_dict.get_dictionary_object("ToUnicode")
                if isinstance(to_unicode, COSStream):
                    with to_unicode.create_input_stream() as src:
                        cmap = CMapParser().parse(src.read())
        except Exception:  # noqa: BLE001 — defensive: malformed CMap → no decode
            cmap = None
        self._cmap_cache[font_resource_name] = cmap
        return cmap

    def _decode_show_text(self, text_bytes: bytes) -> str:
        """Decode a show-text byte string to a Python ``str``.

        Resolution order matches upstream's text-extraction pipeline:

        1. ``/ToUnicode`` CMap when present (most authoritative — present
           on all modern simple fonts and required for composite fonts).
        2. Typed ``PDSimpleFont.decode`` when the font is wired through
           the resources — this covers the ``/Encoding`` + ``/Differences``
           case where the font dictates a per-byte glyph name and the
           Adobe Glyph List supplies the Unicode value.
        3. ``COSString.get_string`` Latin-1 / PDFDocEncoding fallback for
           fonts with neither a ``/ToUnicode`` CMap nor a typed wrapper
           the resource lookup could resolve.
        """
        if self._active_cmap is not None:
            return self._decode_text_via_cmap(text_bytes, self._active_cmap)
        font = self._active_font
        if font is not None:
            # Local import to avoid pulling pdmodel.font into the text
            # module's import graph at top level (circular: pdmodel.font
            # imports COSStream which imports the filter module which
            # imports …).
            from pypdfbox.pdmodel.font import PDSimpleFont  # noqa: PLC0415

            if isinstance(font, PDSimpleFont):
                try:
                    return font.decode(text_bytes)
                except Exception:  # noqa: BLE001 — defensive
                    pass
        # Fallback: construct a transient COSString purely for its
        # PDFDocEncoding-aware decode logic. We can't reuse ``s`` here
        # because callers pass raw bytes via ``s.get_bytes()`` already.
        return text_bytes.decode("latin-1", errors="replace")

    def _get_font_for(self, font_resource_name: str | None) -> PDFont | None:
        """Resolve and cache the typed ``PDFont`` for the resource name
        last set by ``Tf``. Returns ``None`` when the page has no
        matching ``/Font`` entry, when the entry isn't a dictionary, or
        when ``PDFontFactory`` declines to wrap it (e.g. unsupported
        ``/Subtype``)."""
        if font_resource_name is None or self._active_page is None:
            return None
        if font_resource_name in self._font_cache:
            return self._font_cache[font_resource_name]
        font: PDFont | None = None
        try:
            # Local import to break the pdmodel.font ↔ text cycle.
            from pypdfbox.pdmodel.font import PDFontFactory  # noqa: PLC0415

            resources = self._active_page.get_resources()
            font_entry = resources.get_font(COSName.get_pdf_name(font_resource_name))
            if font_entry is not None:
                if isinstance(font_entry, COSDictionary):
                    font = PDFontFactory.create_font(font_entry)
                else:
                    font = font_entry
        except Exception:  # noqa: BLE001 — defensive: malformed font → no decode
            font = None
        self._font_cache[font_resource_name] = font
        return font

    @staticmethod
    def _compute_avg_advance(font: PDFont | None, font_size: float) -> float | None:
        """Convert a font's average glyph width (thousandths of an em) to
        a user-space per-character advance at the given ``font_size``.
        Returns ``None`` when the font has no usable ``/Widths`` array
        — callers fall back to the legacy 0.5-em-per-char estimate."""
        if font is None or font_size <= 0:
            return None
        # Local import to avoid pulling pdmodel.font into module-load
        # time (cycle).
        from pypdfbox.pdmodel.font import PDSimpleFont  # noqa: PLC0415

        if not isinstance(font, PDSimpleFont):
            return None
        avg_thousandths = font.get_average_font_width()
        if avg_thousandths <= 0:
            return None
        return avg_thousandths / 1000.0 * font_size

    @staticmethod
    def _compute_width_of_space(
        font: PDFont | None,
        font_size: float,
        *,
        fallback: float,
    ) -> float:
        """Return a user-space space width for the active font.

        Current font wrappers only expose per-code widths on some
        subclasses, so this is intentionally conservative: use
        ``get_glyph_width(32)`` when present and positive, otherwise
        reuse the per-character fallback already driving run advances.
        """
        if font is not None and font_size > 0:
            get_glyph_width = getattr(font, "get_glyph_width", None)
            if callable(get_glyph_width):
                try:
                    width = float(get_glyph_width(32))
                except Exception:  # noqa: BLE001 — defensive: malformed font metrics
                    width = 0.0
                if width > 0.0:
                    return width / 1000.0 * font_size
        return fallback

    @staticmethod
    def _decode_text_via_cmap(text_bytes: bytes, cmap: CMap) -> str:
        """Walk ``text_bytes`` consuming codes whose width is governed by
        the CMap's codespace ranges, look each up via ``cmap.to_unicode``,
        and concatenate. Codes with no Unicode mapping are skipped.

        Mirrors PDFBox's ``PDFont.encode``/``readCode`` loop, simplified
        for the lite stripper: we drive ``CMap.read_code`` directly off a
        ``BytesIO`` rather than threading the parser through a glyph
        positioning pass.
        """
        import io as _io  # noqa: PLC0415 — local: only used here

        stream = _io.BytesIO(text_bytes)
        out: list[str] = []
        while True:
            pos_before = stream.tell()
            if pos_before >= len(text_bytes):
                break
            code = cmap.read_code(stream)
            # Guard against zero-length reads (defensive — read_code
            # always advances at least one byte for non-empty input).
            if stream.tell() == pos_before:
                break
            piece = cmap.to_unicode(code)
            if piece is not None:
                out.append(piece)
        return "".join(out)

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

        When ``sort_by_position`` is enabled the positions are first
        re-ordered top-to-bottom, left-to-right (descending ``y`` since
        PDF user space puts the origin at the lower-left) so emission
        respects geometric reading order rather than content-stream
        order. This mirrors upstream's ``setSortByPosition(true)``.

        When ``suppress_duplicate_overlapping_text`` is enabled (the
        upstream default), two positions that share the same text and
        whose origins differ by less than a quarter of the font size
        are considered the same glyph painted twice (a common trick
        for fake bold) and the duplicate is dropped before formatting.

        When ``should_separate_by_beads`` is enabled and the active page
        carries thread beads, positions are bucketed into the bead whose
        rectangle contains the run's origin (with a residual bucket for
        runs outside any bead). Buckets are emitted in bead-chain order,
        matching upstream's ``setShouldSeparateByBeads(true)`` semantics.
        """
        if not positions:
            return ""
        # Drop glyphs the subclass declines via ``should_skip_glyph``
        # before any sorting/grouping — keeps the position lists handed
        # to ``write_string`` in sync with what subclasses would have
        # seen via ``processTextPosition`` upstream.
        positions = [p for p in positions if not self.should_skip_glyph(p)]
        if not positions:
            return ""
        if self._suppress_duplicate_overlapping_text:
            positions = self._drop_overlapping_duplicates(positions)
        # Upstream applies the comparator only when ``sortByPosition`` is
        # set — even when bead-separation is on, the in-bead ordering
        # follows content-stream order unless explicit sort is requested.
        # Lite mode follows the same gating.
        if self._sort_by_position:
            if self._flip_axes:
                # Rotated frame: sort by ascending x (top-to-bottom in
                # the rotated reading order) then ascending y (left-to-
                # right within a column). Mirrors upstream's flipped
                # comparator.
                positions = sorted(positions, key=lambda p: (p.x, p.y))
            else:
                positions = sorted(positions, key=lambda p: (-p.y, p.x))

        # Bead-separation: bucket positions by the bead whose rectangle
        # contains their origin, then emit one bucket at a time. Lite
        # mode preserves the upstream invariant that text outside any
        # bead falls into a residual bucket emitted last.
        groups: list[list[TextPosition]] = []
        if self._should_separate_by_beads and self._active_page is not None:
            groups = self._partition_by_beads(positions)
        if not groups:
            groups = [positions]

        chunks: list[str] = []

        def _sink(piece: str) -> None:
            chunks.append(piece)

        for gi, group in enumerate(groups):
            if gi > 0:
                # Bead boundary — upstream emits a line separator between
                # articles when sortByPosition is on so the bead change is
                # visible. Lite mode does the same unconditionally; the
                # caller can post-process the line separator if needed.
                self.write_line_separator(_sink)
            self._emit_group(group, _sink)
        return "".join(chunks)

    def _emit_group(
        self,
        positions: list[TextPosition],
        sink: Callable[[str], None],
    ) -> None:
        """Emit a single ordered list of positions. Splits out from
        ``_format_positions`` so the bead-bucket loop can reuse the same
        line/word/paragraph heuristics for each bucket independently."""
        prev: TextPosition | None = None
        for pos in positions:
            if prev is not None:
                if self._is_line_break(pos, prev):
                    if self.is_paragraph_separation(pos, prev):
                        self.write_paragraph_end(sink)
                        self.write_line_separator(sink)
                        self.write_paragraph_start(sink)
                    else:
                        self.write_line_separator(sink)
                else:
                    if self._is_word_break(pos, prev):
                        self.write_word_separator(sink)
            self.write_string_with_positions(pos.text, [pos], sink)
            prev = pos

    def _is_line_break(
        self, pos: TextPosition, prev: TextPosition
    ) -> bool:
        """True when ``pos`` belongs to a new line relative to ``prev``."""
        if self._flip_axes:
            # Rotated frame: line stepping happens along X.
            return abs(pos.x - prev.x) > max(prev.font_size, 0.1) * 0.5
        return abs(pos.y - prev.y) > max(prev.font_size, 0.1) * 0.5

    def _is_word_break(
        self, pos: TextPosition, prev: TextPosition
    ) -> bool:
        """True when ``pos`` is far enough past ``prev``'s right edge to
        warrant a word separator."""
        if prev.width > 0.0:
            prev_right = prev.x + prev.width if not self._flip_axes else prev.y + prev.width
        else:
            stretch = len(prev.text) * prev.font_size * 0.5
            prev_right = (prev.x + stretch) if not self._flip_axes else (prev.y + stretch)
        gap = (pos.x - prev_right) if not self._flip_axes else (pos.y - prev_right)
        return gap > prev.font_size * self._WORD_GAP_FACTOR

    def is_paragraph_separation(
        self, pos: TextPosition, prev: TextPosition
    ) -> bool:
        """Heuristic: ``pos`` starts a new paragraph relative to ``prev``.

        Upstream PDFBox's ``isParagraphSeparation`` fires on either:
          - a vertical drop larger than ``drop_threshold`` × line height
            (a blank line — a "paragraph drop"), or
          - a noticeable indent — ``pos.x`` jumps right by more than
            ``indent_threshold`` × space width vs the previous line's
            start (an "indented first line").

        Lite mode applies the same two-prong test. ``drop_threshold`` and
        ``indent_threshold`` honour the configured values.
        """
        # Drop test (vertical gap exceeds drop_threshold × line height).
        line_height = max(prev.font_size, 0.1)
        drop = abs(pos.x - prev.x) if self._flip_axes else abs(pos.y - prev.y)
        if drop > line_height * self._drop_threshold:
            return True
        # Indent test — only meaningful when a line-break has been
        # detected; callers gate on ``_is_line_break`` first.
        space_width = prev.width_of_space if prev.width_of_space > 0 else (
            prev.font_size * 0.25
        )
        indent = pos.y - prev.y if self._flip_axes else pos.x - prev.x
        return indent > space_width * self._indent_threshold

    def is_para_break_indented(self, pos: TextPosition, prev: TextPosition) -> bool:
        """Convenience predicate: only the indent prong of
        :meth:`is_paragraph_separation`. Mirrors upstream's helper used
        by callers that want to detect indented-first-line paragraphs
        without conflating them with blank-line paragraph drops."""
        space_width = prev.width_of_space if prev.width_of_space > 0 else (
            prev.font_size * 0.25
        )
        indent = pos.y - prev.y if self._flip_axes else pos.x - prev.x
        return indent > space_width * self._indent_threshold

    def start_of_paragraph(
        self, pos: TextPosition, prev: TextPosition
    ) -> bool:
        """Alias for :meth:`is_paragraph_separation` matching upstream's
        ``isParagraphStart`` accessor name spelling. Both names are
        present on the 3.x surface; we honour both for porting parity."""
        return self.is_paragraph_separation(pos, prev)

    def _partition_by_beads(
        self, positions: list[TextPosition]
    ) -> list[list[TextPosition]]:
        """Bucket ``positions`` by the bead whose rectangle covers each
        run's origin. Returns a list of buckets in bead-chain order; the
        last bucket holds positions that fell outside every bead.

        Returns an empty list when the active page has no thread beads
        (callers fall back to a single all-positions group)."""
        page = self._active_page
        if page is None:
            return []
        try:
            beads = page.get_thread_beads()
        except Exception:  # noqa: BLE001 — defensive: malformed /B
            return []
        if not beads:
            return []
        rects: list[tuple[float, float, float, float] | None] = []
        for bead in beads:
            if bead is None:
                rects.append(None)
                continue
            try:
                r = bead.get_rectangle()
            except Exception:  # noqa: BLE001
                rects.append(None)
                continue
            if r is None:
                rects.append(None)
                continue
            # PDRectangle stores (lower_left_x, lower_left_y, upper_right_x,
            # upper_right_y) — keep that form for membership tests.
            rects.append(
                (
                    float(r.get_lower_left_x()),
                    float(r.get_lower_left_y()),
                    float(r.get_upper_right_x()),
                    float(r.get_upper_right_y()),
                )
            )
        if not any(r is not None for r in rects):
            return []
        buckets: list[list[TextPosition]] = [[] for _ in rects]
        residual: list[TextPosition] = []
        for pos in positions:
            placed = False
            for idx, rect in enumerate(rects):
                if rect is None:
                    continue
                llx, lly, urx, ury = rect
                if llx <= pos.x <= urx and lly <= pos.y <= ury:
                    buckets[idx].append(pos)
                    placed = True
                    break
            if not placed:
                residual.append(pos)
        result = [b for b in buckets if b]
        if residual:
            result.append(residual)
        return result

    @staticmethod
    def _drop_overlapping_duplicates(
        positions: list[TextPosition],
    ) -> list[TextPosition]:
        """Drop ``TextPosition`` entries that overlap an earlier entry
        with the same text — the duplicate-glyph fake-bold case.
        Linear scan against a small ring of recent positions; the
        threshold is a quarter of the font size in user-space units."""
        result: list[TextPosition] = []
        for pos in positions:
            duplicate = False
            tol = max(pos.font_size, 0.1) * 0.25
            # Only check the trailing window — duplicates from fake
            # bold are always emitted right after their original.
            for prior in result[-4:]:
                if (
                    prior.text == pos.text
                    and abs(prior.x - pos.x) <= tol
                    and abs(prior.y - pos.y) <= tol
                ):
                    duplicate = True
                    break
            if not duplicate:
                result.append(pos)
        return result

    # ---------- emission hooks (subclasses may override) ----------
    #
    # These mirror upstream PDFBox's ``writeString`` /
    # ``writeWordSeparator`` / ``writeLineSeparator`` /
    # ``writeParagraphStart`` / ``writeParagraphEnd`` /
    # ``writePageStart`` / ``writePageEnd`` / ``writeArticleStart`` /
    # ``writeArticleEnd`` overrides. Upstream writes to a Java
    # ``Writer``; we accept a callable sink so subclasses don't need
    # to thread a buffer through the call chain.

    def process_text_position(self, text: TextPosition) -> None:
        """Per-glyph hook invoked for every emitted ``TextPosition``.

        The base implementation is a no-op; subclasses override to
        collect or filter individual glyphs (the
        :class:`FilteredTextStripper` ``-rotationMagic`` collector is
        the canonical use case). Upstream PDFBox calls this from its
        showText path; the lite stripper invokes it once per emitted
        run from ``_format_positions`` so the hook stays observable
        without re-engineering the parser walk.
        """
        return None

    def should_skip_glyph(self, text: TextPosition) -> bool:
        """Return ``True`` to drop ``text`` from the formatted output.

        Mirrors upstream PDFBox's ``shouldSkipGlyph`` filter hook
        (added on the 3.x branch alongside ``setIgnoreContentStreamSpaceGlyphs``).
        The base implementation always returns ``False`` — every glyph
        is kept. Subclasses override to filter, e.g. by rotation,
        position, or font.
        """
        return False

    def write_string(
        self,
        text: str,
        text_positions: list[TextPosition],
        sink: Callable[[str], None],
    ) -> None:
        """Hook for emitting a decoded text run. Default writes
        ``text`` to ``sink``. Subclasses may inspect ``text_positions``
        to filter or transform the run before writing."""
        for tp in text_positions:
            self.process_text_position(tp)
        sink(text)

    def write_string_with_positions(
        self,
        text: str,
        text_positions: list[TextPosition],
        sink: Callable[[str], None],
    ) -> None:
        """Position-aware emission hook with the same signature as
        :meth:`write_string`. Mirrors upstream's
        ``writeString(String, List<TextPosition>)`` overload.

        Invariants enforced here for subclasses:

        - ``text`` is non-empty when called from the format path.
        - ``text_positions`` is non-empty and every entry's ``.text``
          contributes to ``text`` (concatenation; the lite stripper emits
          one position per run so the list is length 1).
        - Each position is dispatched through :meth:`process_text_position`
          *before* anything is written to ``sink``, so collectors can
          inspect the run's geometry before its text materialises.

        The default delegates to :meth:`write_string` (the upstream-
        compatible single-arg name); subclasses can override either.
        """
        if not text or not text_positions:
            return
        self.write_string(text, text_positions, sink)

    def write_word_separator(self, sink: Callable[[str], None]) -> None:
        sink(self._word_separator)

    def write_line_separator(self, sink: Callable[[str], None]) -> None:
        sink(self._line_separator)

    def write_paragraph_start(self, sink: Callable[[str], None]) -> None:
        sink(self._paragraph_start)

    def write_paragraph_end(self, sink: Callable[[str], None]) -> None:
        sink(self._paragraph_end)

    def write_page_start(self, sink: Callable[[str], None]) -> None:
        sink(self._page_start)

    def write_page_end(self, sink: Callable[[str], None]) -> None:
        sink(self._page_end)

    def write_article_start(self, sink: Callable[[str], None]) -> None:
        sink(self._article_start)

    def write_article_end(self, sink: Callable[[str], None]) -> None:
        sink(self._article_end)

    def write_characters(self, text: TextPosition) -> None:
        """Per-glyph character-write hook.

        Mirrors upstream PDFBox's protected ``writeCharacters(TextPosition)``
        — the lowest-level emission hook, called for the unicode payload
        of a single ``TextPosition``. The default is a no-op because the
        lite stripper composes runs at the ``write_string`` level
        (``TextPosition`` granularity, not glyph granularity); subclasses
        that want to capture or transform per-glyph output can override.
        """
        return None

    def start_document(self, document: PDDocument) -> None:
        """Hook invoked once at the start of every ``get_text`` walk.

        Mirrors upstream's protected ``startDocument(PDDocument)``. The
        base implementation is a no-op; subclasses override to install
        per-document state (e.g. a streaming writer).
        """
        return None

    def end_document(self, document: PDDocument) -> None:
        """Hook invoked once at the end of every ``get_text`` walk.

        Mirrors upstream's protected ``endDocument(PDDocument)``. The
        base implementation is a no-op; subclasses override to flush
        per-document state.
        """
        return None

    def start_page(self, page: PDPage) -> None:
        """Hook invoked at the start of every page in the walk, before
        ``process_page`` runs and before ``write_page_start`` emits the
        page-start separator.

        Mirrors upstream's protected ``startPage(PDPage)``. Distinct
        from :meth:`write_page_start`: this hook does not write to the
        sink — it lets subclasses observe the page boundary without
        committing characters.
        """
        return None

    def end_page(self, page: PDPage) -> None:
        """Hook invoked at the end of every page in the walk, after
        ``write_page_end`` has emitted the page-end separator.

        Mirrors upstream's protected ``endPage(PDPage)``.
        """
        return None

    def start_article(self, is_ltr: bool = True) -> None:
        """Hook invoked at the start of an article (bead-bounded
        column). Mirrors upstream's protected ``startArticle(boolean)``;
        ``is_ltr`` tracks whether the article's primary text direction
        is left-to-right (the default).

        The lite stripper treats the page as a single article, so this
        hook is observable but not actively dispatched by the page loop
        — callers and subclass tests can drive it directly. The base
        implementation is a no-op for parity with upstream.
        """
        return None

    def end_article(self) -> None:
        """Hook invoked at the end of an article. Mirrors upstream's
        protected ``endArticle``."""
        return None


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
        "tm_a",
        "tm_b",
        "tm_c",
        "tm_d",
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
        # Text-matrix scale/shear components — only ``Tm`` mutates these
        # (Td/TD/T*/'/" affect translation only, leaving a/b/c/d alone),
        # so tracking them here is enough to recover the run's rotation
        # at emit time. Identity by default per PDF 1.7 §9.4.1 ``BT``.
        self.tm_a: float = 1.0
        self.tm_b: float = 0.0
        self.tm_c: float = 0.0
        self.tm_d: float = 1.0


def _two_numbers(operands: list[COSBase]) -> tuple[float, float]:
    """Pull two numeric operands; default to 0.0 on malformed input."""
    if len(operands) < 2:
        return 0.0, 0.0
    a, b = operands[0], operands[1]
    if not (isinstance(a, COSNumber) and isinstance(b, COSNumber)):
        return 0.0, 0.0
    return a.float_value(), b.float_value()


def _six_numbers(operands: list[COSBase]) -> tuple[float, float, float, float, float, float] | None:
    """Pull six numeric operands; return ``None`` on malformed input."""
    if len(operands) < 6:
        return None
    a, b, c, d, e, f = operands[:6]
    if not isinstance(a, COSNumber):
        return None
    if not isinstance(b, COSNumber):
        return None
    if not isinstance(c, COSNumber):
        return None
    if not isinstance(d, COSNumber):
        return None
    if not isinstance(e, COSNumber):
        return None
    if not isinstance(f, COSNumber):
        return None
    return (
        a.float_value(),
        b.float_value(),
        c.float_value(),
        d.float_value(),
        e.float_value(),
        f.float_value(),
    )


__all__ = ["PDFTextStripper"]
