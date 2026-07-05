from __future__ import annotations

import logging
import math
import re
import sys
import unicodedata
from collections.abc import Callable
from functools import cmp_to_key
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

_log = logging.getLogger(__name__)

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
    from pypdfbox.pdmodel.pd_resources import PDResources


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
        # Page-rotation bookkeeping for the per-page coordinate fold. Mirrors
        # upstream ``LegacyPDFStreamEngine``'s ``pageRotation`` / ``pageSize``
        # fields (LegacyPDFStreamEngine.java:82-83, set in ``processPage``).
        # The page ``/Rotate`` (0/90/180/270) and the cropbox extents feed the
        # ``TextPosition`` page-rotation accessors (``getX``/``getY``/``getWidth``,
        # via ``getXRot``/``getYLowerLeftRot``/``getWidthRot`` —
        # TextPosition.java:293-446) so a rotated page's runs are grouped in the
        # device (rotated) frame, the way the default-path (``sortByPosition``
        # false) ``writePage`` consumes ``getX()``/``getY()``/``getWidth()``
        # (PDFTextStripper.java:585-591).
        self._page_rotation: int = 0
        self._page_width: float = 0.0
        self._page_height: float = 0.0
        self._active_cmap: CMap | None = None
        self._active_font: PDFont | None = None
        # Resources override active while recursing into a form XObject's
        # content stream (the ``Do`` operator). When set, font / ToUnicode /
        # property-list lookups consult these resources instead of the host
        # page's — mirroring upstream ``PDFStreamEngine.showForm`` pushing the
        # form's ``/Resources`` for the duration of the form body. ``None``
        # restores the page-level resources.
        self._active_resources: PDResources | None = None
        # Form-XObject recursion depth guard, matching the upstream
        # ``DrawObject`` cap of 50 nested forms.
        self._form_level: int = 0
        # Per-glyph advance for the active font in user-space units (i.e.
        # already multiplied by ``font_size`` and divided by 1000). When
        # ``None`` we fall back to the legacy 0.5-em estimate so unknown
        # fonts still produce monotonic text-x advances.
        self._active_avg_advance: float | None = None
        # Glyph height (text-space fraction of the em) of the active font,
        # computed via ``_compute_font_height`` and recomputed on every
        # ``Tf``. ``None`` falls back to the half-em proxy. Cached per font
        # object in ``_font_height_cache`` for the page lifetime, mirroring
        # upstream's ``LegacyPDFStreamEngine.fontHeightMap``.
        self._active_font_height: float | None = None
        self._font_height_cache: dict[int, float] = {}
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
        ``page_start`` / ``page_end``; each article (bead bucket) within a
        page is wrapped in ``article_start`` / ``article_end`` — mirroring
        upstream's per-``charactersByArticle`` ``startArticle`` /
        ``endArticle``. A page with no beads is a single article.

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
        # Mirror upstream ``writeText``: when ``add_more_formatting`` is on,
        # the paragraph-end, page-start and article-start/end markers are all
        # promoted to the line separator so each structural boundary becomes a
        # visible break. Markers stay at their explicit (default "") values
        # otherwise.
        if self.get_add_more_formatting():
            self._paragraph_end = self._line_separator
            self._page_start = self._line_separator
            self._article_start = self._line_separator
            self._article_end = self._line_separator
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
                # ``article_start`` / ``article_end`` are emitted per article
                # (bead bucket) inside ``_format_positions`` — mirroring
                # upstream's ``startArticle()`` / ``endArticle()`` around each
                # ``charactersByArticle`` entry — rather than once around the
                # whole page. For a page with no beads this collapses to a
                # single article wrap, preserving the prior single-group
                # behaviour.
                _sink(self.process_page(page))
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
            # A page with no content stream is still an empty article in
            # upstream's ``writePage`` loop — emit the same empty-article
            # wrap a glyph-free (but non-empty) content stream would (see
            # :meth:`_empty_article_wrap`).
            self._characters_by_article = [[]]
            return self._empty_article_wrap()
        # Bind the page so ``Tf`` handlers can reach ``/Resources`` for
        # ``/ToUnicode`` and typed-font lookup, and clear the per-page
        # caches.
        self._active_page = page
        # Snapshot the page rotation + cropbox extents for the per-page
        # coordinate fold (``_apply_page_rotation`` below). Mirrors upstream
        # ``LegacyPDFStreamEngine.processPage`` (LegacyPDFStreamEngine.java:
        # 139-153), which records ``pageRotation`` and the cropbox so each
        # ``TextPosition`` is constructed with the page rotation and page
        # dimensions. Defensive against a malformed ``/Rotate`` or missing
        # cropbox so unrotated pages keep their existing raw-user-space frame.
        try:
            self._page_rotation = int(page.get_rotation()) % 360
        except Exception:  # noqa: BLE001 — defensive: bad /Rotate
            self._page_rotation = 0
        try:
            crop = page.get_crop_box()
            self._page_width = float(crop.get_width())
            self._page_height = float(crop.get_height())
        except Exception:  # noqa: BLE001 — defensive: missing/odd CropBox
            self._page_width = 0.0
            self._page_height = 0.0
        self._cmap_cache = {}
        self._font_cache = {}
        self._active_cmap = None
        self._active_font = None
        self._active_avg_advance = None
        self._active_font_height = None
        self._font_height_cache = {}
        try:
            positions = self._extract_positions(body)
            # Fold the page ``/Rotate`` into each run's stored coordinates so
            # the line/word grouping consumes the device (rotated) frame, the
            # way upstream's default-path ``writePage`` reads
            # ``getX()``/``getY()``/``getWidth()`` (PDFTextStripper.java:
            # 585-591). No-op when the page is unrotated.
            self._apply_page_rotation(positions)
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

    def _apply_page_rotation(self, positions: list[TextPosition]) -> None:
        """Fold the page ``/Rotate`` into each run's stored ``x``/``y``/``width``.

        Faithful port of upstream's page-rotation coordinate handling. In Apache
        PDFBox the page rotation is **not** baked into the CTM
        (``PDPage.getMatrix()`` returns the identity — PDPage.java:385-389);
        instead every ``TextPosition`` is constructed with the page rotation +
        page dimensions (``LegacyPDFStreamEngine.showGlyph`` →
        ``new TextPosition(pageRotation, pageWidth, pageHeight, ...)``,
        LegacyPDFStreamEngine.java:309-313) and the *page-rotation-adjusted*
        coordinates are derived lazily by ``TextPosition``'s constructor /
        accessors:

          * ``getX()``      = ``getXRot(rotation)``        (TextPosition.java:293)
          * ``getY()`` (raw lower-left) = ``getYLowerLeftRot(rotation)``
                                                            (TextPosition.java:356)
          * ``getWidth()``  = ``getWidthRot(rotation)``    (TextPosition.java:426)

        The default extraction path (``sortByPosition`` false — the
        ``PDFTextStripper`` default) groups on exactly these page-rotation
        accessors (``writePage``, PDFTextStripper.java:585-591), so a rotated
        page's glyphs land in the rotated *device* frame: a row of horizontal
        glyphs on a ``/Rotate 90`` page advances along the grouping's *line*
        axis (each glyph a new ``getY``) and reports zero ``getWidth`` (its
        text-space extent is perpendicular to the rotated width axis), which is
        what fragments the rotated rows in Java's output.

        The lite ``TextPosition`` carries Y in the PDF user-space (y-up,
        lower-left-origin) frame the existing heuristics are calibrated for, so
        this fold stores ``getYLowerLeftRot`` (upstream's ``getY()`` mirrored by
        a page-extent constant) rather than the upper-left ``getY()`` — the
        relative geometry the difference/overlap heuristics consume is
        identical, and ``/Rotate 0`` is a verbatim no-op (``getXRot(0)`` /
        ``getYLowerLeftRot(0)`` / ``getWidthRot(0)`` are the raw translate /
        run width the lite emitter already stored).
        """
        rotation = self._page_rotation
        if rotation == 0:
            # Unrotated page — leave the raw user-space coordinates untouched
            # (byte-exact with every pre-fold extraction). Still record the
            # page geometry + rotation on the positions for API parity with
            # upstream ``getRotation``/``getPageWidth``/``getPageHeight``.
            pw = self._page_width
            ph = self._page_height
            for pos in positions:
                pos.rotation = 0.0
                pos.page_width = pw
                pos.page_height = ph
            return
        pw = self._page_width
        ph = self._page_height
        for pos in positions:
            raw_x = pos.x
            raw_y = pos.y
            raw_width = pos.width
            # ``getWidthRot`` (TextPosition.java:426-436): for 90/270 the width
            # is measured along Y (``|endY - ty|``), for 0/180 along X
            # (``|endX - tx|``). The lite run is laid along its text direction
            # (``dir``), so its raw end point is the origin stepped by the run
            # width along that direction: ``endX = x + width·cosθ``,
            # ``endY = y + width·sinθ``. A horizontal run (``dir == 0``) has
            # ``endY == y`` so its 90/270 rotated width is 0 — the zero-extent
            # that fragments the rotated row in Java's output.
            theta = math.radians(pos.dir % 360.0)
            end_x_raw = raw_x + raw_width * math.cos(theta)
            end_y_raw = raw_y + raw_width * math.sin(theta)
            width_adj = (
                abs(end_y_raw - raw_y)
                if rotation in (90, 270)
                else abs(end_x_raw - raw_x)
            )
            # ``getXRot`` (TextPosition.java:293-312).
            if rotation == 90:
                x_adj = raw_y
            elif rotation == 180:
                x_adj = pw - raw_x
            elif rotation == 270:
                x_adj = ph - raw_y
            else:
                x_adj = raw_x
            # Line-flow axis (``getY`` — TextPosition.java:325-328, the value
            # the default-path grouping reads at PDFTextStripper.java:588). The
            # grouping accumulates the line extent with ``maxYForLine = max(...)``
            # (PDFTextStripper.java:689-692; lite ``max_y_for_line``), which is
            # **not** symmetric under negation — so the stored Y must run in the
            # SAME direction as upstream's ``getY()`` for the line accumulation
            # to match, rather than the lower-left mirror. (For ``/Rotate 0``
            # the within-line Y is constant, so the lite's historical raw-``ty``
            # y-up frame and upstream's ``pageHeight - ty`` agree regardless of
            # direction and stay byte-exact; that no-op case is handled above.)
            # ``getY`` = ``pageHeight - getYLowerLeftRot`` (0/180) or
            # ``pageWidth - getYLowerLeftRot`` (90/270) — TextPosition.java:
            # 110-117 / 406-418.
            if rotation == 90:
                # getYLowerLeftRot(90) = pageWidth - tx ⇒ getY = tx = raw_x.
                y_adj = raw_x
            elif rotation == 180:
                y_adj = ph - raw_y
            elif rotation == 270:
                # getYLowerLeftRot(270) = tx ⇒ getY = pageWidth - tx.
                y_adj = pw - raw_x
            else:
                y_adj = raw_y
            pos.x = x_adj
            pos.y = y_adj
            pos.width = width_adj
            pos.rotation = float(rotation)
            pos.page_width = pw
            pos.page_height = ph

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
            # Mark the text object open — text matrix + line matrix are now
            # non-null, so the show/move operators are permitted (upstream
            # ``BeginText`` sets both matrices to identity).
            state.in_text_object = True
        elif op == "ET":
            # End text object — clears the text + line matrices (upstream
            # ``EndText`` sets both to null). Subsequent text/positioning
            # operators stranded outside a BT…ET pair are ignored.
            state.in_text_object = False
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
                self._active_font_height = self._compute_font_height(
                    self._active_font
                )
        elif op == "TL":
            if operands and isinstance(operands[0], COSNumber):
                state.leading = operands[0].float_value()
        elif op == "Td":
            # Upstream ``MoveText`` ignores ``Td`` when the text-line matrix
            # is null (outside a BT…ET pair).
            if not state.in_text_object:
                return
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
            if not state.in_text_object:
                return
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
                # ``Tm`` sets both the text matrix and the text-line matrix to
                # the supplied affine — making both non-null even when no
                # ``BT`` is open (upstream ``SetMatrix`` does not gate). So a
                # ``Tj`` after a stray ``Tm`` would render; mark the text
                # object effectively open to mirror that.
                state.in_text_object = True
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
            if not state.in_text_object:
                return
            # Move to start of next line — equivalent to ``0 -leading Td``.
            # The ``(0, -leading)`` text-space delta is carried through the
            # text-matrix scale/shear before moving the line origin.
            state.line_x += -state.leading * state.tm_c
            state.line_y += -state.leading * state.tm_d
            state.text_x = state.line_x
            state.text_y = state.line_y
        elif op == "Tj":
            # Upstream ``ShowText`` ignores ``Tj`` when the text matrix is null
            # (outside a BT…ET pair).
            if not state.in_text_object:
                return
            if operands and isinstance(operands[0], COSString):
                self._emit(operands[0], state, positions)
        elif op == "TJ":
            # Upstream ``ShowTextAdjusted`` ignores ``TJ`` when the text matrix
            # is null (outside a BT…ET pair).
            if not state.in_text_object:
                return
            if operands and isinstance(operands[0], COSArray):
                self._emit_tj_array(operands[0], state, positions)
        elif op == "'":
            # ``'`` = ``T*`` then ``Tj``; both halves are no-ops outside a
            # text object (text-line / text matrix null).
            if not state.in_text_object:
                return
            # Move to next line then show string.
            state.line_x += -state.leading * state.tm_c
            state.line_y += -state.leading * state.tm_d
            state.text_x = state.line_x
            state.text_y = state.line_y
            if operands and isinstance(operands[0], COSString):
                self._emit(operands[0], state, positions)
        elif op == '"':
            # ``aw ac string "`` — set word + char spacing, next line, show.
            # Upstream runs ``Tw`` / ``Tc`` unconditionally, then a gated
            # ``T*`` + ``Tj`` (no-ops outside a text object). Set the spacing
            # first, then skip the show when no text object is open.
            if (
                len(operands) >= 3
                and isinstance(operands[0], COSNumber)
                and isinstance(operands[1], COSNumber)
                and isinstance(operands[2], COSString)
            ):
                state.word_spacing = operands[0].float_value()
                state.char_spacing = operands[1].float_value()
                if not state.in_text_object:
                    return
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
        elif op == "Tz":
            # Horizontal text scaling — operand is a percentage (100 = no
            # scaling). Stored as a fraction (``Tz/100``); scales the
            # horizontal glyph displacement the word-gap heuristic measures
            # (PDF 32000-1 §9.3.4).
            if operands and isinstance(operands[0], COSNumber):
                state.horizontal_scaling = operands[0].float_value() / 100.0
        elif op == "Ts":
            # Text rise — a vertical baseline shift in unscaled text-space
            # units (PDF 32000-1 §9.3.7). Positive raises the baseline of
            # subsequent glyphs (superscript), negative lowers it
            # (subscript). It is applied to the rendered glyph origin via the
            # text-rendering matrix (see ``_text_rendering_matrix``) and does
            # not affect the cursor advance; a later ``0 Ts`` resets it.
            if operands and isinstance(operands[0], COSNumber):
                state.text_rise = operands[0].float_value()
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
        elif op == "BMC":
            # Begin marked content with a bare tag (no property list).
            # Upstream ``BeginMarkedContentSequence.process`` iterates the
            # whole operand list and keeps the *last* ``COSName`` (any
            # leading non-name junk is skipped), so ``1 (x) /Span BMC``
            # opens the ``/Span`` sequence. Mirror the registered operator
            # / ``_props.extract_tag`` here rather than taking ``operands[0]``.
            tag = self._last_cos_name(operands)
            self.begin_marked_content_sequence(tag, None)
        elif op == "BDC":
            # Begin marked content with a property list — the source of
            # an ``/ActualText`` replacement (PDF §14.9.4). Unlike BMC, the
            # tag is the *first* operand (``operands[0]``): the property
            # operand of the ``/Name`` form is itself a ``COSName`` and must
            # not be mistaken for the tag (matches upstream
            # ``BeginMarkedContentSequenceWithProperties`` / the registered
            # ``BeginMarkedContentWithProps`` operator). When the tag is not a
            # name, or the property list cannot be resolved to a dictionary
            # (unknown ``/Name``, wrong type, missing resources), upstream
            # ``BeginMarkedContentSequenceWithProperties.process`` returns
            # *without* opening a sequence (``propDict == null``) — so we do
            # not open one either; the matching EMC still pops the parent,
            # matching upstream's no-underflow ``endMarkedContentSequence``.
            tag = operands[0] if operands and isinstance(operands[0], COSName) else None
            if tag is None:
                return
            properties = self._resolve_bdc_properties(operands)
            if properties is None:
                return
            self.begin_marked_content_sequence(tag, properties)
        elif op == "EMC":
            self.end_marked_content_sequence()
        elif op == "Do":
            # Draw an XObject. For text extraction we descend into form
            # XObjects (and transparency groups, which are form XObjects)
            # so their show-text operators contribute to the page text —
            # mirroring upstream ``PDFStreamEngine.showForm`` reached via
            # the ``DrawObject`` operator. Image XObjects carry no text and
            # are skipped.
            self._show_form_xobject(operands, state, positions)
        # Other operators (paths, colour, marked-content points, etc.) are
        # intentionally ignored — they have no effect on the lite text
        # stream.

    def _show_form_xobject(
        self,
        operands: list[COSBase],
        state: _TextState,
        positions: list[TextPosition],
    ) -> None:
        """``Do`` — recurse into a form XObject's content stream.

        Resolves the named XObject through the resources currently in
        effect, skips image XObjects (no text), and for a form / group
        XObject concatenates the form's ``/Matrix`` onto the current CTM
        and replays the form body so its show-text operators emit text.
        The form's ``/Resources`` are pushed for the duration so its own
        ``Tf`` names resolve against the right font dictionaries. Recursion
        depth is capped at 50, matching upstream's ``DrawObject`` guard.
        """
        if not operands or not isinstance(operands[0], COSName):
            return
        name = operands[0]
        resources = self._current_resources()
        if resources is None:
            return
        try:
            is_image = getattr(resources, "is_image_x_object", None)
            if is_image is not None and is_image(name):
                return
            xobject = resources.get_x_object(name)
        except Exception:  # noqa: BLE001 — defensive: malformed XObject entry
            return
        if xobject is None:
            return
        if type(xobject).__name__ not in {"PDFormXObject", "PDTransparencyGroup"}:
            return
        if self._form_level >= 50:
            _log.error("recursion is too deep, skipping form XObject")
            return

        try:
            body = self._get_form_contents(xobject)
        except Exception:  # noqa: BLE001 — defensive: malformed form stream
            return
        if not body:
            return

        # Concatenate the form's /Matrix onto the current CTM (PDF §8.10.1).
        form_matrix = self._form_matrix(xobject)
        form_ctm = form_matrix.multiply(state.ctm)

        # Save and swap the resolution context: the form's own resources and
        # a fresh per-context font/cmap cache (resource names like ``F0`` can
        # mean different fonts inside the form than on the host page).
        saved_resources = self._active_resources
        saved_cmap_cache = self._cmap_cache
        saved_font_cache = self._font_cache
        saved_active_cmap = self._active_cmap
        saved_active_font = self._active_font
        saved_avg_advance = self._active_avg_advance
        saved_font_height = self._active_font_height
        try:
            form_resources = xobject.get_resources()
        except Exception:  # noqa: BLE001 — defensive
            form_resources = None
        self._active_resources = form_resources
        self._cmap_cache = {}
        self._font_cache = {}
        self._active_cmap = None
        self._active_font = None
        self._active_avg_advance = None
        self._active_font_height = None
        self._form_level += 1

        form_state = _TextState()
        form_state.ctm = form_ctm
        try:
            with RandomAccessReadBuffer(body) as src:
                parser = PDFStreamParser(src)
                form_operands: list[COSBase] = []
                for token in parser.tokens():
                    if isinstance(token, Operator):
                        self._dispatch(
                            token.get_name(), form_operands, form_state, positions
                        )
                        form_operands = []
                    else:
                        form_operands.append(token)
        finally:
            self._form_level -= 1
            self._active_resources = saved_resources
            self._cmap_cache = saved_cmap_cache
            self._font_cache = saved_font_cache
            self._active_cmap = saved_active_cmap
            self._active_font = saved_active_font
            self._active_avg_advance = saved_avg_advance
            self._active_font_height = saved_font_height

    @staticmethod
    def _get_form_contents(xobject: object) -> bytes:
        """Return the decoded content-stream bytes of a form XObject."""
        cos = xobject.get_cos_object()  # type: ignore[attr-defined]
        if not isinstance(cos, COSStream):
            return b""
        with cos.create_input_stream() as src:
            return src.read()

    @staticmethod
    def _form_matrix(xobject: object) -> Matrix:
        """Return the form's ``/Matrix`` as a :class:`Matrix` (identity when
        absent or malformed)."""
        try:
            values = xobject.get_matrix()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 — defensive
            return Matrix()
        if values is None or len(values) != 6:
            return Matrix()
        a, b, c, d, e, f = (float(v) for v in values)
        return Matrix(a, b, c, d, e, f)

    @staticmethod
    def _last_cos_name(operands: list[COSBase]) -> COSName | None:
        """Return the **last** ``COSName`` among the operands, or ``None``.

        Mirrors upstream ``BeginMarkedContentSequence.process`` /
        ``MarkedContentPoint.process`` (and the shared
        ``_props.extract_tag`` helper used by the registered operators):
        the whole operand list is scanned and the most recent ``COSName``
        wins, so any leading non-name junk (numbers, strings) is skipped
        rather than aborting tag selection. Used for the inline ``BMC``
        dispatch; ``BDC`` deliberately uses ``operands[0]`` instead.
        """
        tag: COSName | None = None
        for argument in operands:
            if isinstance(argument, COSName):
                tag = argument
        return tag

    def _resolve_bdc_properties(
        self,
        operands: list[COSBase],
    ) -> COSDictionary | None:
        """``BDC`` carries either an inline property dictionary or a
        ``COSName`` referencing the active page resources' ``/Properties``
        subdictionary. The inline dictionary wins; otherwise resolve the
        name through the page resources. Returns ``None`` when neither is
        present or the resource lookup fails (defensive against malformed
        resources).
        """
        if len(operands) < 2:
            return None
        prop = operands[1]
        if isinstance(prop, COSDictionary):
            return prop
        if isinstance(prop, COSName) and self._active_page is not None:
            try:
                resources = self._current_resources()
                if resources is None:
                    return None
                pl = resources.get_property_list(prop)
                if pl is not None:
                    return pl.get_cos_object()
            except Exception:  # noqa: BLE001 — defensive: malformed resources
                return None
        return None

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

        Text rise (``Ts``) is folded in the way upstream
        ``PDFStreamEngine.showText`` does: as the f-translation of the
        font-parameter matrix applied *before* the text matrix
        (``parameterMatrix × textMatrix × ctm``). In this lite port the font
        size is applied separately, so the rise-bearing parameter matrix is
        just the translation ``[1, 0, 0, 1, 0, rise]``. Composing it first
        shifts the glyph origin along the text matrix's local Y axis — so a
        positive rise lifts a superscript run above the baseline (and a
        rotated ``Tm`` rotates the shift with it) without touching the
        glyph's scale or direction.
        """
        text_matrix = Matrix(
            state.tm_a, state.tm_b, state.tm_c, state.tm_d, state.text_x, state.text_y
        )
        rise = getattr(state, "text_rise", 0.0)
        if rise:
            parameter_matrix = Matrix(1.0, 0.0, 0.0, 1.0, 0.0, rise)
            return parameter_matrix.multiply(text_matrix).multiply(state.ctm)
        return text_matrix.multiply(state.ctm)

    @staticmethod
    def _text_dir(trm: Matrix) -> float:
        """Text direction in degrees (0 / 90 / 180 / 270) for a run.

        Mirrors upstream ``TextPosition.getDir()``: the direction is the
        rotation baked into the text-rendering matrix, snapped to the
        nearest right angle. PDFBox derives it from the matrix's X basis
        vector — ``getScaleX()`` (slot 0,0) and ``getShearY()`` (slot 0,1)
        — so a ``Tm`` rotated 90/180/270° (or a page-rotation folded into
        the CTM) yields the matching quadrant. ``atan2`` of that basis
        vector gives the angle; we normalise to ``[0, 360)`` and snap to a
        multiple of 90 so a glyph painted with ``Matrix.getRotateInstance``
        reports exactly 0/90/180/270 the way Apache PDFBox does.
        """
        angle = math.degrees(math.atan2(trm.get_shear_y(), trm.get_scale_x()))
        # Snap to the nearest right angle and fold into [0, 360).
        quadrant = round(angle / 90.0) * 90
        return float(quadrant % 360)

    def _glyph_segments(
        self,
        text_bytes: bytes,
        state: _TextState,
        font: PDFont | None,
        fallback_advance: float,
    ) -> list[tuple[str, float, float]] | None:
        """Decode ``text_bytes`` into per-glyph ``(unicode, advance, width)``.

        Threads real per-glyph advances through the lite stripper: each
        character code is read via the font's ``read_code`` (1–4 bytes for
        Type0/CID composite fonts, single byte for simple fonts), decoded to
        its Unicode piece, and assigned its true displacement

            ``w0 / 1000 × fontSize + Tc (+ Tw on single-byte code 32)``

        in unscaled text space (the caller applies horizontal scaling
        ``Th``). ``w0`` is the font's per-code width from ``PDFont.get_width``
        (the ``/Widths`` array or the embedded font program — oracle-verified
        wave 1408). Mirrors upstream ``PDFStreamEngine.showText`` /
        ``PDFont.getDisplacement`` (PDF 32000-1 §9.4.4).

        Returns ``None`` when the font is unavailable or cannot decode the
        bytes, so the caller falls back to the average-advance path that keeps
        malformed PDFs producing monotonic cursor steps.
        """
        if font is None:
            return None
        read_code = getattr(font, "read_code", None)
        get_width = getattr(font, "get_width", None)
        if not callable(read_code) or not callable(get_width):
            return None
        try:
            from pypdfbox.pdmodel.font import PDType3Font  # noqa: PLC0415

            type3_scale = (
                font.get_font_matrix()[0]
                if isinstance(font, PDType3Font)
                else None
            )
        except Exception:  # noqa: BLE001 — defensive
            type3_scale = None
        font_size = state.font_size
        char_spacing = state.char_spacing
        word_spacing = state.word_spacing
        segments: list[tuple[str, float, float]] = []
        offset = 0
        n = len(text_bytes)
        try:
            while offset < n:
                code, consumed = read_code(text_bytes, offset)
                if consumed <= 0:
                    return None
                # Decode this single code to its Unicode piece, reusing the
                # same resolution order ``_decode_show_text`` follows.
                piece = self._decode_code_to_unicode(
                    text_bytes[offset : offset + consumed], code, font
                )
                w0 = float(get_width(code))
                if type3_scale is not None:
                    glyph_width = w0 * type3_scale * font_size
                else:
                    glyph_width = w0 / 1000.0 * font_size
                advance = glyph_width + char_spacing
                # ``Tw`` (word spacing) applies only to the single-byte code
                # 32 (PDF 32000-1 §9.3.3) — never to a 2-byte composite code.
                if consumed == 1 and code == 32:
                    advance += word_spacing
                segments.append((piece, advance, glyph_width))
                offset += consumed
        except Exception:  # noqa: BLE001 — defensive: malformed font / decode
            return None
        if not segments:
            return None
        # When the per-code decode yields nothing useful (every width zero
        # and no advance), let the caller fall back to the average path.
        if all(w == 0.0 for _piece, _adv, w in segments) and fallback_advance > 0:
            return None
        return segments

    def _decode_code_to_unicode(
        self, code_bytes: bytes, code: int, font: PDFont | None
    ) -> str:
        """Decode a single character code to its Unicode piece.

        Resolution order matches :meth:`_decode_show_text`: ``/ToUnicode``
        CMap first, then the typed font's own ``to_unicode`` / simple-font
        decode, then a Latin-1 fallback. Returns ``""`` for a code that
        resolves to nothing (a non-spacing/absent glyph still carries its
        advance via :meth:`_glyph_segments`).
        """
        if self._active_cmap is not None:
            piece = self._active_cmap.to_unicode(code)
            if piece is None and font is not None:
                try:
                    piece = font.to_unicode(code)
                except Exception:  # noqa: BLE001 — defensive
                    piece = None
            return piece if piece is not None else ""
        if font is not None:
            try:
                piece = font.to_unicode(code)
                if piece is not None:
                    return piece
            except Exception:  # noqa: BLE001 — defensive
                pass
            from pypdfbox.pdmodel.font import PDSimpleFont  # noqa: PLC0415

            if isinstance(font, PDSimpleFont):
                try:
                    return font.decode(code_bytes)
                except Exception:  # noqa: BLE001 — defensive
                    pass
        return code_bytes.decode("latin-1", errors="replace")

    @staticmethod
    def _is_vertical_font(font: PDFont | None) -> bool:
        """``True`` when ``font`` paints glyphs in vertical writing mode
        (WMode 1).

        Mirrors upstream ``PDFont.isVertical`` — only composite (Type 0)
        fonts can be vertical, and only when their ``/Encoding`` CMap
        declares ``/WMode 1`` (e.g. ``/Identity-V``). Defensive: a font
        without an ``is_vertical`` predicate (every simple font) is treated
        as horizontal.
        """
        if font is None:
            return False
        is_vertical = getattr(font, "is_vertical", None)
        if not callable(is_vertical):
            return False
        try:
            return bool(is_vertical())
        except Exception:  # noqa: BLE001 — defensive: malformed CMap
            return False

    def _emit_vertical(
        self,
        raw_bytes: bytes,
        text: str,
        state: _TextState,
        positions: list[TextPosition],
        font: PDFont,
        resolved_font_name: str | None,
    ) -> None:
        """Per-glyph emission for a vertical (WMode 1) Type0 font.

        Ports upstream ``PDFStreamEngine.showText`` (PDFStreamEngine.java:
        430-470) vertical branch: each character code is read off
        ``raw_bytes`` via the font's ``read_code``, its origin is offset by
        the font's *position vector* (``font.get_position_vector(code)`` — in
        em, already negated per PDF 32000-1 §9.7.3) scaled by the font size,
        and the text cursor then advances DOWN the column by the *vertical
        displacement* ``ty = w1y·fontSize + Tc + Tw`` (where
        ``w1y = font.get_displacement(code)[1]`` is the negative ``/W2`` /
        ``/DW2`` advance in em). One :class:`TextPosition` is emitted per
        glyph, so the line-grouping heuristic (each glyph on a successive
        baseline, vertically disjoint) breaks a line after every glyph —
        reproducing Apache PDFBox's one-glyph-per-line vertical reading order
        (top-to-bottom within a column; the comparator orders columns
        right-to-left when ``sort_by_position`` is on, see
        :meth:`_compare_reading_order_vertical`).

        The text cursor lives in the text matrix's translation slots, so the
        text-space ``(0, ty)`` and position-vector deltas are carried through
        the text-matrix scale/shear ``(a, b, c, d)`` before they move
        ``text_x`` / ``text_y`` — matching the horizontal path's
        ``run_width × (tm_a, tm_b)`` cursor carry. Each glyph's device-space
        origin is the composed ``textMatrix × CTM`` translation.
        """
        font_size = state.font_size
        char_spacing = state.char_spacing
        word_spacing = state.word_spacing
        # Effective font size / glyph height / direction are matrix-scaled the
        # same way the horizontal path does (the run's scale comes from the
        # text-rendering matrix, independent of the per-glyph translation).
        trm = self._text_rendering_matrix(state)
        y_scale = trm.get_scaling_factor_y()
        x_scale = trm.get_scaling_factor_x()
        effective_font_size = font_size * y_scale
        font_size_in_pt = font_size * x_scale
        font_height_fraction = self._active_font_height
        run_height = (
            0.0 if font_height_fraction is None
            else font_height_fraction * effective_font_size
        )
        text_dir = self._text_dir(trm)
        # ``/ActualText`` substitution still applies per show-text run: inside
        # an ``/ActualText`` span the whole replacement string is emitted once
        # (at the span's first glyph), and every later glyph's text is
        # suppressed (the cursor still advances). ``actual_text`` is the
        # replacement for the first run / ``None`` for a suppressed later run,
        # and ``None`` (with ``has_actual_text`` False) when no span is active —
        # the latter is the common case where each glyph emits its own piece.
        has_actual_text = self._actual_text is not None
        actual_text = self._actual_text_for_run(text) if has_actual_text else None

        offset = 0
        n = len(raw_bytes)
        try:
            read_code = font.read_code
        except AttributeError:
            read_code = None
        emitted_any = False
        while offset < n:
            if read_code is None:
                break
            try:
                code, consumed = read_code(raw_bytes, offset)
            except Exception:  # noqa: BLE001 — defensive: malformed font / bytes
                break
            if consumed <= 0:
                break
            piece = self._decode_code_to_unicode(
                raw_bytes[offset : offset + consumed], code, font
            )
            offset += consumed
            # Position vector (em) — offsets the glyph origin so the vertical
            # baseline lands where the ``/W2`` / ``/DW2`` ``v`` component
            # places it (PDF 32000-1 §9.7.4.3). ``(0, 0)`` for fonts without
            # ``/W2``.
            try:
                v_x, v_y = font.get_position_vector(code)
            except Exception:  # noqa: BLE001 — defensive
                v_x, v_y = 0.0, 0.0
            # Vertical displacement (em); ``w1y`` is negative (advance down).
            try:
                _w0, w1y = font.get_displacement(code)
            except Exception:  # noqa: BLE001 — defensive
                w1y = -1.0
            # Glyph origin in text space = cursor + positionVector·fontSize,
            # carried through the text-matrix scale/shear into the
            # translation slots.
            glyph_tx = v_x * font_size
            glyph_ty = v_y * font_size
            origin_x = (
                state.text_x + glyph_tx * state.tm_a + glyph_ty * state.tm_c
            )
            origin_y = (
                state.text_y + glyph_tx * state.tm_b + glyph_ty * state.tm_d
            )
            # Under an ``/ActualText`` span the replacement is emitted once at
            # the first glyph (``actual_text``); later glyphs in the span carry
            # no text. Without a span each glyph emits its own decoded piece.
            if has_actual_text:
                glyph_text = actual_text or ""
                actual_text = ""  # emit the span replacement only once
            else:
                glyph_text = piece
            if glyph_text:
                origin = self._origin_matrix(state, origin_x, origin_y)
                positions.append(
                    TextPosition(
                        text=glyph_text,
                        x=origin.get_translate_x(),
                        y=origin.get_translate_y(),
                        font_size=effective_font_size,
                        font_size_in_pt=font_size_in_pt,
                        font_name=state.font_name,
                        font=font,
                        resolved_font_name=resolved_font_name,
                        width=0.0,
                        width_of_space=0.0,
                        char_spacing=char_spacing,
                        word_spacing=word_spacing,
                        dir=text_dir,
                        height=run_height,
                        text_matrix=[
                            state.tm_a,
                            state.tm_b,
                            state.tm_c,
                            state.tm_d,
                            origin_x,
                            origin_y,
                        ],
                    )
                )
                emitted_any = True
            # Advance the cursor down the column by the vertical displacement
            # ``ty = w1y·fontSize + Tc (+ Tw on single-byte code 32)``.
            ty = w1y * font_size + char_spacing
            if consumed == 1 and code == 32:
                ty += word_spacing
            state.text_x += ty * state.tm_c
            state.text_y += ty * state.tm_d
        # When the font could not read any code (defensive), fall back to one
        # collapsed run at the cursor so no text is silently dropped.
        if not emitted_any:
            fallback_text = actual_text if has_actual_text else text
            if fallback_text:
                origin = self._origin_matrix(state, state.text_x, state.text_y)
                positions.append(
                    TextPosition(
                        text=fallback_text,
                        x=origin.get_translate_x(),
                        y=origin.get_translate_y(),
                        font_size=effective_font_size,
                        font_size_in_pt=font_size_in_pt,
                        font_name=state.font_name,
                        font=font,
                        resolved_font_name=resolved_font_name,
                        width=0.0,
                        width_of_space=0.0,
                        char_spacing=char_spacing,
                        word_spacing=word_spacing,
                        dir=text_dir,
                        height=run_height,
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

    def _emit(
        self,
        s: COSString,
        state: _TextState,
        positions: list[TextPosition],
    ) -> None:
        """Emit the positions for one show-text string.

        Thin wrapper over :meth:`_emit_run` that tags every position the
        run produced while an ``/ActualText`` span was open. Upstream's
        ``PDFTextStripper.processTextPosition`` bypasses the
        duplicate-overlapping-text filter whenever ``actualText != null``
        (the glyph is always shown and never recorded in
        ``characterListMapping``); the lite pipeline dedups after the
        page walk, so the span membership must travel with the position.
        """
        mark = len(positions)
        in_actual_text = self._actual_text is not None
        self._emit_run(s, state, positions)
        if in_actual_text:
            for pos in positions[mark:]:
                pos.from_actual_text = True

    def _emit_run(
        self,
        s: COSString,
        state: _TextState,
        positions: list[TextPosition],
    ) -> None:
        raw_bytes = s.get_bytes()
        text = self._decode_show_text(raw_bytes)
        if not text:
            return
        font = self._active_font
        resolved_font_name = font.get_name() if font is not None else None
        # Vertical writing mode (WMode 1): when the active font's encoding
        # CMap declares vertical writing, each glyph advances DOWN the page
        # by its vertical displacement vector rather than along the text
        # matrix's horizontal axis. Upstream ``PDFStreamEngine.showText``
        # (PDFStreamEngine.java:430-470) offsets each glyph origin by the
        # font's position vector and steps the text cursor by
        # ``(0, w1y·fontSize + Tc + Tw)`` per glyph, so consecutive glyphs
        # land on successive baselines and the line-grouping heuristic emits
        # one glyph per line (top-to-bottom within a column). Delegate to the
        # per-glyph vertical emitter, which never goes through the
        # horizontal run-width / word-gap machinery below.
        if self._is_vertical_font(font):
            self._emit_vertical(raw_bytes, text, state, positions, font, resolved_font_name)
            return
        per_char = self._active_avg_advance
        if per_char is None:
            per_char = state.font_size * 0.5
        width_of_space = self._compute_width_of_space(
            font, state.font_size, fallback=per_char
        )
        # Real per-glyph advances from the font's /Widths (wave 1408 per-code
        # lookups), decoded code-by-code via the font's encoding. ``None``
        # falls back to the average-advance path below for malformed fonts.
        segments = self._glyph_segments(raw_bytes, state, font, per_char)
        # Resolve the device-space origin and effective glyph size from
        # the full text-rendering matrix. ``font_size`` (the ``Tf``
        # operand) is scaled by the matrix's Y scaling so the line-break
        # and word-gap heuristics operate on the rendered glyph size, and
        # the run width (computed in text space) is scaled by the X
        # scaling so it lands in the same device-space units as the
        # origin.
        trm = self._text_rendering_matrix(state)
        # The device-space origin per (sub-)run is computed from the run's own
        # cursor via ``_origin_matrix`` below; here we only need the matrix's
        # scaling factors and rotation for the effective font size and dir.
        y_scale = trm.get_scaling_factor_y()
        x_scale = trm.get_scaling_factor_x()
        effective_font_size = state.font_size * y_scale
        # Device-space glyph height — upstream ``maxHeight``: the font's
        # text-space height fraction (``_compute_font_height``) times the
        # font size times the matrix Y scale. Feeds the line-grouping
        # vertical-overlap test (see ``_emit_group``). ``None`` (no Tf yet /
        # unresolved font) leaves it 0.0 so the height accessors fall back
        # to ``font_size``.
        font_height_fraction = self._active_font_height
        if font_height_fraction is None:
            run_height = 0.0
        else:
            run_height = font_height_fraction * effective_font_size
        text_dir = self._text_dir(trm)
        # ``/ActualText`` substitution (PDF §14.9.4): inside a marked-content
        # span carrying ``/ActualText``, the glyph-derived text is replaced
        # and the ``/ActualText`` string is emitted *once* (at the origin of
        # the span's first show-text run), mirroring Apache PDFBox's
        # ``PDFTextStripper``. Every run still advances the cursor by its
        # glyph width so positions after ``EMC`` line up.
        # ``_actual_text_for_run`` returns the replacement string for the
        # first run, ``None`` for suppressed later runs, and the unchanged
        # ``text`` when no ``/ActualText`` is active.
        emit_text = self._actual_text_for_run(text)
        # ``Tz`` (horizontal text scaling, stored as ``Tz/100``) scales the
        # horizontal glyph displacement in text space (PDF 32000-1 §9.3.4),
        # so the advance the cursor takes — and the run width / space width
        # the word-gap heuristic measures — are condensed (<1) or expanded
        # (>1) by it. The rendered space width scales too, so an engine that
        # honours ``Tz`` segments words differently from one that ignores it.
        th = getattr(state, "horizontal_scaling", 1.0)
        if segments is not None:
            # Real per-glyph advances (text space), scaled by Th. The run
            # width is their sum — replacing the ``len(text) × average``
            # estimate so ``prev_right`` and the average-char-width prong of
            # the word-break threshold use true metrics. ``glyph_width`` is
            # the bare glyph advance (no Tc/Tw), used to size each glyph's
            # right edge for the intra-run word-break test.
            glyph_text = [piece for piece, _adv, _w in segments]
            glyph_adv = [adv * th for _piece, adv, _w in segments]
            glyph_width = [w * th for _piece, _adv, w in segments]
            run_width = sum(glyph_adv)
        else:
            glyph_text = list(text)
            glyph_adv = [per_char * th] * len(text)
            glyph_width = list(glyph_adv)
            run_width = len(text) * per_char * th
        width_of_space = width_of_space * th

        # Page-rotation per-glyph emission. On a ``/Rotate 90``/``270`` page the
        # default grouping consumes the page-rotation-adjusted ``getX``/``getY``
        # (``_apply_page_rotation``), in which a horizontal run advances along
        # the grouping's *line* axis — so each glyph of the run lands on its own
        # rotated line, exactly the way upstream's per-glyph ``showGlyph``
        # (LegacyPDFStreamEngine.java:161) feeds one ``TextPosition`` per glyph
        # into ``writePage``. The lite stripper otherwise emits one position per
        # show-text run; to reproduce Java's rotated-row fragmentation faithfully
        # we emit per glyph here. Only the plain (non-``/ActualText``,
        # non-ignore-space) path takes this branch — those rarer combinations
        # fall through to the run path below.
        if (
            self._page_rotation in (90, 270)
            and not self._ignore_content_stream_space_glyphs
            and emit_text is not None
            and emit_text == text
        ):
            self._emit_per_glyph(
                state,
                positions,
                font,
                resolved_font_name,
                glyph_text,
                glyph_adv,
                glyph_width,
                effective_font_size,
                x_scale,
                width_of_space,
                run_height,
                text_dir,
            )
            state.text_x += run_width * state.tm_a
            state.text_y += run_width * state.tm_b
            return

        if self._ignore_content_stream_space_glyphs:
            if emit_text is not None:
                self._emit_ignoring_space_glyphs(
                    emit_text,
                    state,
                    positions,
                    font,
                    resolved_font_name,
                    per_char * th,
                    width_of_space,
                )
                return
            # Suppressed run inside an ActualText span: keep the cursor
            # advance (carried below) but emit no positions.
            state.text_x += run_width * state.tm_a
            state.text_y += run_width * state.tm_b
            return

        if emit_text is not None:
            # Subdivide the run on any *intra-run* glyph gap wide enough to
            # be a word break — matching upstream's per-glyph emission, which
            # turns a large ``Tc`` (or a sparse positioning advance) inside a
            # single ``Tj`` string into a word separator. ``emit_text`` is the
            # decoded run text (or the ``/ActualText`` replacement, which is
            # never subdivided — it is a single semantic unit).
            sub_runs = self._split_run_on_word_gaps(
                emit_text, text, glyph_text, glyph_adv, glyph_width, width_of_space
            )
            for sub_text, start_offset, _sub_advance, sub_width in sub_runs:
                sub_text_x = state.text_x + start_offset * state.tm_a
                sub_text_y = state.text_y + start_offset * state.tm_b
                sub_trm = self._origin_matrix(state, sub_text_x, sub_text_y)
                positions.append(
                    TextPosition(
                        text=sub_text,
                        x=sub_trm.get_translate_x(),
                        y=sub_trm.get_translate_y(),
                        font_size=effective_font_size,
                        font_size_in_pt=state.font_size * x_scale,
                        font_name=state.font_name,
                        font=font,
                        resolved_font_name=resolved_font_name,
                        width=sub_width * x_scale,
                        width_of_space=width_of_space * x_scale,
                        char_spacing=state.char_spacing,
                        word_spacing=state.word_spacing,
                        dir=text_dir,
                        height=run_height,
                        text_matrix=[
                            state.tm_a,
                            state.tm_b,
                            state.tm_c,
                            state.tm_d,
                            sub_text_x,
                            sub_text_y,
                        ],
                    )
                )
            # When no subdivision occurred, the single emitted run carries the
            # full glyph advance list so consumers (PDFTextStripperByArea) can
            # route per glyph with true offsets.
            if len(sub_runs) == 1 and positions:
                positions[-1].individual_widths = [a * x_scale for a in glyph_adv]
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

    def _emit_per_glyph(
        self,
        state: _TextState,
        positions: list[TextPosition],
        font: PDFont | None,
        resolved_font_name: str | None,
        glyph_text: list[str],
        glyph_adv: list[float],
        glyph_width: list[float],
        effective_font_size: float,
        x_scale: float,
        width_of_space: float,
        run_height: float,
        text_dir: float,
    ) -> None:
        """Emit one :class:`TextPosition` per glyph of a show-text run.

        Used on rotated (``/Rotate 90``/``270``) pages so the line/word
        grouping fragments the rotated rows the way upstream's per-glyph
        ``showGlyph`` does (LegacyPDFStreamEngine.java:161 →
        ``processTextPosition`` per glyph). Each glyph's origin is the run
        cursor stepped by the cumulative text-space advance of the preceding
        glyphs, carried through the text matrix's scale/shear into the
        translation slots — identical to how the run path advances
        ``text_x``/``text_y`` (``translate(advance, 0) × Tm``). Widths are the
        raw (pre-rotation) glyph advances; ``_apply_page_rotation`` then folds
        each glyph into the device frame.
        """
        offset = 0.0
        for piece, adv, gw in zip(glyph_text, glyph_adv, glyph_width, strict=False):
            if piece:
                glyph_x = state.text_x + offset * state.tm_a
                glyph_y = state.text_y + offset * state.tm_b
                origin = self._origin_matrix(state, glyph_x, glyph_y)
                positions.append(
                    TextPosition(
                        text=piece,
                        x=origin.get_translate_x(),
                        y=origin.get_translate_y(),
                        font_size=effective_font_size,
                        font_size_in_pt=state.font_size * x_scale,
                        font_name=state.font_name,
                        font=font,
                        resolved_font_name=resolved_font_name,
                        width=gw * x_scale,
                        width_of_space=width_of_space * x_scale,
                        char_spacing=state.char_spacing,
                        word_spacing=state.word_spacing,
                        dir=text_dir,
                        height=run_height,
                        individual_widths=[gw * x_scale],
                        text_matrix=[
                            state.tm_a,
                            state.tm_b,
                            state.tm_c,
                            state.tm_d,
                            glyph_x,
                            glyph_y,
                        ],
                    )
                )
            offset += adv

    @staticmethod
    def _origin_matrix(state: _TextState, text_x: float, text_y: float) -> Matrix:
        """Text-rendering matrix for a glyph origin at ``(text_x, text_y)``.

        Like :meth:`_text_rendering_matrix` but for an explicit translation
        (a subdivided sub-run starts partway through the parent run). Folds
        text rise (``Ts``) in the same parameter-matrix-first way.
        """
        tm = Matrix(state.tm_a, state.tm_b, state.tm_c, state.tm_d, text_x, text_y)
        rise = getattr(state, "text_rise", 0.0)
        if rise:
            tm = Matrix(1.0, 0.0, 0.0, 1.0, 0.0, rise).multiply(tm)
        return tm.multiply(state.ctm)

    def _split_run_on_word_gaps(
        self,
        emit_text: str,
        run_text: str,
        glyph_text: list[str],
        glyph_adv: list[float],
        glyph_width: list[float],
        width_of_space: float,
    ) -> list[tuple[str, float, float, float]]:
        """Subdivide a show-text run into word-separated sub-runs.

        Mirrors upstream ``PDFStreamEngine``/``PDFTextStripper`` emitting one
        ``TextPosition`` per glyph and inserting a word separator whenever the
        gap between one glyph's right edge and the next glyph's origin exceeds
        the space-width-relative threshold (the intra-run analogue of
        :meth:`_is_word_break`). A large ``Tc`` (or a sparse positioning
        advance) inside a single ``Tj`` string therefore segments into words
        exactly the way Java does — closing the documented
        per-glyph-granularity / intra-run word-break carve-out.

        Returns a list of ``(sub_text, start_offset, sub_advance,
        sub_width)`` tuples in text-space units (already scaled by ``Th``):
        ``start_offset`` is the cumulative advance to the sub-run's first
        glyph, ``sub_advance`` the sum of its glyphs' advances (so the offsets
        tile the parent run's full advance and drive the cursor), and
        ``sub_width`` the sum of its glyphs' *bare* widths (excluding the
        trailing inter-glyph ``Tc``/``Tw``) — which is what the emitted
        ``TextPosition.width`` must carry so the inter-position gap that the
        word-break heuristic measures reflects the real ``Tc`` spacing, the
        way Java's per-glyph widths do. A single-element result means no
        break fired.

        Subdivision is suppressed when the run carries an ``/ActualText``
        replacement (``emit_text != run_text``) — that string is one semantic
        unit and must not be split mid-replacement.
        """
        # No metrics, single glyph, an ActualText replacement, or a decode
        # mismatch (the per-code join disagrees with the run text — e.g. a
        # ligature or NFKC-normalised run) → emit one run unchanged so the
        # subdivided text never diverges from the non-subdivided path.
        n = len(glyph_adv)
        # A run/segment's visual right edge (Java ``endX``) is the last
        # glyph's origin + its *bare* width — i.e. the sum of advances minus
        # the trailing inter-glyph spacing carried in the last glyph's
        # advance. This is the width the inter-run word-break heuristic must
        # measure against.
        full_width = (
            sum(glyph_adv) - (glyph_adv[-1] - glyph_width[-1]) if glyph_adv else 0.0
        )
        single = [(emit_text, 0.0, sum(glyph_adv), full_width)]
        if (
            n <= 1
            or emit_text != run_text
            or not glyph_text
            or "".join(glyph_text) != run_text
        ):
            return single
        # Threshold mirrors ``_is_word_break``: the smaller of the
        # space-width and average-char-width prongs.
        delta_space = (
            width_of_space * self._spacing_tolerance
            if width_of_space > 0.0
            else math.inf
        )
        positive_widths = [w for w in glyph_width if w > 0.0]
        if positive_widths:
            avg_char_width = sum(positive_widths) / len(positive_widths)
            delta_char = avg_char_width * self._average_char_tolerance
        else:
            delta_char = math.inf
        threshold = min(delta_space, delta_char)
        if not math.isfinite(threshold):
            return single
        sub_runs: list[tuple[str, float, float, float]] = []
        seg_start = 0.0  # cumulative advance to the start of the segment
        seg_text: list[str] = []
        seg_adv = 0.0
        for i in range(n):
            seg_text.append(glyph_text[i])
            seg_adv += glyph_adv[i]
            # Gap after this glyph = advance beyond the bare glyph width
            # (i.e. Tc, plus Tw on a space). Compare to the threshold.
            gap = glyph_adv[i] - glyph_width[i]
            # The segment ends here (at the last glyph or before a break);
            # its visual width is the advance up to here minus this glyph's
            # own trailing inter-glyph spacing (Java ``endX``).
            seg_width = seg_adv - gap
            if i == n - 1:
                sub_runs.append(("".join(seg_text), seg_start, seg_adv, seg_width))
            elif gap > threshold:
                sub_runs.append(("".join(seg_text), seg_start, seg_adv, seg_width))
                seg_start += seg_adv
                seg_text = []
                seg_adv = 0.0
        # Drop any empty segment (defensive).
        return [s for s in sub_runs if s[0] != ""] or single

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
        text_dir = self._text_dir(trm_scale)
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
            # Fold text rise (``Ts``) in the way the main ``_emit`` path does
            # — as the f-translation of the font-parameter matrix applied
            # before the text matrix (``[1, 0, 0, 1, 0, rise] × Tm × ctm``).
            rise = getattr(state, "text_rise", 0.0)
            if rise:
                tm = Matrix(1.0, 0.0, 0.0, 1.0, 0.0, rise).multiply(tm)
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
                    font_size_in_pt=state.font_size * x_scale,
                    font_name=state.font_name,
                    font=font,
                    resolved_font_name=resolved_font_name,
                    width=len(chunk_text) * per_char * x_scale,
                    width_of_space=width_of_space * x_scale,
                    char_spacing=state.char_spacing,
                    word_spacing=state.word_spacing,
                    dir=text_dir,
                    height=(
                        0.0
                        if self._active_font_height is None
                        else self._active_font_height * effective_font_size
                    ),
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
                # in text space, so (like the show-text advance) it is
                # scaled horizontally by ``Tz/100`` (PDF 32000-1 §9.3.4)
                # and then carried through the text-matrix scale/shear
                # before it moves the translation-space cursor. Honouring
                # ``Tz`` here makes a ``TJ`` jump condense / expand with the
                # surrounding text, so word segmentation matches an engine
                # that scales the gap by ``Tz``.
                adj = (
                    entry.float_value()
                    * state.font_size
                    / 1000.0
                    * getattr(state, "horizontal_scaling", 1.0)
                )
                state.text_x -= adj * state.tm_a
                state.text_y -= adj * state.tm_b

    # ---------- /ToUnicode CMap helpers ----------

    def _current_resources(self) -> PDResources | None:
        """Resources in effect for font / property-list lookups.

        While recursing into a form XObject (``Do``) the form's own
        ``/Resources`` override the host page's, mirroring upstream's
        ``PDFStreamEngine.showForm`` pushing the form resources for the
        duration of the form body. Otherwise the active page's resources.
        """
        if self._active_resources is not None:
            return self._active_resources
        if self._active_page is None:
            return None
        return self._active_page.get_resources()

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
            resources = self._current_resources()
            if resources is None:
                self._cmap_cache[font_resource_name] = None
                return None
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
            return self._decode_text_via_cmap(
                text_bytes, self._active_cmap, self._active_font
            )
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

            resources = self._current_resources()
            if resources is None:
                self._font_cache[font_resource_name] = None
                return None
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
        """Convert a font's average glyph width to a user-space
        per-character advance at the given ``font_size``. Returns ``None``
        when the font has no usable ``/Widths`` array — callers fall back to
        the legacy 0.5-em-per-char estimate.

        The glyph-space → user-space scale is ``1/1000`` for ordinary simple
        fonts but the font's ``/FontMatrix`` x-scale for a Type 3 font (see
        below)."""
        if font is None or font_size <= 0:
            return None
        # Local import to avoid pulling pdmodel.font into module-load
        # time (cycle).
        from pypdfbox.pdmodel.font import PDSimpleFont  # noqa: PLC0415

        if not isinstance(font, PDSimpleFont):
            return None
        avg_width = font.get_average_font_width()
        if avg_width <= 0:
            return None
        # ``/Widths`` for most simple fonts are glyph-space thousandths of an
        # em (the implicit ``[0.001 0 0 0.001 0 0]`` FontMatrix), so the
        # user-space advance is ``width / 1000 × fontSize``. A Type 3 font is
        # the exception: its ``/Widths`` are in the glyph space defined by an
        # explicit ``/FontMatrix`` whose x-scale is rarely 0.001, so the
        # advance is ``width × fontMatrix[a] × fontSize`` — mirroring upstream
        # ``PDType3Font.getDisplacement`` (``fontMatrix.transform(width,0).x``)
        # which the rendering / text engine uses to advance the cursor. Using
        # the fixed 1/1000 here would mis-scale every Type 3 advance by the
        # ratio of the real FontMatrix x-scale to 0.001.
        from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font  # noqa: PLC0415

        if isinstance(font, PDType3Font):
            x_scale = font.get_font_matrix()[0]
            return avg_width * x_scale * font_size
        return avg_width / 1000.0 * font_size

    def _compute_font_height(self, font: PDFont | None) -> float:
        """Return the font's glyph height in text-space units (a fraction of
        the em), mirroring upstream ``LegacyPDFStreamEngine.computeFontHeight``
        (LegacyPDFStreamEngine.java:324-368).

        Upstream takes half the font bounding box height, then prefers the
        descriptor's ``/CapHeight`` (or ``(ascent − descent) / 2``) when the
        bbox is implausibly tall, and finally scales glyph space → text space
        (``/1000`` for ordinary fonts, the ``/FontMatrix`` for Type 3). The
        result feeds the line-grouping vertical-overlap test in
        :meth:`_emit_group`; the caller multiplies it by ``font_size`` (and
        the text-rendering matrix's Y scale) to get the device-space glyph
        height. The per-font value is cached for the active page exactly as
        upstream caches it in its ``fontHeightMap``.

        Returns ``0.5`` (half the em) when the font, its bounding box, and its
        descriptor are all unavailable — a neutral proxy that keeps the
        overlap test working for metric-less fonts without the previous
        full-em (``1.0``) over-grouping.
        """
        if font is None:
            return 0.5
        cached = self._font_height_cache.get(id(font))
        if cached is not None:
            return cached
        glyph_height = 0.0
        try:
            bbox = font.get_bounding_box()
        except Exception:  # noqa: BLE001 — defensive: malformed font program
            bbox = None
        if bbox is not None:
            lower_left_y = bbox.get_lower_left_y()
            if lower_left_y < -32768:
                # PDFBOX-2158 / PDFBOX-3130 over-/under-flowed lower-left Y.
                bbox_height = bbox.get_upper_right_y() - (-(lower_left_y + 65536))
            else:
                bbox_height = bbox.get_height()
            glyph_height = bbox_height / 2.0
        try:
            descriptor = font.get_font_descriptor()
        except Exception:  # noqa: BLE001 — defensive
            descriptor = None
        if descriptor is not None:
            cap_height = descriptor.get_cap_height()
            if cap_height != 0 and (cap_height < glyph_height or glyph_height == 0):
                glyph_height = cap_height
            ascent = descriptor.get_ascent()
            descent = descriptor.get_descent()
            if (
                cap_height > ascent
                and ascent > 0
                and descent < 0
                and ((ascent - descent) / 2.0 < glyph_height or glyph_height == 0)
            ):
                glyph_height = (ascent - descent) / 2.0
        # Glyph space → text space.
        from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font  # noqa: PLC0415

        if isinstance(font, PDType3Font):
            try:
                height = font.get_font_matrix()[3] * glyph_height
            except Exception:  # noqa: BLE001 — defensive
                height = glyph_height / 1000.0
        else:
            height = glyph_height / 1000.0
        if height <= 0:
            # No usable metrics — fall back to half the em (a neutral proxy
            # that avoids the full-em over-grouping the line-overlap test had
            # before real heights were threaded through).
            height = 0.5
        self._font_height_cache[id(font)] = height
        return height

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
    def _decode_text_via_cmap(
        text_bytes: bytes, cmap: CMap, font: PDFont | None = None
    ) -> str:
        """Walk ``text_bytes`` consuming codes whose width is governed by
        the CMap's codespace ranges, look each up via ``cmap.to_unicode``,
        and concatenate.

        When the ``/ToUnicode`` CMap has no mapping for a code, resolve it
        through ``font.to_unicode(code)`` — this preserves upstream's
        ``PDFont.toUnicode`` fallback chain (ToUnicode → ``/Encoding`` glyph
        name → Adobe Glyph List). A simple font whose ``/ToUnicode`` CMap
        covers only some codes (a common subsetting/ligature pattern) would
        otherwise lose every uncovered glyph, diverging from Apache PDFBox's
        ``PDFTextStripper`` which emits ``font.toUnicode(code)`` per glyph.
        Only when the font fallback also yields nothing is the code dropped.

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
            if piece is None and font is not None:
                try:
                    piece = font.to_unicode(code)
                except Exception:  # noqa: BLE001 — defensive: malformed font
                    piece = None
            if piece is not None:
                out.append(piece)
        return "".join(out)

    # ---------- formatting ----------

    def _empty_article_wrap(self) -> str:
        """Text emitted for a page that yields no glyphs.

        Upstream ``PDFTextStripper.writePage`` still iterates
        ``charactersByArticle`` for a glyph-free page (a page with no beads
        contributes a single empty article slot) and brackets each slot in
        ``startArticle()`` / ``endArticle()`` regardless of whether it holds
        any text (PDFTextStripper.java:497-560). The page-body
        ``writeParagraphStart`` / ``writeParagraphEnd`` are gated on at least
        one written character (the ``startOfArticle`` / first-glyph path), so
        an empty article emits *only* the article markers, never paragraph
        ones. With the default empty markers this is invisible; under
        ``add_more_formatting`` (article markers promoted to the line
        separator) it supplies the per-page newlines the Java oracle emits for
        a whitespace-only page. Returning ``""`` here — as the lite stripper
        did before wave 1542 — dropped those markers, so a glyph-free page
        diverged from Java whenever any article marker was non-empty.
        """
        if not self._article_start and not self._article_end:
            return ""
        return self._article_start + self._article_end

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
        upstream default), a position whose text was already painted on
        the page at (nearly) the same origin — within a half-open window
        of ``width / len(text) / 3`` on both axes, upstream
        ``processTextPosition``'s tolerance — is considered the same
        glyph painted twice (a common trick for fake bold) and the
        duplicate is dropped before formatting (see
        :meth:`_drop_overlapping_duplicates`).

        When ``should_separate_by_beads`` is enabled and the active page
        carries thread beads, positions are bucketed into upstream's
        per-article ``charactersByArticle`` slots (``2*N + 1`` for ``N``
        beads; see :meth:`_partition_by_beads`) and the slots are emitted in
        index order, matching upstream's ``setShouldSeparateByBeads(true)``
        semantics. The running line state carries across the slot boundaries
        the way ``writePage`` declares it outside the article loop.
        """
        if not positions:
            return self._empty_article_wrap()
        # Drop glyphs the subclass declines via ``should_skip_glyph``
        # before any sorting/grouping — keeps the position lists handed
        # to ``write_string`` in sync with what subclasses would have
        # seen via ``processTextPosition`` upstream.
        positions = [p for p in positions if not self.should_skip_glyph(p)]
        if not positions:
            return self._empty_article_wrap()
        if self._suppress_duplicate_overlapping_text:
            positions = self._drop_overlapping_duplicates(positions)
        # Upstream applies the comparator only when ``sortByPosition`` is
        # set — even when bead-separation is on, the in-bead ordering
        # follows content-stream order unless explicit sort is requested.
        # Lite mode follows the same gating.
        if self._sort_by_position:
            # Upstream's ``TextPositionComparator`` keys on ``getDir()``
            # first, so glyphs are grouped by text direction (0/90/180/270)
            # before any positional ordering — a page that mixes runs
            # rotated by different right angles emits each direction's runs
            # contiguously, in ascending-direction order, rather than
            # interleaving them by raw device coordinate. Within a single
            # direction the positional sort below reproduces the per-group
            # reading order.
            if self._flip_axes:
                # Rotated frame: sort by ascending x (top-to-bottom in
                # the rotated reading order) then ascending y (left-to-
                # right within a column). Mirrors upstream's flipped
                # comparator.
                positions = sorted(positions, key=lambda p: (p.dir % 360.0, p.x, p.y))
            else:
                positions = sorted(
                    positions, key=cmp_to_key(self._compare_reading_order)
                )

        # Bead-separation: bucket positions into upstream's per-article
        # ``charactersByArticle`` slots (``2*N + 1`` for ``N`` beads), then
        # emit one slot at a time in index order — the gap slots interleave
        # between the bead columns, reproducing the reading flow. Text outside
        # every bead lands in the first gap slot it is left-of / above (see
        # :meth:`_partition_by_beads`), not a single trailing residual.
        groups: list[list[TextPosition]] = []
        if self._should_separate_by_beads and self._active_page is not None:
            groups = self._partition_by_beads(positions)
        if not groups:
            groups = [positions]
        # Mirror upstream ``processPage``: ``charactersByArticle`` *is* the
        # per-article (bead-bucket) structure that ``writePage`` iterates, not
        # the flat pre-partition position list. ``process_page`` seeds it with
        # a provisional single group before calling here; overwrite it with the
        # post-filter, post-sort, partitioned buckets so
        # ``get_characters_by_article`` and the upstream-signature
        # ``write_page`` both see the same article slots upstream exposes. (When
        # bead separation is off or the page has no usable beads this is a
        # single all-positions group, matching the prior behaviour.)
        self._characters_by_article = groups

        chunks: list[str] = []

        def _sink(piece: str) -> None:
            chunks.append(piece)

        # Upstream wraps EACH article (bead bucket) in ``startArticle()`` /
        # ``endArticle()`` — i.e. ``article_start`` before and ``article_end``
        # after every group — with NO implicit line separator between
        # consecutive articles. Both markers default to "" (they only become a
        # line separator when ``add_more_formatting`` is enabled), so by
        # default adjacent bead buckets are concatenated directly. Emitting a
        # hardcoded line separator here would diverge from PDFBox, which only
        # inserts a break between articles when the producer asked for one via
        # the article separators.
        # Upstream ``writePage`` emits the page-body ``writeParagraphStart``
        # exactly once, on the first character of the first non-empty article
        # (the ``startOfPage`` flag, set false after the first glyph), and a
        # ``writeParagraphEnd`` after the last line of *each* article
        # (PDFTextStripper.java:700-724). ``_emit_group`` reproduces both: it
        # opens the page paragraph on its first written run when
        # ``open_page_paragraph`` is set, clearing the page-level flag so a
        # later article does not re-open it, and always closes the paragraph
        # after its final line. With the default empty paragraph markers these
        # emissions are invisible; under ``add_more_formatting`` (both promoted
        # to the line separator) they supply the trailing per-article and
        # leading per-page newlines the Java oracle emits.
        #
        # A subclass that overrides ``write_article_start`` (e.g.
        # ``PDFText2HTML``, which brackets each article's body with its own
        # ``<p>`` / ``</p>`` inside the article hooks) takes over paragraph
        # bracketing; for those the base ``_emit_group`` wrapping is
        # suppressed so the markers are not emitted twice. The plain base
        # stripper keeps the wrapping so its ``add_more_formatting`` cadence
        # matches the Java oracle.
        manages_own_paragraph = (
            type(self).write_article_start is not PDFTextStripper.write_article_start
        )
        open_page_paragraph = not manages_own_paragraph
        # Upstream's ``writePage`` declares the running line-extent /
        # previous-glyph state (``lastPosition``, ``maxYForLine``,
        # ``maxHeightForLine``, ``lastLineStartPosition``) *outside* the
        # ``for (List<TextPosition> textList : charactersByArticle)`` loop
        # (PDFTextStripper.java:497-503), so that state persists across
        # article boundaries: the first glyph of a new article is line-broken
        # against the *last* glyph of the previous article whenever their
        # vertical spans do not overlap. Only ``startOfArticle`` resets per
        # article. The lite emitter mirrors that by threading a shared carry
        # dict through each ``_emit_group`` call rather than re-seeding the
        # line state for every bead bucket. Without it, a glyph that fell
        # into a trailing residual slot (e.g. a final line below the last
        # bead) would be concatenated onto the previous article's last line
        # instead of starting its own.
        carry: dict[str, object] | None = {} if len(groups) > 1 else None
        for group in groups:
            if self._article_start:
                self.write_article_start(_sink)
            wrote = self._emit_group(
                group,
                _sink,
                open_page_paragraph,
                emit_paragraph_markers=not manages_own_paragraph,
                carry=carry,
            )
            if wrote:
                open_page_paragraph = False
            if self._article_end:
                self.write_article_end(_sink)
        return "".join(chunks)

    def _emit_group(
        self,
        positions: list[TextPosition],
        sink: Callable[[str], None],
        open_page_paragraph: bool = False,
        emit_paragraph_markers: bool = True,
        carry: dict[str, object] | None = None,
    ) -> bool:
        """Emit a single ordered list of positions. Splits out from
        ``_format_positions`` so the bead-bucket loop can reuse the same
        line/word/paragraph heuristics for each bucket independently.

        When ``emit_paragraph_markers`` is ``True`` the group reproduces
        upstream ``writePage``'s page-body paragraph bracketing: a
        ``write_paragraph_start`` before its first written run when
        ``open_page_paragraph`` is set (fired once per page, on the first
        glyph of the first non-empty article), and a ``write_paragraph_end``
        after its final line when it wrote at least one run (upstream's
        per-article ``writeParagraphEnd``, PDFTextStripper.java:700-724). A
        subclass that brackets paragraphs itself (e.g. ``PDFText2HTML`` via
        its overridden article hooks) passes ``False`` so the markers are not
        emitted twice. The mid-page paragraph-separation break is emitted in
        either case. Returns ``True`` when the group wrote at least one run,
        so the caller can clear its page-level paragraph-open flag.

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

        # Running line-extent accumulators mirroring upstream
        # ``writePage`` (PDFTextStripper.java:497-501). A position joins
        # the current line when its vertical glyph span overlaps the
        # *line's* accumulated span (``max_y_for_line`` / its height) —
        # not merely the immediately-previous glyph. This is what keeps a
        # wrapped row label's continuation (e.g. ``(as HCl)``) and its
        # value cells (``10 000 - -``, painted a few points higher on a
        # slightly different baseline) on one logical line in a
        # multi-column table, where the flat prev-only 0.5·fontSize test
        # split them. The accumulators reset on a line break and on a
        # horizontal jump larger than one space (a new column whose font
        # size may differ), matching upstream lines 681-687.
        #
        # Per-axis line-extent accumulator. Upstream tracks
        # ``maxYForLine = MAX(positionY)`` in its y-down *device* frame
        # (PDFTextStripper.java:689-692), i.e. the lowest (bottom-most)
        # baseline seen on the line, reset to ``-Float.MAX_VALUE``. Which
        # coordinate frame the lite stripper's stored ``pos.y`` lives in
        # depends on the path:
        #
        #   * upright, unrotated page (``not _flip_axes and
        #     _page_rotation == 0``): ``pos.y`` is the raw PDF user-space
        #     (y-up) baseline — a larger Y is *higher* on the page. The
        #     y-up mirror of "max device-Y" is therefore "**min user-Y**":
        #     the accumulator must track the lowest baseline as ``MIN`` and
        #     reset to ``+inf`` (update ``if position_y <= acc``). Keeping
        #     the literal ``MAX`` / ``-inf`` here is the long-standing sign
        #     mismatch that split a single visual line mixing very different
        #     glyph heights (a large-font run between two normal-font
        #     anchors) where Java merges them. ``_overlaps_line`` is already
        #     the correct y-up transform of upstream ``overlap`` *given* a
        #     MIN-user-Y accumulator (its two span clauses carry the matching
        #     heights — verified by substituting ``device_y = -user_y`` into
        #     upstream's ``overlap``), so only the accumulation direction was
        #     wrong.
        #
        #   * rotated page (``_page_rotation in (90, 180, 270)``):
        #     ``_apply_page_rotation`` has already rewritten ``pos.y`` into
        #     upstream's ``getY()`` device frame (see that method's lines
        #     866-878: the stored Y runs in the SAME direction as upstream's
        #     ``getY()`` precisely so this accumulation matches). There the
        #     literal ``MAX`` / ``-inf`` is upstream's verbatim behaviour and
        #     the 90/270 fragmentation pattern depends on it — flipping the
        #     sense would regress
        #     ``test_right_angle_rotation_byte_exact``.
        #
        #   * flip-axes (``set_should_flip_axes``): a lite-only manual X/Y
        #     transpose with no upstream counterpart; ``_overlaps_line`` is
        #     not consulted on that path (it uses ``_is_line_break``), so the
        #     accumulator is dead for line-breaking there — kept on the
        #     legacy ``MAX`` / ``-inf`` sense for stability (documented
        #     carve-out, see ``set_should_flip_axes`` DEFERRED entry).
        #
        # ``min_y_line_axis`` selects the upright-unrotated MIN-user-Y path.
        min_y_line_axis = not self._flip_axes and self._page_rotation == 0
        _MAX_Y_RESET = math.inf if min_y_line_axis else -math.inf
        _MAX_HEIGHT_RESET = -1.0
        # When a ``carry`` dict is supplied the running line state persists
        # across article (bead-bucket) boundaries — mirroring upstream's
        # ``writePage``, which declares this state outside the per-article
        # loop (PDFTextStripper.java:497-503). The first bucket seeds an
        # empty carry; later buckets resume from the previous bucket's final
        # glyph so an inter-article line break fires when their vertical
        # spans do not overlap. ``open_page_paragraph`` already guards the
        # once-per-page paragraph open, so resuming ``prev`` does not re-open
        # the page paragraph.
        max_y_for_line = _MAX_Y_RESET
        max_height_for_line = _MAX_HEIGHT_RESET

        wrote_any = False
        prev: TextPosition | None = None
        # Upstream tracks the wrapper of the first glyph of the previous
        # line (``lastLineStartPosition``) and the wrapper of the
        # immediately-previous glyph (``lastPosition``) so
        # ``isParagraphSeparation`` can compare the current X to the
        # *previous line's* left margin rather than to the prior glyph
        # (PDFTextStripper.java:503, 660, 709-713). The lite stripper
        # mirrors that here. The flip-axes path keeps the legacy prev-only
        # indent heuristic — its transposed frame is not calibrated for the
        # wrapper-based indent test, and (verified wave 1493) the
        # wrapper-based ``_classify_paragraph_separation`` cannot be reused
        # there: ``set_should_flip_axes`` is a lite-only *manual* X/Y
        # transpose with NO upstream counterpart (a full scan of
        # pdfbox-app-3.0.7.jar finds no ``flipAxes`` symbol) and it carries
        # no rotation in the coordinate matrix, so ``dir`` stays 0 and the
        # dir-adjusted fields (``get_x_dir_adj`` / ``get_y_dir_adj``) the
        # classifier reads are pure identity — there is nothing for them to
        # normalise. (Page ``/Rotate`` parity is a separate surface handled
        # by the page-rotation CTM fold in ``LegacyPDFStreamEngine``; see
        # ``tests/text/oracle/test_rotated_page_extraction_oracle.py`` and
        # a deferred follow-up.)
        last_line_start: PositionWrapper | None = None
        last_wrapper: PositionWrapper | None = None
        if carry is not None and carry:
            max_y_for_line = carry.get("max_y_for_line", _MAX_Y_RESET)  # type: ignore[assignment]
            max_height_for_line = carry.get(  # type: ignore[assignment]
                "max_height_for_line", _MAX_HEIGHT_RESET
            )
            prev = carry.get("prev")  # type: ignore[assignment]
            last_line_start = carry.get("last_line_start")  # type: ignore[assignment]
            last_wrapper = carry.get("last_wrapper")  # type: ignore[assignment]
        # Upstream resets ``startOfArticle = true`` at the head of every
        # article iteration (PDFTextStripper.java:534); the first glyph of an
        # article with a non-null ``lastPosition`` then flags that previous
        # glyph as the article start (line 641-645). The lite emitter only
        # carries ``last_wrapper`` across buckets, so this flag governs the
        # one inter-article transition handled inside this call.
        start_of_article = True
        for pos in positions:
            position_y = pos.x if self._flip_axes else pos.y
            position_height = pos.get_height_dir()
            cur_wrapper = PositionWrapper(pos)
            if (
                start_of_article
                and last_wrapper is not None
                and not self._flip_axes
            ):
                # ``lastPosition.setArticleStart()`` — the previous bucket's
                # final glyph becomes the article-start anchor consulted by
                # the article-start branch of ``handleLineSeparation``.
                last_wrapper.set_article_start()
            start_of_article = False
            if prev is None and open_page_paragraph and emit_paragraph_markers:
                # Upstream opens the page-body paragraph on the first glyph
                # (``startOfPage && lastPosition == null`` →
                # ``writeParagraphStart``, PDFTextStripper.java:700-703).
                self.write_paragraph_start(sink)
            if prev is None and not self._flip_axes:
                # Upstream marks the first glyph of the page as both a
                # paragraph start and a line start, seeding
                # ``lastLineStartPosition`` (PDFTextStripper.java:709-713).
                cur_wrapper.set_paragraph_start()
                cur_wrapper.set_line_start()
                last_line_start = cur_wrapper
            if prev is not None:
                # Flip-axes extraction keeps the legacy prev-only
                # line-stepping heuristic — the running-overlap model is
                # calibrated for the upright frame where Y is the line-flow
                # axis and ``get_height_dir`` is the glyph's vertical extent;
                # under the lite-only ``set_should_flip_axes`` transpose the
                # stepping axis is X and the relevant extent would be the
                # glyph width, which the overlap model does not track. The
                # overlap model is NOT reusable here via the dir-adjusted
                # fields: flip-axes carries no rotation in the matrix
                # (``dir == 0``), so those fields are identity (verified
                # wave 1493). Page ``/Rotate`` is a separate surface (the
                # missing page-rotation CTM fold — a deferred follow-up).
                if self._flip_axes:
                    line_broke = self._is_line_break(pos, prev)
                else:
                    line_broke = not self._overlaps_line(
                        position_y,
                        position_height,
                        max_y_for_line,
                        max_height_for_line,
                    )
                if line_broke:
                    _flush_word()
                    # Mark the new line's first glyph and run upstream's
                    # paragraph-separation classifier against the *previous*
                    # line's start glyph (``handleLineSeparation``,
                    # PDFTextStripper.java:1559-1587). The flip-axes path
                    # keeps the legacy prev-only indent test.
                    cur_wrapper.set_line_start()
                    if self._flip_axes:
                        para_break = self.is_paragraph_separation(pos, prev)
                    else:
                        self._classify_paragraph_separation(
                            cur_wrapper,
                            last_wrapper,  # type: ignore[arg-type]
                            last_line_start,
                            max_height_for_line
                            if max_height_for_line > 0.0
                            else position_height,
                        )
                        para_break = cur_wrapper.is_paragraph_start()
                    # Faithful port of upstream ``handleLineSeparation``'s
                    # emission tree (PDFTextStripper.java:1566-1585). When the
                    # previous glyph was flagged an article start (the first
                    # glyph of a new bead bucket whose ``lastPosition`` is the
                    # prior bucket's tail), a *paragraph* break across that
                    # boundary collapses to just ``writeParagraphStart`` (plus
                    # a line separator only if that tail was itself a line
                    # start) — i.e. NO inter-article line break is emitted for
                    # a large vertical jump between columns. Only a non-article
                    # paragraph break expands to ``writeLineSeparator +
                    # writeParagraphSeparator`` (= end+start). A plain
                    # (non-paragraph) line break between two articles, by
                    # contrast, still emits a single line separator — which is
                    # what splits a column's trailing line from a residual
                    # final line one row below it (the ``mon Dieu`` case).
                    last_is_article_start = (
                        last_wrapper is not None and last_wrapper.is_article_start()
                    )
                    if para_break and last_is_article_start:
                        # Upstream's inner ``if (lastPosition.isLineStart())
                        # writeLineSeparator()`` (PDFTextStripper.java:1570-
                        # 1573) keys on the *last glyph* of the previous
                        # article. The lite stripper emits one TextPosition per
                        # show-text run rather than per glyph (the documented
                        # run-vs-glyph carve-out), so its ``last_wrapper`` is
                        # the whole final run; a multi-glyph final line's last
                        # glyph is never a line start in Java, so the run-level
                        # ``is_line_start`` would over-fire here. Mirror Java's
                        # effective behaviour for multi-glyph runs by emitting
                        # only the paragraph start.
                        self.write_paragraph_start(sink)
                    elif para_break:
                        # Upstream ``handleLineSeparation`` emits the line
                        # separator *first*, then the paragraph separator
                        # (``writeParagraphEnd`` + ``writeParagraphStart``)
                        # for a mid-page paragraph break — i.e.
                        # ``writeLineSeparator → writeParagraphEnd →
                        # writeParagraphStart`` (PDFTextStripper.java:1578-
                        # 1579, where ``writeParagraphSeparator`` expands to
                        # end+start). In PDFText2HTML this surfaces as
                        # ``\n</p>\n<p>`` rather than the previously-emitted
                        # ``</p>\n\n<p>``.
                        self.write_line_separator(sink)
                        self.write_paragraph_end(sink)
                        self.write_paragraph_start(sink)
                    else:
                        self.write_line_separator(sink)
                    # The new line's first glyph becomes the next
                    # ``lastLineStartPosition`` (PDFTextStripper.java:1565).
                    last_line_start = cur_wrapper
                    max_y_for_line = _MAX_Y_RESET
                    max_height_for_line = _MAX_HEIGHT_RESET
                else:
                    if self._is_word_break(pos, prev):
                        _flush_word()
                        self.write_word_separator(sink)
                    # A horizontal jump of more than one space may mark a
                    # new column whose font (and thus glyph height) differs
                    # — reset the line extents so the next glyph re-anchors
                    # them (upstream PDFTextStripper.java:681-687).
                    if not self._flip_axes and self._is_column_jump(pos, prev):
                        max_y_for_line = _MAX_Y_RESET
                        max_height_for_line = _MAX_HEIGHT_RESET
            # Accumulate the line's vertical extent (upstream lines
            # 689-707): track the bottom-most baseline and the tallest glyph.
            # In the upright unrotated y-up frame the bottom-most baseline is
            # the *minimum* user-Y (mirror of upstream's max device-Y); the
            # rotated / flip-axes paths keep upstream's literal max sense (see
            # the ``min_y_line_axis`` note above).
            if min_y_line_axis:
                if position_y <= max_y_for_line:
                    max_y_for_line = position_y
            elif position_y >= max_y_for_line:
                max_y_for_line = position_y
            max_height_for_line = max(max_height_for_line, position_height)
            self.write_string_with_positions(pos.text, [pos], _buffered_sink)
            wrote_any = True
            prev = pos
            last_wrapper = cur_wrapper
        _flush_word()
        if wrote_any and emit_paragraph_markers:
            # Upstream closes the article's paragraph after its final line
            # (``writeLine(...); writeParagraphEnd()``,
            # PDFTextStripper.java:720-724).
            self.write_paragraph_end(sink)
        if carry is not None:
            # Persist the running line state for the next bead bucket so the
            # inter-article line-break test resumes from this bucket's final
            # glyph (upstream's loop-scoped ``lastPosition`` / ``maxYForLine``).
            carry["max_y_for_line"] = max_y_for_line
            carry["max_height_for_line"] = max_height_for_line
            carry["prev"] = prev
            carry["last_line_start"] = last_line_start
            carry["last_wrapper"] = last_wrapper
        return wrote_any

    # Tolerance (user-space units) below which two runs are treated as
    # sharing a baseline. Mirrors upstream ``TextPositionComparator``'s
    # ``yDifference < .1`` literal.
    _SORT_Y_TOLERANCE: float = 0.1

    def _compare_reading_order(
        self, pos1: TextPosition, pos2: TextPosition
    ) -> int:
        """Reading-order comparison for the non-flipped (``dir==0``) sort.

        Mirrors upstream ``org.apache.pdfbox.text.TextPositionComparator``:
        glyphs are grouped by direction first, then two runs that share a
        baseline (Y difference under tolerance) *or whose vertical glyph
        extents overlap* are ordered left-to-right by X rather than by their
        raw Y. Only runs that are vertically disjoint fall through to a
        Y comparison.

        The lite stripper carries Y in the PDF user-space frame (y-up: a
        larger Y is higher on the page), so the directions of the tolerance
        and Y comparisons are the user-space mirror of upstream's
        upper-left (y-down) frame: "top first" means *larger* Y first.

        Replacing the previous naive ``(-y, x)`` key (wave 1471) fixes the
        case where two runs on a visually shared line differ in Y by a
        sub-line-height jitter: the naive key reordered them by raw Y
        (putting the higher glyph first regardless of X) and then the
        word-break test, keyed on X gaps, misfired — diverging from Java,
        which keeps such runs in left-to-right reading order.
        """
        d1 = pos1.dir % 360.0
        d2 = pos2.dir % 360.0
        if d1 < d2:
            return -1
        if d1 > d2:
            return 1

        x1 = pos1.x
        x2 = pos2.x
        # Baselines in the user-space (y-up) frame.
        y1 = pos1.y
        y2 = pos2.y
        # Top edge of each run (one line height above its baseline).
        y1_top = y1 + pos1.get_height_dir()
        y2_top = y2 + pos2.get_height_dir()

        y_difference = abs(y1 - y2)
        if (
            y_difference < self._SORT_Y_TOLERANCE
            or (y1 <= y2 <= y1_top)
            or (y2 <= y1 <= y2_top)
        ):
            if x1 < x2:
                return -1
            if x1 > x2:
                return 1
            return 0

        # Vertically disjoint — top-to-bottom: larger Y (higher) first.
        if y1 > y2:
            return -1
        return 1

    def _is_line_break(
        self, pos: TextPosition, prev: TextPosition
    ) -> bool:
        """True when ``pos`` belongs to a new line relative to ``prev``."""
        if self._flip_axes:
            # Rotated frame: line stepping happens along X.
            return abs(pos.x - prev.x) > max(prev.font_size, 0.1) * 0.5
        # The sole caller (_format_positions, ~line 2759) only invokes
        # _is_line_break inside its ``if self._flip_axes:`` branch — the
        # upright path uses the running-overlap model (_overlaps_line)
        # instead — so this non-flip fallback is structurally unreachable.
        # Kept for API symmetry with the flip-axes carve-out it serves.
        return abs(pos.y - prev.y) > max(prev.font_size, 0.1) * 0.5  # pragma: no cover

    @staticmethod
    def _overlaps_line(
        position_y: float,
        position_height: float,
        max_y_for_line: float,
        max_height_for_line: float,
    ) -> bool:
        """True when a glyph's vertical span overlaps the running line span.

        y-up mirror of upstream's private ``overlap``
        (PDFTextStripper.java:762-766), which in the device (y-down) frame
        reads::

            within(y1, y2, .1f)
            || y2 <= y1 && y2 >= y1 - height1
            || y1 <= y2 && y1 >= y2 - height2

        Here ``y1`` is the glyph baseline (``position_y``) and ``y2`` is the
        line's accumulated baseline (``max_y_for_line``). On the upright
        unrotated path the lite TextPosition carries Y in PDF user space
        (y-up: a larger Y is higher on the page) and ``max_y_for_line`` is
        the line's MIN user-Y (the bottom-most baseline — the y-up mirror of
        upstream's max device-Y; see ``_emit_group``). Substituting
        ``device_y = -user_y`` into upstream's ``overlap`` yields exactly the
        two clauses below: the glyph-span clause carries the *line's* height
        (``y2 <= y1 <= y2 + height2``) and the line-span clause carries the
        *glyph's* height (``y1 <= y2 <= y1 + height1``). A run's top edge is
        ``baseline + height`` (y-up) rather than ``baseline - height``. The
        ``within`` (shared-baseline) clause is sign-agnostic. When the line
        extents are still at their reset sentinels (no glyph yet), the height
        clauses correctly report no overlap so the first glyph always opens
        the line.
        """
        if PDFTextStripper.within(position_y, max_y_for_line, 0.1):
            return True
        # Glyph baseline sits within the line's [baseline, top] span.
        if max_y_for_line <= position_y <= max_y_for_line + max_height_for_line:
            return True
        # Line baseline sits within the glyph's [baseline, top] span.
        return position_y <= max_y_for_line <= position_y + position_height

    def _is_column_jump(self, pos: TextPosition, prev: TextPosition) -> bool:
        """True when ``pos`` starts more than one space past ``prev``'s
        origin along the flow axis.

        Mirrors upstream PDFTextStripper.java:681-682
        (``abs(position.getX() - lastPosition.getX()) > wordSpacing +
        deltaSpace``) — the trigger that resets the running line extents so
        a new column whose font size differs re-anchors the overlap test.
        Uses the previous run's space width and the configured spacing
        tolerance (``deltaSpace = wordSpacing × spacingTolerance``), falling
        back to the coarse ``font_size`` estimate for a metric-less run.
        """
        prev_origin = prev.y if self._flip_axes else prev.x
        cur_origin = pos.y if self._flip_axes else pos.x
        word_spacing = prev.width_of_space
        if word_spacing <= 0.0:
            word_spacing = prev.font_size * 0.5
        delta_space = word_spacing * self._spacing_tolerance
        return abs(cur_origin - prev_origin) > word_spacing + delta_space

    def _is_word_break(
        self, pos: TextPosition, prev: TextPosition
    ) -> bool:
        """True when ``pos`` is far enough past ``prev``'s right edge to
        warrant a word separator.

        Mirrors upstream ``PDFTextStripper.writeString``'s word-segmentation
        gate (PDF 32000-1 text-layout reconstruction): a separator is
        inserted when the horizontal gap between the previous run's right
        edge and this run's origin exceeds the *space-glyph-width-relative*
        threshold

            ``min(widthOfSpace × spacingTolerance,
                  averageCharWidth × averageCharTolerance)``

        with the default ``spacingTolerance = 0.5`` and
        ``averageCharTolerance = 0.3``. This replaces the legacy coarse
        ``font_size × 1.5`` heuristic, which fired ~36pt later than Java for a
        24pt font and missed mid-size positioning gaps (a deferred
        follow-up on word-break gap-threshold calibration). The space width
        and average char width are now real per-glyph metrics threaded
        through ``_emit``
        from the font's ``/Widths`` (wave 1408 per-code lookups), so the
        threshold tracks the active font's metrics the way upstream does.

        When the font supplies no usable space width (``width_of_space`` is
        zero — a malformed font with no metrics), upstream sets
        ``deltaSpace = Float.MAX_VALUE`` so only the average-char-width prong
        governs; we fall back to the same average-char prong, and finally to
        the legacy ``font_size`` estimate when neither metric is available.
        """
        # Upstream gates the gap-driven separator on a single, purely
        # previous-glyph test (PDFTextStripper.java:670-674):
        #
        #     (wordSeparator.isEmpty() ||
        #         (lastPosition.getUnicode() != null &&
        #          !lastPosition.getUnicode().endsWith(wordSeparator)))
        #
        # i.e. emit the separator unless the *previous* glyph's unicode
        # already ends with the configured word-separator string. There is
        # NO suppression keyed on the *current* glyph: when a producer
        # widens the gap *into* an explicit space glyph (a large ``Tc`` over
        # ``(AB CD)``), Java emits a gap separator *before* the space glyph
        # AND keeps the space glyph itself — yielding the double space in
        # ``A B  C D`` — and only suppresses the redundant separator on the
        # transition *out of* that space glyph (where the previous glyph's
        # unicode is the separator). Mirror that exactly: never inspect
        # ``pos`` here, and key the suppression on whether ``prev`` ends with
        # the word-separator string (not arbitrary whitespace).
        separator = self._word_separator
        if (
            separator
            and prev.text is not None
            and prev.text.endswith(separator)
        ):
            return False
        if prev.width > 0.0:
            prev_right = prev.x + prev.width if not self._flip_axes else prev.y + prev.width
        else:
            stretch = len(prev.text) * prev.font_size * 0.5
            prev_right = (prev.x + stretch) if not self._flip_axes else (prev.y + stretch)
        gap = (pos.x - prev_right) if not self._flip_axes else (pos.y - prev_right)
        # The space-width-relative threshold is only trustworthy when the
        # previous run carries *real* font metrics (a resolved ``PDFont`` whose
        # ``/Widths`` fed the run width and space width — wave 1408/1488). For a
        # malformed / font-less run both metrics are the coarse 0.5-em estimate,
        # so the fine threshold would over-segment; fall back to the legacy
        # ``font_size × 1.5`` estimate there (preserving pre-1488 behaviour for
        # streams whose font could not be resolved).
        if prev.font is None or prev.width_of_space <= 0.0 or prev.width <= 0.0:
            return gap > prev.font_size * self._WORD_GAP_FACTOR
        # Space-width-relative threshold (upstream ``deltaSpace`` prong).
        word_spacing = prev.width_of_space
        delta_space = word_spacing * self._spacing_tolerance
        # Average-char-width prong (upstream ``averageCharWidth``). Derived
        # from the previous run's true advance / glyph count.
        n_prev = len(prev.text)
        if n_prev > 0:
            average_char_width = prev.width / n_prev
            delta_char = average_char_width * self._average_char_tolerance
        else:
            delta_char = math.inf
        threshold = min(delta_space, delta_char)
        if not math.isfinite(threshold):
            threshold = prev.font_size * self._WORD_GAP_FACTOR
        return gap > threshold

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

    def _classify_paragraph_separation(
        self,
        position: PositionWrapper,
        last_position: PositionWrapper,
        last_line_start: PositionWrapper | None,
        max_height_for_line: float,
    ) -> None:
        """Faithful port of upstream ``isParagraphSeparation``
        (PDFTextStripper.java:1611-1683).

        Unlike the public 2-arg :meth:`is_paragraph_separation` (which
        compares the current glyph to the *immediately-previous* glyph and
        is kept for the existing unit API), this mirrors upstream exactly:
        the y-gap drop prong compares ``position`` to ``last_position``,
        but the indent / hanging-indent / list-item prongs compare
        ``position``'s X to ``last_line_start`` — the first glyph of the
        *previous line*. It toggles ``set_paragraph_start`` /
        ``set_hanging_indent`` on ``position`` rather than returning a bool,
        matching upstream's flag-mutating contract.
        """
        result = False
        if last_line_start is None:
            result = True
        else:
            pos_tp = position.get_text_position()
            last_tp = last_position.get_text_position()
            lls_tp = last_line_start.get_text_position()
            # y-gap drop prong vs the immediately-previous glyph
            # (PDFTextStripper.java:1621-1623).
            y_gap = abs(pos_tp.get_y_dir_adj() - last_tp.get_y_dir_adj())
            new_y_val = self.multiply_float(
                self.get_drop_threshold(), max_height_for_line
            )
            # indent prong vs the previous line's start glyph
            # (PDFTextStripper.java:1625-1629).
            x_gap = pos_tp.get_x_dir_adj() - lls_tp.get_x_dir_adj()
            new_x_val = self.multiply_float(
                self.get_indent_threshold(), pos_tp.get_width_of_space()
            )
            position_width = self.multiply_float(0.25, pos_tp.get_width())

            if y_gap > new_y_val:
                result = True
            elif x_gap > new_x_val:
                # text is indented, but try to screen for hanging indent
                if not last_line_start.is_paragraph_start():
                    result = True
                else:
                    position.set_hanging_indent()
            elif x_gap < -pos_tp.get_width_of_space():
                # text is left of previous line. Was it a hanging indent?
                if not last_line_start.is_paragraph_start():
                    result = True
            elif abs(x_gap) < position_width:
                # within 1/4 char of the last line start — lined up.
                if last_line_start.is_hanging_indent():
                    position.set_hanging_indent()
                elif last_line_start.is_paragraph_start():
                    # previous line looks like a list item?
                    li_pattern = self.match_list_item_pattern(last_line_start)
                    if li_pattern is not None:
                        current_pattern = self.match_list_item_pattern(position)
                        if li_pattern is current_pattern:
                            result = True
        if result:
            position.set_paragraph_start()

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
        """Bucket ``positions`` into the per-article ``charactersByArticle``
        slots upstream maintains when ``shouldSeparateByBeads`` is enabled.

        Faithful port of the article-assignment logic from upstream
        ``processPage`` (sizing, PDFTextStripper.java:349-377) and
        ``processTextPosition`` (assignment, PDFTextStripper.java:954-1020).
        For ``N`` thread beads upstream allocates ``2*N + 1`` slots: slot
        ``i*2 + 1`` holds glyphs *inside* bead ``i``, slot ``i*2`` is the
        "gap" before bead ``i`` (glyphs left-of / above the bead that did
        not land inside an earlier one), and the final slot
        (``charactersByArticle.size() - 1``) catches everything else. The
        slots are emitted in index order, which interleaves the gap runs
        between the bead columns and reproduces the reading flow — e.g. an
        inline stage-direction painted between two column beads stays
        adjacent to the text it follows rather than being shunted to a
        trailing residual bucket.

        Returns the non-empty slots in index order; an empty list when the
        active page has no usable thread beads (callers fall back to a
        single all-positions group).
        """
        page = self._active_page
        if page is None:
            return []
        try:
            beads = page.get_thread_beads()
        except Exception:  # noqa: BLE001 — defensive: malformed /B
            return []
        if not beads:
            return []
        # Bead rectangles, kept in the PDF user-space (y-up) frame the lite
        # TextPosition origins live in. Upstream flips them into image
        # (y-down) space (fillBeadRectangles, PDFTextStripper.java:386-420)
        # and compares against ``text.getY()`` there; working consistently
        # in y-up is equivalent for the ``contains`` test, and the gap-slot
        # fallbacks below are mirrored accordingly (see ``_bead_above``).
        # CropBox lower-left offsets are subtracted to mirror upstream's
        # cropbox adjustment (lines 410-417).
        try:
            crop = page.get_crop_box()
            crop_llx = float(crop.get_lower_left_x())
            crop_lly = float(crop.get_lower_left_y())
        except Exception:  # noqa: BLE001 — defensive: missing/odd CropBox
            crop_llx = 0.0
            crop_lly = 0.0
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
            rects.append(
                (
                    float(r.get_lower_left_x()) - crop_llx,
                    float(r.get_lower_left_y()) - crop_lly,
                    float(r.get_upper_right_x()) - crop_llx,
                    float(r.get_upper_right_y()) - crop_lly,
                )
            )
        if not any(r is not None for r in rects):
            return []
        # Upstream allocates ``2 * beadRectangles.size() + 1`` slots.
        slots: list[list[TextPosition]] = [[] for _ in range(len(rects) * 2 + 1)]
        last_index = len(slots) - 1
        for pos in positions:
            x = pos.x
            y = pos.y
            found = -1
            left_above = -1
            left = -1
            above = -1
            for i, rect in enumerate(rects):
                if found != -1:
                    break
                if rect is None:
                    # Upstream: a null bead rectangle short-circuits the
                    # glyph into slot 0 (PDFTextStripper.java:988-991).
                    found = 0
                    continue
                llx, lly, urx, ury = rect
                inside = llx <= x <= urx and lly <= y <= ury
                # Upstream image-space ``x < lowerLeftX`` is the same test in
                # either frame; ``y < upperRightY`` (image, y-down) is, in
                # PDF y-up space, ``y > lowerLeftY`` (the glyph baseline sits
                # above the bead's bottom edge).
                cond_left = x < llx
                cond_above = y > lly
                if inside:
                    found = i * 2 + 1
                elif (cond_left or cond_above) and left_above == -1:
                    left_above = i * 2
                elif cond_left and left == -1:
                    left = i * 2
                elif cond_above and above == -1:
                    above = i * 2
            if found != -1:
                idx = found
            elif left_above != -1:
                idx = left_above
            elif left != -1:
                idx = left
            elif above != -1:
                idx = above
            else:
                idx = last_index
            slots[idx].append(pos)
        return [s for s in slots if s]

    @staticmethod
    def _drop_overlapping_duplicates(
        positions: list[TextPosition],
    ) -> list[TextPosition]:
        """Drop runs that re-paint an earlier same-text run at (nearly)
        the same origin — the fake-bold / drop-shadow double strike.

        Faithful port of the ``suppressDuplicateOverlappingText`` filter in
        upstream ``PDFTextStripper.processTextPosition`` (PDFBox 3.0.7),
        adapted to the lite stripper's run-level positions:

        - The dedup map is PAGE-global and keyed on the decoded text
          (upstream ``characterListMapping``, cleared per page), so a
          re-paint of a run *anywhere* later in the page's content stream
          is still recognised — not just one painted immediately after its
          original.
        - ``tolerance = width / len(text) / 3`` — upstream divides the
          position's width by its unicode length; for the lite run-level
          position that is the run's average glyph advance over three. The
          SAME tolerance applies on both axes (upstream reuses ``tolerance``
          for the ``subMap`` x-window and the ``subSet`` y-window).
        - The match window is half-open — ``[v - tol, v + tol)`` — because
          Java's two-argument ``TreeMap.subMap`` / ``TreeSet.subSet`` are
          from-inclusive, to-exclusive: a recorded origin exactly at
          ``v - tol`` matches, one exactly at ``v + tol`` does not.
        - Only a SHOWN run records its origin; a suppressed run never
          extends the map (upstream adds to ``sameTextCharacters`` only
          when ``!suppressCharacter``).
        - Runs emitted inside an ``/ActualText`` span bypass the filter
          entirely (upstream guards the whole block with
          ``this.actualText == null``): they are always shown and are never
          recorded in the map.
        - An empty decoded text mirrors Java float arithmetic: with a
          positive width, ``width / 0`` is ``+Infinity`` — any earlier
          empty-text run on the page suppresses; with width 0 the tolerance
          is ``NaN`` and nothing ever matches (the run is always shown).

        Lite-only fallback: a non-empty run with no width metric
        (``width <= 0`` — synthetic positions, metric-less fonts, and the
        vertical-mode emitter, which carries no run width) uses a
        quarter-of-font-size window on both axes. Upstream never produces
        such glyphs (its ``TextPosition`` always carries the real glyph
        advance, so the true formula applies); with a literal ``0``
        tolerance the half-open window would be empty and double-painted
        vertical text that Java collapses would survive here.
        """
        result: list[TextPosition] = []
        seen: dict[str, dict[float, list[float]]] = {}
        for pos in positions:
            if pos.from_actual_text:
                result.append(pos)
                continue
            text = pos.text
            char_count = len(text)
            if pos.width > 0.0:
                # Java: text.getWidth() / textCharacter.length() / 3.0f —
                # float division, so length 0 yields +Infinity, not an error.
                tol = math.inf if char_count == 0 else pos.width / char_count / 3.0
            elif char_count == 0:
                # Java: 0f / 0 == NaN — every comparison below is False, so
                # the run is never suppressed (and its origin is recorded).
                tol = math.nan
            else:
                # Lite-only: no width metric — see docstring.
                tol = max(pos.font_size, 0.1) * 0.25
            same_text = seen.setdefault(text, {})
            suppress = False
            x_lo = pos.x - tol
            x_hi = pos.x + tol
            y_lo = pos.y - tol
            y_hi = pos.y + tol
            for x_key, y_values in same_text.items():
                if x_lo <= x_key < x_hi and any(
                    y_lo <= y_val < y_hi for y_val in y_values
                ):
                    suppress = True
                    break
            if not suppress:
                same_text.setdefault(pos.x, []).append(pos.y)
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

        - From the format path ``text`` is non-empty and ``text_positions``
          carries one entry per emitted run (the lite stripper emits one
          position per run, so the list is length 1).
        - Each position is dispatched through :meth:`process_text_position`
          *before* anything is written to ``sink``, so collectors can
          inspect the run's geometry before its text materialises.

        Upstream's ``writeString(String, List<TextPosition>)`` unconditionally
        delegates to ``writeString(String)`` — it writes ``text`` regardless
        of how many positions accompany it (the default overload ignores the
        position list entirely). The lite stripper mirrors that: a word's
        ``text`` is written whenever it is non-empty, even when its position
        list is empty (e.g. a caller-built :class:`WordWithTextPositions`
        with no backing glyphs, as ``write_line`` may receive). Dropping the
        run on an empty position list — the pre-wave-1588 behaviour — silently
        swallowed such words while still emitting the word separators around
        them, diverging from Java's ``writeLine``. Writing an *empty* ``text``
        stays a no-op (``writeString("")`` writes nothing), so it is skipped.

        The default delegates to :meth:`write_string` (the upstream-
        compatible single-arg name); subclasses can override either.
        """
        if not text:
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

    # ---------- /ActualText substitution ----------

    def _actual_text_for_run(self, text: str) -> str | None:
        """Decide what a show-text run contributes under an active
        ``/ActualText`` span.

        Returns:
          * ``text`` unchanged when no ``/ActualText`` is in effect;
          * the ``/ActualText`` replacement string for the **first**
            show-text run of the span (consuming the first-position flag);
          * ``None`` for every later run in the span (its glyph text is
            suppressed — the cursor still advances).

        Mirrors Apache PDFBox's ``PDFTextStripper``, which emits the
        ``/ActualText`` once at the span's first glyph and drops the
        glyph-derived text for the rest of the span (PDF §14.9.4).
        """
        if self._actual_text is None:
            return text
        if self._first_actual_text_position:
            self._first_actual_text_position = False
            return self._actual_text
        return None

    # ---------- marked-content hooks ----------

    def begin_marked_content_sequence(
        self,
        tag: COSName | None,
        properties: COSDictionary | None,
    ) -> None:
        """Hook invoked at every ``BMC`` / ``BDC`` operator. Tracks the
        current span's ``/ActualText`` so subsequent show-text runs emit
        the replacement instead of their raw glyph text (PDF §14.9.4).

        Mirrors upstream's overridden
        ``beginMarkedContentSequence(COSName, COSDictionary)``
        (PDFTextStripper.java): the current ``actualText`` field is set
        **unconditionally** to this span's ``/ActualText`` — so entering a
        nested span *without* one clears any inherited replacement, exactly
        as PDFBox does (verified against the live oracle, wave 1445). When
        the span carries an ``/ActualText`` the soft hyphen (U+00AD) is
        stripped and the first-position flag is armed so the replacement is
        emitted once, at the span's first glyph."""
        actual: str | None = None
        if properties is not None:
            try:
                raw = properties.get_string("ActualText")
            except Exception:  # noqa: BLE001 — defensive
                raw = None
            if raw is not None:
                actual = raw.replace("­", "")
        self._marked_content_stack.append((tag, properties, actual))
        # Upstream sets the field unconditionally; ``None`` here means a
        # nested span without /ActualText turns substitution back off.
        self._actual_text = actual
        if actual is not None:
            self._first_actual_text_position = True

    def end_marked_content_sequence(self) -> None:
        """Hook invoked at every ``EMC`` operator. Pops the marked-content
        stack and clears the current ``actual_text`` when the popped span
        contributed one.

        Mirrors upstream's overridden ``endMarkedContentSequence``
        (PDFTextStripper.java), which peeks the top span, nulls
        ``actualText`` if that span had an ``/ActualText``, then pops."""
        if not self._marked_content_stack:
            return
        _, _, actual = self._marked_content_stack[-1]
        if actual is not None:
            self._actual_text = None
        self._marked_content_stack.pop()


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
        "horizontal_scaling",
        "text_rise",
        "tm_a",
        "tm_b",
        "tm_c",
        "tm_d",
        "ctm",
        "gs_stack",
        "in_text_object",
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
        # Horizontal text scaling (``Tz``), as a fraction (``Tz/100``). PDF
        # 32000-1 §9.3.4: ``Tz`` is a *percentage* that scales the horizontal
        # component of every glyph displacement — and of ``Tc`` / ``Tw`` — by
        # ``Tz/100``. Default 1.0 (i.e. 100%) per ``BT`` text-state reset.
        # A non-1.0 value condenses (<1) or expands (>1) the horizontal
        # advance the word-gap heuristic measures, so word segmentation in
        # ``getText`` is ``Tz``-dependent.
        self.horizontal_scaling: float = 1.0
        # Text rise (``Ts``), in unscaled text-space units. PDF 32000-1
        # §9.3.7: ``Ts`` raises (positive) or lowers (negative) the baseline
        # of subsequent glyphs by shifting the text-rendering matrix origin
        # vertically — upstream folds it into the f-translation of the
        # font-parameter matrix (``[fontSize·Th, 0, 0, fontSize, 0, rise]``),
        # so it moves the glyph origin without changing the glyph scale or
        # direction. A superscript run (``4 Ts``) sits above the baseline; a
        # subscript run sits below. Default 0.0 per the ``BT`` text-state
        # reset. The rise is *not* part of the cursor advance — it is applied
        # only to the rendered origin and reset to 0 by a later ``0 Ts``.
        self.text_rise: float = 0.0
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
        # Whether a text object (``BT`` … ``ET``) is currently open. Upstream
        # gates the text-showing and text-positioning operators on a non-null
        # text matrix / text-line matrix (both set to identity by ``BT`` and
        # to ``null`` by ``ET`` and at stream start): ``Tj`` / ``TJ`` skip when
        # ``getTextMatrix() == null`` (``ShowText`` / ``ShowTextAdjusted``) and
        # ``Td`` / ``TD`` / ``T*`` skip when ``getTextLineMatrix() == null``
        # (``MoveText``). A single open/closed flag captures both, since ``BT``
        # sets both matrices and ``ET`` clears both. Without this gate the lite
        # stripper would extract glyphs from text operators stranded outside a
        # ``BT`` … ``ET`` pair (e.g. after a truncated stream drops the ``BT``),
        # diverging from Apache PDFBox which silently ignores them.
        self.in_text_object: bool = False


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
