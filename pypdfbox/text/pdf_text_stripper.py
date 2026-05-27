from __future__ import annotations

import re
import sys
import unicodedata
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSNumber, COSStream, COSString
from pypdfbox.fontbox.cmap import CMap, CMapParser
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.util.matrix import Matrix

from .bidi import BidiResolver, get_paragraph_direction
from .bidi import _reorder_indices as _bidi_reorder_indices
from .position_wrapper import PositionWrapper
from .text_position import TextPosition
from .word_with_text_positions import WordWithTextPositions

# Unicode bidi-mirroring map for L4 — pairs are derived from
# ``unicodedata.mirrored`` at module load time. The PDFBox upstream
# parses ``BidiMirroring.txt`` from its bundled resources; we use the
# same data already vendored in Python's UCD via the ``mirrored``
# property. The map covers paired punctuation (`(` <-> `)`, `[` <-> `]`,
# `{` <-> `}`, the angle and corner brackets, the mathematical
# delimiters, etc.) — every codepoint whose mirrored bidi-class
# substitution is one well-defined other codepoint.
_BIDI_MIRROR_MAP: dict[str, str] = {
    "(": ")",
    ")": "(",
    "[": "]",
    "]": "[",
    "{": "}",
    "}": "{",
    "<": ">",
    ">": "<",
    "«": "»",  # « »
    "»": "«",
    "‹": "›",  # ‹ ›
    "›": "‹",
    "⌈": "⌉",  # ⌈ ⌉
    "⌉": "⌈",
    "⌊": "⌋",  # ⌊ ⌋
    "⌋": "⌊",
    "⟨": "⟩",  # ⟨ ⟩
    "⟩": "⟨",
    "⟪": "⟫",  # ⟪ ⟫
    "⟫": "⟪",
    "〈": "〉",  # 〈 〉
    "〉": "〈",
    "〈": "〉",  # 〈 〉 (CJK)
    "〉": "〈",
    "《": "》",  # 《 》
    "》": "《",
    "「": "」",  # 「 」
    "」": "「",
    "『": "』",  # 『 』
    "』": "『",
    "【": "】",  # 【 】
    "】": "【",
    "〔": "〕",  # 〔 〕
    "〕": "〔",
    "〖": "〗",  # 〖 〗
    "〗": "〖",
    "〘": "〙",  # 〘 〙
    "〙": "〘",
    "〚": "〛",  # 〚 〛
    "〛": "〚",
}

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
        # Upstream PDFBox defaults ``paragraphEnd`` to ``""`` and emits the
        # line terminator separately (``writeLineSeparator``). The lite
        # stripper previously defaulted this to ``"\n"``, which doubled the
        # newline at every detected paragraph break (``write_paragraph_end``
        # + ``write_line_separator`` both fired ``"\n"``), inserting a
        # spurious blank line that the Java oracle never emits. Match
        # upstream's empty default so a paragraph break collapses to the
        # single ``line_separator`` newline.
        self._paragraph_end: str = ""
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
        # Per-walk caches refreshed by ``process_pages`` / ``reset_engine``.
        self._bead_rectangles: list[tuple[float, float, float, float]] = []
        self._start_bookmark_page_number: int = -1
        self._end_bookmark_page_number: int = -1
        # Marked-content state. ``_marked_content_stack`` mirrors
        # upstream's ``Stack<PDMarkedContent>``; lite mode tracks just
        # the pieces it needs to surface ``/ActualText`` to subclasses.
        self._marked_content_stack: list[
            tuple[COSName | None, COSDictionary | None, str | None]
        ] = []
        self._actual_text: str | None = None
        self._first_actual_text_position: bool = False
        # Document handle for ``process_pages`` bookmark resolution.
        # Populated by ``get_text`` while a walk is in progress.
        self._active_document: PDDocument | None = None
        # Per-walk sink used by subclass hooks (``start_document`` /
        # ``end_document`` / ``start_article`` / ``end_article`` /
        # ``write_string`` overrides) that want to stream text through
        # the same gateway as the parent's page loop. Populated by
        # ``get_text`` for the duration of a walk; restored to its
        # previous value (typically ``None``) when the walk completes.
        # Mirrors upstream's per-walk ``output`` field but exposes it as
        # a callable so the lite stripper's in-memory ``chunks`` path
        # and any externally installed :class:`io.TextIO` writer share
        # the same emission point.
        self._active_sink: Callable[[str], None] | None = None

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
        self.reset_engine()
        self._active_document = document
        # Bookmark clamping. Upstream takes the bookmark range as
        # authoritative when set, but only narrows (never widens) the
        # explicit page range.
        bm_first = (
            self._resolve_bookmark_page(self._start_bookmark, document)
            if self._start_bookmark is not None
            else None
        )
        bm_last = (
            self._resolve_bookmark_page(self._end_bookmark, document)
            if self._end_bookmark is not None
            else None
        )
        # Mirror upstream PDFTextStripper.processPages: when start/end
        # bookmarks both fail to resolve (i.e. they're orphans) AND they
        # refer to the same bookmark object, clamp the range to the empty
        # one — the result is empty extracted text. Without this clamp
        # any previously-set start_page / end_page leaks through and
        # yields content the caller explicitly opted out of.
        if (
            bm_first is None
            and bm_last is None
            and self._start_bookmark is not None
            and self._end_bookmark is not None
            and self._start_bookmark.get_cos_object()
            is self._end_bookmark.get_cos_object()
        ):
            return ""
        if bm_first is not None:
            first = max(first, bm_first)
        if bm_last is not None:
            last = min(last, bm_last)
        if first > last:
            return ""
        chunks: list[str] = []
        # When ``write_text`` installed an output writer, stream each
        # page's text into it as the page is processed so subclass
        # ``end_page`` hooks can inspect the buffer (e.g. PDFHighlighter
        # reads per-page text from a StringIO output to emit <loc>
        # entries against the searched words). Without per-page streaming
        # the writer would only see the joined text after the page loop
        # exits, by which point every ``end_page`` call has already run
        # with an empty buffer.
        out = self._output

        def _sink(piece: str) -> None:
            chunks.append(piece)
            if out is not None:
                out.write(piece)

        # Expose the active sink so subclass hooks
        # (``start_document``/``end_document``/etc.) can stream text
        # through the same gateway as the parent's page loop. Upstream
        # PDFBox accomplishes the same via a per-walk ``output`` field;
        # we mirror that contract here. The slot is restored in the
        # ``finally`` block so it does not leak across overlapping
        # ``get_text`` calls.
        previous_sink = self._active_sink
        self._active_sink = _sink

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
                _sink(self.process_page(page))
                if self._article_end:
                    self.write_article_end(_sink)
                self.write_page_end(_sink)
                self.end_page(page)
        finally:
            self.end_document(document)
            self._current_page_no = 0
            self._active_document = None
            self._active_sink = previous_sink
        return "".join(chunks)

    def write_text(self, document: PDDocument, output: _TextWriter) -> None:
        """Write extracted text to ``output``.

        Mirrors upstream ``PDFTextStripper.writeText(PDDocument, Writer)``:
        the supplied writer is exposed through :meth:`get_output` while
        document/page/string hooks run, and is cleared when the walk
        completes or raises. Page text streams through ``output``
        incrementally — each page is flushed before its ``end_page``
        hook fires, matching upstream behaviour that subclasses like
        ``PDFHighlighter`` rely on.
        """
        previous_output = self._output
        self._output = output
        try:
            self.get_text(document)
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

        # Text-state machine. Tracks the text matrix plus the page CTM via
        # a graphics-state stack (``q`` / ``Q`` / ``cm``); the emitter
        # composes textMatrix × CTM to recover device-space glyph origins
        # and the effective font size, so producers that position lines
        # with a per-line ``cm`` and fold the point size into ``Tm`` lay
        # out correctly. See CHANGES.md.
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
            # matrix to the new line origin (PDF 1.7 §9.4.2). ``(tx, ty)``
            # is a text-space delta, so it is carried through the
            # text-matrix scale/shear before moving the translation-space
            # line origin (otherwise a ``Tm`` that folds the point size
            # into its scale would under-translate every ``Td``).
            state.line_x += tx * state.tm_a + ty * state.tm_c
            state.line_y += tx * state.tm_b + ty * state.tm_d
            state.text_x = state.line_x
            state.text_y = state.line_y
        elif op == "TD":
            tx, ty = _two_numbers(operands)
            # ``TD`` = ``-ty TL`` then ``tx ty Td``.
            state.leading = -ty
            state.line_x += tx * state.tm_a + ty * state.tm_c
            state.line_y += tx * state.tm_b + ty * state.tm_d
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
            # The ``(0, -leading)`` text-space delta is carried through the
            # text-matrix scale/shear before moving the line origin.
            state.line_x += -state.leading * state.tm_c
            state.line_y += -state.leading * state.tm_d
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
            state.line_x += -state.leading * state.tm_c
            state.line_y += -state.leading * state.tm_d
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
                state.line_x += -state.leading * state.tm_c
                state.line_y += -state.leading * state.tm_d
                state.text_x = state.line_x
                state.text_y = state.line_y
                self._emit(operands[2], state, positions)
        elif op == "Tc":
            if operands and isinstance(operands[0], COSNumber):
                state.char_spacing = operands[0].float_value()
        elif op == "Tw":
            if operands and isinstance(operands[0], COSNumber):
                state.word_spacing = operands[0].float_value()
        elif op == "q":
            # Save graphics state — push a copy of the current CTM so a
            # later ``Q`` restores it (PDF 1.7 §8.4.2). Text state itself
            # is not part of the graphics-state stack, so only the CTM is
            # tracked here.
            state.gs_stack.append(state.ctm.clone())
        elif op == "Q":
            # Restore graphics state — pop the saved CTM. Defensive: a
            # malformed stream with an unbalanced ``Q`` leaves the CTM
            # unchanged rather than raising.
            if state.gs_stack:
                state.ctm = state.gs_stack.pop()
        elif op == "cm":
            # Concatenate the operand matrix onto the CTM (PDF 1.7 §8.3.4).
            # Upstream applies ``newCTM = operandMatrix × CTM``; with the
            # row-vector convention used by :class:`Matrix` this is
            # ``operandMatrix.multiply(ctm)``.
            values = _six_numbers(operands)
            if values is not None:
                a, b, c, d, e, f = values
                state.ctm = Matrix(a, b, c, d, e, f).multiply(state.ctm)
        # Other operators (paths, colour, marked content, etc.) are
        # intentionally ignored — they have no effect on the lite text
        # stream.

    # ---------- emission ----------

    @staticmethod
    def _text_rendering_matrix(state: _TextState) -> Matrix:
        """Compose the run's text matrix with the CTM.

        Mirrors upstream ``PDFStreamEngine.showText``'s
        ``textMatrix.multiply(ctm)`` (the font-size parameter matrix is
        applied separately to ``font_size`` rather than folded in here).
        The result's translation is the glyph origin in device space and
        its scaling factors give the effective glyph size — so producers
        that fold the point size into ``Tm`` (``14 0 0 14 … Tm`` with a
        ``1 Tf``) and position each line via a per-line ``cm`` are placed
        and scaled correctly instead of collapsing onto one baseline.
        """
        text_matrix = Matrix(
            state.tm_a, state.tm_b, state.tm_c, state.tm_d, state.text_x, state.text_y
        )
        return text_matrix.multiply(state.ctm)

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
        # Resolve the device-space origin and effective glyph size from
        # the full text-rendering matrix. ``font_size`` (the ``Tf``
        # operand) is scaled by the matrix's Y scaling so the line-break
        # and word-gap heuristics operate on the rendered glyph size, and
        # the run width (computed in text space) is scaled by the X
        # scaling so it lands in the same device-space units as the
        # origin.
        trm = self._text_rendering_matrix(state)
        device_x = trm.get_translate_x()
        device_y = trm.get_translate_y()
        y_scale = trm.get_scaling_factor_y()
        x_scale = trm.get_scaling_factor_x()
        effective_font_size = state.font_size * y_scale
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
                x=device_x,
                y=device_y,
                font_size=effective_font_size,
                font_name=state.font_name,
                font=font,
                resolved_font_name=resolved_font_name,
                width=run_width * x_scale,
                width_of_space=width_of_space * x_scale,
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
        #
        # ``run_width`` is the advance in *text space* (em-units × the
        # ``Tf`` operand). The text cursor (``text_x`` / ``text_y``) lives
        # in the text matrix's translation slots, so the advance must be
        # carried through the text-matrix scale/shear — i.e.
        # ``translate(run_width, 0) × Tm`` — which moves the cursor by
        # ``(run_width·a, run_width·b)``. Without this, producers that
        # fold the point size into ``Tm`` (``14 0 0 14 … Tm`` with a
        # ``1 Tf``) would advance 14× too slowly and every glyph would
        # collapse onto its neighbour.
        state.text_x += run_width * state.tm_a
        state.text_y += run_width * state.tm_b

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
        """Emit non-space chunks while preserving the original text advance.

        Each chunk's text-space origin is run through the text-rendering
        matrix (textMatrix × CTM) so device-space positions and the
        effective glyph size match the main :meth:`_emit` path.
        """
        ctm = state.ctm
        tm_scale = Matrix(state.tm_a, state.tm_b, state.tm_c, state.tm_d, 0.0, 0.0)
        trm_scale = tm_scale.multiply(ctm)
        y_scale = trm_scale.get_scaling_factor_y()
        x_scale = trm_scale.get_scaling_factor_x()
        effective_font_size = state.font_size * y_scale
        # ``cursor_x`` tracks the text matrix's translation slot (slot e),
        # so the per-character text-space advance is carried through the
        # horizontal text-matrix scale (``tm_a``) — matching the main
        # show-text path.
        advance = per_char * state.tm_a
        cursor_x = state.text_x
        chunk_start_x = cursor_x
        chunk: list[str] = []

        def _device_origin(text_x: float) -> tuple[float, float]:
            tm = Matrix(
                state.tm_a, state.tm_b, state.tm_c, state.tm_d, text_x, state.text_y
            )
            trm = tm.multiply(ctm)
            return trm.get_translate_x(), trm.get_translate_y()

        def flush_chunk() -> None:
            nonlocal chunk_start_x
            if not chunk:
                return
            chunk_text = "".join(chunk)
            device_x, device_y = _device_origin(chunk_start_x)
            positions.append(
                TextPosition(
                    text=chunk_text,
                    x=device_x,
                    y=device_y,
                    font_size=effective_font_size,
                    font_name=state.font_name,
                    font=font,
                    resolved_font_name=resolved_font_name,
                    width=len(chunk_text) * per_char * x_scale,
                    width_of_space=width_of_space * x_scale,
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
            cursor_x += advance
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
                # subtracted (negative = move forward). The adjustment is
                # in text space, so (like the show-text advance) it must
                # be carried through the text-matrix scale/shear before it
                # moves the translation-space cursor.
                adj = entry.float_value() * state.font_size / 1000.0
                state.text_x -= adj * state.tm_a
                state.text_y -= adj * state.tm_b

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
        line/word/paragraph heuristics for each bucket independently.

        Wave 1387 buffers each adjacent run of TextPositions (those
        not separated by a line break or word break) into a
        ``word_buffer`` and runs :meth:`handle_direction` (UAX #9 BiDi)
        once per word — matching upstream Apache PDFBox's per-word
        ``handleDirection`` contract in ``LegacyPDFStreamEngine.normalize``.
        The buffer is flushed on every word separator, line separator,
        and paragraph break.
        """
        # Per-word bidi buffer — concatenate adjacent TextPosition
        # fragments belonging to the same word, then run them through
        # handle_direction at the next break (word / line / paragraph).
        word_buffer: list[str] = []

        def _buffered_sink(piece: str) -> None:
            word_buffer.append(piece)

        def _flush_word() -> None:
            if not word_buffer:
                return
            text = "".join(word_buffer)
            word_buffer.clear()
            # ``normalize_word`` decomposes Unicode presentation forms
            # (Alphabetic Presentation Forms FB00–FDFF, e.g. the ``ﬁ``/``ﬂ``
            # ligatures → ``fi``/``fl``, and Arabic Presentation Forms-B)
            # via NFKC and then applies the per-word ``handle_direction``
            # bidi reorder — mirroring upstream's ``normalizeWord`` →
            # ``handleDirection`` chain in ``LegacyPDFStreamEngine.normalize``.
            # It already wraps ``handle_direction`` in both branches, so
            # this also covers the pure-LTR bidi fast path.
            sink(self.normalize_word(text))

        prev: TextPosition | None = None
        for pos in positions:
            if prev is not None:
                if self._is_line_break(pos, prev):
                    _flush_word()
                    if self.is_paragraph_separation(pos, prev):
                        self.write_paragraph_end(sink)
                        self.write_line_separator(sink)
                        self.write_paragraph_start(sink)
                    else:
                        self.write_line_separator(sink)
                else:
                    if self._is_word_break(pos, prev):
                        _flush_word()
                        self.write_word_separator(sink)
            self.write_string_with_positions(pos.text, [pos], _buffered_sink)
            prev = pos
        _flush_word()

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
        # When an explicit space glyph already borders the boundary
        # (the previous run ends in whitespace, or this run begins with
        # whitespace), a producer has already encoded the word break in
        # the content stream. Emitting a gap-based separator on top of it
        # would double the space — Java's stripper collapses to a single
        # separator here.
        if prev.text and prev.text[-1].isspace():
            return False
        if pos.text and pos.text[0].isspace():
            return False
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

        A fake-bold duplicate is the *same* glyph painted a second time at
        (essentially) the *same* origin — the stroke offset is a tiny
        fraction of a point. A genuine adjacent glyph, by contrast,
        advances by roughly its own width. The tolerance is therefore a
        small fraction of the run's own width (with a tiny absolute floor
        so the exact-overlap fake-bold case at width 0 still matches),
        not a quarter of the font size: at proportional sizes a flat
        ``0.25 × font_size`` window is wider than a narrow glyph's advance
        and would drop legitimate consecutive characters once positions
        are packed in true device space (CTM-aware emission)."""
        result: list[TextPosition] = []
        for pos in positions:
            duplicate = False
            # x tolerance: a fake-bold offset is a small fraction of the
            # glyph width, so cap well below a full glyph advance. When
            # the run carries no width metric (synthetic positions / fonts
            # without ``/Widths``) fall back to a font-size fraction so
            # near-coincident same-text runs are still recognised.
            if pos.width > 0.0:
                x_tol = max(pos.width * 0.3, 0.05)
                y_tol = max(pos.font_size, 0.1) * 0.05
            else:
                x_tol = max(pos.font_size, 0.1) * 0.25
                y_tol = max(pos.font_size, 0.1) * 0.25
            # Only check the trailing window — duplicates from fake
            # bold are always emitted right after their original.
            for prior in result[-4:]:
                if (
                    prior.text == pos.text
                    and abs(prior.x - pos.x) <= x_tol
                    and abs(prior.y - pos.y) <= y_tol
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

    # ---------- additional upstream helpers (1:1 parity) ----------

    @staticmethod
    def within(first: float, second: float, variance: float) -> bool:
        """Return ``True`` when ``second`` lies within ``variance`` of
        ``first`` (i.e. ``|second - first| < variance``).

        Mirrors upstream's private ``within(float, float, float)`` helper
        (PDFTextStripper.java:857). Note: upstream is strict ``<`` not
        ``<=`` — preserve that.
        """
        return first - variance < second < first + variance

    @staticmethod
    def overlap(y1: float, height1: float, y2: float, height2: float) -> bool:
        """Return ``True`` when two vertical glyph spans overlap.

        Mirrors upstream's private ``overlap`` helper
        (PDFTextStripper.java:762):
            within(y1, y2, .1f)
            || y2 <= y1 && y2 >= y1 - height1
            || y1 <= y2 && y1 >= y2 - height2
        """
        if PDFTextStripper.within(y1, y2, 0.1):
            return True
        if y2 <= y1 and y2 >= y1 - height1:
            return True
        return y1 <= y2 and y1 >= y2 - height2

    @staticmethod
    def multiply_float(value1: float, value2: float) -> float:
        """Multiply two floats and truncate the result to 3 decimal
        places (in thousandths) to avoid float-comparison drift.

        Mirrors upstream's ``multiplyFloat`` (PDFTextStripper.java:1685):
        ``Math.round(value1 * value2 * 1000) / 1000f``.
        """
        return round(value1 * value2 * 1000) / 1000.0

    @staticmethod
    def has_font_or_size_changed(
        current: TextPosition, last: TextPosition | None
    ) -> bool:
        """Return ``True`` when ``current`` differs from ``last`` in
        either font instance, font name, or font size.

        Mirrors upstream's private ``hasFontOrSizeChanged``
        (PDFTextStripper.java:730). The comparison falls back to font
        identity / hash when both wrappers expose no name — matching
        upstream's last-resort branch.
        """
        if last is None:
            return False
        if current.get_font_size() != last.get_font_size():
            return True
        cur_font = current.get_font()
        last_font = last.get_font()
        if cur_font is last_font:
            return False
        cur_name = cur_font.get_name() if cur_font is not None else None
        last_name = last_font.get_name() if last_font is not None else None
        if cur_name is not None:
            return cur_name != last_name
        if last_name is not None:
            return True
        # Both fonts have no name — compare identities (Python equivalent
        # of upstream's hashCode fallback).
        return id(cur_font) != id(last_font)

    @staticmethod
    def remove_contained_spaces(text_list: list[TextPosition]) -> None:
        """Remove space characters whose bounding box is fully contained
        in the previous run's bounding box (a fake-space artefact left
        over by some PDF producers — see PDFBOX-5487).

        Mirrors upstream's private ``removeContainedSpaces``
        (PDFTextStripper.java:771); mutates the supplied list in place.
        """
        if not text_list:
            return
        previous_position = text_list[0]
        idx = 1
        while idx < len(text_list):
            position = text_list[idx]
            if (
                position.get_unicode() == " "
                and previous_position.completely_contains(position)
            ):
                del text_list[idx]
                continue
            previous_position = position
            idx += 1

    def fill_bead_rectangles(self, page: PDPage) -> list[tuple[float, float, float, float]]:
        """Collect the rectangles of every thread bead on ``page``.

        Mirrors upstream's private ``fillBeadRectangles``
        (PDFTextStripper.java:386). Upstream stores the result on the
        protected ``beadRectangles`` field; the lite stripper exposes it
        via the return value (and refreshes the cached
        ``_bead_rectangles`` attribute) so subclasses can inspect the
        same shape upstream callers see.
        """
        rects: list[tuple[float, float, float, float]] = []
        try:
            beads = page.get_thread_beads()
        except Exception:  # noqa: BLE001 — defensive: malformed /B
            beads = []
        for bead in beads or []:
            if bead is None:
                continue
            try:
                r = bead.get_rectangle()
            except Exception:  # noqa: BLE001
                continue
            if r is None:
                continue
            rects.append(
                (
                    float(r.get_lower_left_x()),
                    float(r.get_lower_left_y()),
                    float(r.get_upper_right_x()),
                    float(r.get_upper_right_y()),
                )
            )
        self._bead_rectangles = rects
        return rects

    def reset_engine(self) -> None:
        """Clear per-walk state. Mirrors upstream's private
        ``resetEngine`` (PDFTextStripper.java:223): resets the
        ``charactersByArticle`` accumulator, the per-page bead rectangle
        cache, and the bookmark page resolution cache so back-to-back
        ``get_text`` walks don't leak state from each other."""
        self._characters_by_article = []
        self._bead_rectangles = []
        self._start_bookmark_page_number = -1
        self._end_bookmark_page_number = -1
        self._current_page_no = 0

    def process_pages(self, pages: list[PDPage]) -> str:
        """Walk every page in ``pages`` invoking
        :meth:`process_page` and return the concatenated text.

        Mirrors upstream's protected ``processPages(PDPageTree)``
        (PDFTextStripper.java:263). Bookmark resolution is cached on the
        instance (``_start_bookmark_page_number`` /
        ``_end_bookmark_page_number``) for the duration of the call so
        ``process_page`` can consult it without re-walking the outline
        tree per page.
        """
        chunks: list[str] = []
        # Resolve bookmarks against the page list — when neither bookmark
        # resolves but both were set and point to the same outline item,
        # upstream forces an empty range (start=0, end=0).
        start_pg = -1
        end_pg = -1
        if self._start_bookmark is not None:
            for idx, page in enumerate(pages, start=1):
                tgt = self._start_bookmark.find_destination_page(self._active_document)
                if tgt is not None and page.get_cos_object() is tgt:
                    start_pg = idx
                    break
        if self._end_bookmark is not None:
            for idx, page in enumerate(pages, start=1):
                tgt = self._end_bookmark.find_destination_page(self._active_document)
                if tgt is not None and page.get_cos_object() is tgt:
                    end_pg = idx
                    break
        if (
            start_pg == -1
            and self._start_bookmark is not None
            and end_pg == -1
            and self._end_bookmark is not None
            and self._start_bookmark.get_cos_object()
            is self._end_bookmark.get_cos_object()
        ):
            start_pg = 0
            end_pg = 0
        self._start_bookmark_page_number = start_pg
        self._end_bookmark_page_number = end_pg
        for page in pages:
            if page.get_contents():
                chunks.append(self.process_page(page))
            self._current_page_no += 1
        return "".join(chunks)

    def write_page(self) -> str:
        """Render the most recently extracted positions through the
        line/word/paragraph hooks and return the formatted text.

        Mirrors upstream's protected ``writePage`` (PDFTextStripper.java:495)
        in shape, but defers to the lite ``_format_positions`` heuristic
        rather than the wrapper-based line walker since lite mode does
        not yet maintain the full ``PositionWrapper`` chain. Subclasses
        relying on the upstream signature can override this method
        directly.
        """
        if not self._characters_by_article:
            return ""
        chunks: list[str] = []

        def sink(piece: str) -> None:
            chunks.append(piece)

        for group in self._characters_by_article:
            self._emit_group(group, sink)
        return "".join(chunks)

    def write_line(
        self,
        line: list[WordWithTextPositions],
        sink: Callable[[str], None],
    ) -> None:
        """Write a list of normalized words for a single line, inserting
        the configured word separator between them.

        Mirrors upstream's private ``writeLine`` (PDFTextStripper.java:1853);
        exposed as a public method here so lite-mode subclasses that
        compose their own line list can plug into the same hook surface.
        """
        n = len(line)
        for i, word in enumerate(line):
            self.write_string_with_positions(
                word.get_text(), word.get_text_positions(), sink
            )
            if i < n - 1:
                self.write_word_separator(sink)

    def write_paragraph_separator(self, sink: Callable[[str], None]) -> None:
        """Emit ``paragraph_end`` followed by ``paragraph_start``.

        Mirrors upstream's protected ``writeParagraphSeparator``
        (PDFTextStripper.java:1697)."""
        self.write_paragraph_end(sink)
        self.write_paragraph_start(sink)

    def match_list_item_pattern(
        self, pw: PositionWrapper
    ) -> re.Pattern[str] | None:
        """Return the list-item regex matching the wrapped position's
        decoded text, or ``None`` when none match.

        Mirrors upstream's private ``matchListItemPattern``
        (PDFTextStripper.java:1763). Public here because Python lacks
        Java's package-private visibility distinction — subclasses may
        want to call it directly."""
        tp = pw.get_text_position()
        return self.match_pattern(tp.get_unicode(), self.get_list_item_patterns())

    def create_word(
        self,
        word: str,
        word_positions: list[TextPosition],
    ) -> WordWithTextPositions:
        """Build a :class:`WordWithTextPositions` for ``word`` after
        running it through :meth:`normalize_word`.

        Mirrors upstream's private ``createWord``
        (PDFTextStripper.java:2035)."""
        return WordWithTextPositions(self.normalize_word(word), word_positions)

    def normalize_word(self, word: str) -> str:
        """Normalise Unicode presentation forms in ``word`` and apply the
        bidi reordering performed by :meth:`handle_direction`.

        Mirrors upstream's private ``normalizeWord``
        (PDFTextStripper.java:2047). Decomposes Unicode Alphabetic
        Presentation Forms (FB00–FDFF) and Arabic Presentation Forms-B
        (FE70–FEFF) via NFKC, with the upstream-specific quirks for
        U+FDF2 (the ``Allah`` ligature) and reversed Hebrew/Arabic
        decompositions preserved."""
        builder: list[str] = []
        p = 0
        q = 0
        str_length = len(word)
        had_change = False
        while q < str_length:
            c = word[q]
            cp = ord(c)
            if (0xFB00 <= cp <= 0xFDFF) or (0xFE70 <= cp <= 0xFEFF):
                if not had_change:
                    builder = []
                    had_change = True
                builder.append(word[p:q])
                if cp == 0xFDF2 and q > 0 and ord(word[q - 1]) in (0x0627, 0xFE8D):
                    # Compensate for fonts that map U+FDF2 with a leading
                    # alif by inserting the canonical Allah-without-alif
                    # decomposition.
                    builder.append("لله")
                else:
                    normalized = unicodedata.normalize("NFKC", word[q : q + 1]).strip()
                    if cp >= 0xFB1D and len(normalized) > 1:
                        normalized = normalized[::-1]
                    builder.append(normalized)
                p = q + 1
            q += 1
        if not had_change:
            return self.handle_direction(word)
        builder.append(word[p:q])
        return self.handle_direction("".join(builder))

    def handle_direction(self, word: str) -> str:
        """Reorder a string from logical to visual order for mixed bidi
        text. Mirrors upstream's private ``handleDirection``
        (PDFTextStripper.java:1903).

        Wave 1387 closes the long-standing ICU-bidi divergence by
        routing through :class:`pypdfbox.text.bidi.BidiResolver` — a
        stdlib-only port of UAX #9 (paragraph-direction detection +
        explicit embedding/override/isolate stack + weak/neutral/
        implicit resolution + L1-L4 reorder). The pure-LTR fast path
        from upstream is preserved (`Bidi.isMixed() == false &&
        baseLevel == LTR` → return unchanged); otherwise the resolver
        produces per-codepoint embedding levels and we reorder via the
        standard reverse-runs algorithm, applying Unicode mirroring
        (`L4`) on every RTL-level codepoint that declares
        :func:`unicodedata.mirrored`.
        """
        if not word:
            return word
        # Fast-path: scan for any strong-RTL character or explicit
        # formatting; if absent, the paragraph is pure LTR and the bidi
        # algorithm is the identity (matches upstream's
        # ``!bidi.isMixed() && baseLevel == DIRECTION_LEFT_TO_RIGHT``
        # short-circuit at PDFTextStripper.java:1911).
        needs_resolve = False
        for ch in word:
            cls = unicodedata.bidirectional(ch)
            if cls in ("R", "AL", "AN", "RLE", "RLO", "RLI", "FSI", "LRE", "LRO", "LRI"):
                needs_resolve = True
                break
        if not needs_resolve:
            return word
        paragraph_dir = get_paragraph_direction(word)
        resolver = BidiResolver()
        levels = resolver.resolve(word, paragraph_direction=paragraph_dir)
        # If the resolver agrees the paragraph is pure LTR (every level
        # 0), nothing to reorder.
        if all(level == 0 for level in levels):
            return word
        # L2 — reverse all level runs from highest level down to the
        # lowest odd level. Then apply L4 mirroring on every RTL-level
        # codepoint.
        indices = _bidi_reorder_indices(levels)
        out: list[str] = []
        for i in indices:
            ch = word[i]
            level = levels[i]
            if level % 2 == 1 and unicodedata.mirrored(ch):
                mirror = _BIDI_MIRROR_MAP.get(ch)
                out.append(mirror if mirror is not None else ch)
            else:
                out.append(ch)
        return "".join(out)

    def normalize(
        self, line: list[_LineItem]
    ) -> list[WordWithTextPositions]:
        """Walk a list of :class:`_LineItem` entries and produce a list
        of normalized :class:`WordWithTextPositions`.

        Mirrors upstream's private ``normalize(List<LineItem>)``
        (PDFTextStripper.java:1874). The ``LineItem`` sentinel pattern is
        ported as :class:`_LineItem`."""
        normalized: list[WordWithTextPositions] = []
        line_builder: list[str] = []
        word_positions: list[TextPosition] = []
        for item in line:
            self.normalize_add(normalized, line_builder, word_positions, item)
        if line_builder:
            normalized.append(self.create_word("".join(line_builder), list(word_positions)))
        return normalized

    def normalize_add(
        self,
        normalized: list[WordWithTextPositions],
        line_builder: list[str],
        word_positions: list[TextPosition],
        item: _LineItem,
    ) -> None:
        """Append a :class:`_LineItem` to the normalized line buffers.

        Mirrors upstream's private ``normalizeAdd``
        (PDFTextStripper.java:2111). Upstream returns a
        ``StringBuilder`` (a freshly allocated one when the item is a
        word separator) — we mutate ``line_builder`` and
        ``word_positions`` in place to match Python conventions while
        preserving the same caller contract."""
        if item.is_word_separator():
            normalized.append(
                self.create_word("".join(line_builder), list(word_positions))
            )
            line_builder.clear()
            word_positions.clear()
            return
        text = item.get_text_position()
        if text is not None:
            line_builder.append(text.get_visually_ordered_unicode())
            word_positions.append(text)

    @staticmethod
    def parse_bidi_file(input_stream: object) -> dict[str, str]:
        """Parse the upstream ``BidiMirroring.txt`` resource format and
        return a ``{char: mirrored_char}`` map.

        Mirrors upstream's private static ``parseBidiFile(InputStream)``
        (PDFTextStripper.java:1992). Lite mode keeps the parser as a
        utility — the actual mirroring map is supplied by Unicode's
        bidi data inside :func:`unicodedata.mirrored` plus the system
        font metrics, so the result is informational rather than
        load-bearing for layout."""
        mirroring: dict[str, str] = {}
        if input_stream is None:
            return mirroring
        # Accept both file-like and bytes/str inputs.
        data = input_stream.read() if hasattr(input_stream, "read") else input_stream
        text = (
            data.decode("ascii", errors="replace")
            if isinstance(data, bytes)
            else str(data)
        )
        for raw_line in text.splitlines():
            line = raw_line
            comment_at = line.find("#")
            if comment_at != -1:
                line = line[:comment_at]
            if len(line) < 2:
                continue
            tokens = [t.strip() for t in line.split(";") if t.strip()]
            if len(tokens) == 2:
                try:
                    a = chr(int(tokens[0], 16))
                    b = chr(int(tokens[1], 16))
                except ValueError:
                    continue
                mirroring[a] = b
        return mirroring

    def handle_line_separation(
        self,
        current: PositionWrapper,
        last_position: PositionWrapper | None,
        last_line_start: PositionWrapper | None,
        max_height_for_line: float,
    ) -> PositionWrapper:
        """Mark ``current`` as a line start and (when the heuristic
        agrees) a paragraph start.

        Mirrors upstream's private ``handleLineSeparation``
        (PDFTextStripper.java around the writePage paragraph block).
        Returns the wrapper that should be remembered as the new
        ``last_line_start_position``.
        """
        current.set_line_start()
        if last_position is not None:
            prev = last_position.get_text_position()
            cur_tp = current.get_text_position()
            if self.is_paragraph_separation(cur_tp, prev):
                current.set_paragraph_start()
        return current

    @staticmethod
    def word_with_text_positions(
        word: str, positions: list[TextPosition]
    ) -> WordWithTextPositions:
        """Lite-mode factory matching the upstream inner-class
        constructor signature ``new WordWithTextPositions(word, positions)``.
        Provided so ports of upstream code can call the same name without
        having to import the standalone class."""
        return WordWithTextPositions(word, positions)

    # ---------- marked-content hooks ----------

    def begin_marked_content_sequence(
        self,
        tag: COSName | None,
        properties: COSDictionary | None,
    ) -> None:
        """Hook invoked at every ``BMC`` / ``BDC`` operator. Tracks
        ``/ActualText`` so subsequent runs use the marked-content
        replacement instead of their raw glyph text.

        Mirrors upstream's overridden
        ``beginMarkedContentSequence(COSName, COSDictionary)``
        (PDFTextStripper.java:863). Lite mode does not yet route the
        content-stream walker through the marked-content stack, so the
        captured ``actual_text`` is exposed for subclasses but not
        consumed by the default extraction path. See CHANGES.md."""
        actual: str | None = None
        if properties is not None:
            try:
                raw = properties.get_string("ActualText")
            except Exception:  # noqa: BLE001 — defensive
                raw = None
            if raw is not None:
                actual = raw.replace("­", "")
        self._marked_content_stack.append((tag, properties, actual))
        if actual is not None:
            self._actual_text = actual
            self._first_actual_text_position = True

    def end_marked_content_sequence(self) -> None:
        """Hook invoked at every ``EMC`` operator. Pops the
        marked-content stack and clears ``actual_text`` when the popped
        entry contributed it.

        Mirrors upstream's overridden ``endMarkedContentSequence``
        (PDFTextStripper.java:877)."""
        if not self._marked_content_stack:
            return
        _, _, actual = self._marked_content_stack.pop()
        if actual is not None:
            self._actual_text = None


class _LineItem:
    """Marker class used as a placeholder in a list of
    :class:`TextPosition` runs being normalised into words.

    Mirrors upstream's private inner class
    ``PDFTextStripper.LineItem`` (PDFTextStripper.java:2133): a singleton
    sentinel signals a word boundary; otherwise the entry carries a
    single ``TextPosition``. Promoted to a top-level (module-private)
    class so the ``normalize`` / ``normalize_add`` hooks can be invoked
    without nested-class gymnastics."""

    WORD_SEPARATOR: _LineItem  # set after the class body

    __slots__ = ("_text_position",)

    def __init__(self, text_position: TextPosition | None = None) -> None:
        self._text_position = text_position

    @classmethod
    def get_word_separator(cls) -> _LineItem:
        """Return the singleton word-separator sentinel."""
        return cls.WORD_SEPARATOR

    def get_text_position(self) -> TextPosition | None:
        return self._text_position

    def is_word_separator(self) -> bool:
        return self._text_position is None


_LineItem.WORD_SEPARATOR = _LineItem()


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
        "ctm",
        "gs_stack",
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
        # Current transformation matrix (CTM). The ``cm`` operator
        # concatenates onto it; ``q`` / ``Q`` push / pop it. Tracking the
        # CTM lets the emitter compute the full text-rendering matrix
        # (textMatrix × CTM) the way upstream ``PDFStreamEngine.showText``
        # does, so producers that fold the point size into ``Tm`` and
        # position each line via a per-line ``cm`` are scaled and placed
        # correctly instead of collapsing to a single baseline at size 1.
        self.ctm: Matrix = Matrix()
        self.gs_stack: list[Matrix] = []


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
