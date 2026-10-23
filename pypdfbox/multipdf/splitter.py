import contextlib
import logging
import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSObject,
)

if TYPE_CHECKING:
    from pypdfbox.io import MemoryUsageSetting
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage


_LOG = logging.getLogger(__name__)

_TYPE: COSName = COSName.get_pdf_name("Type")
_RESOURCES: COSName = COSName.get_pdf_name("Resources")
_B: COSName = COSName.get_pdf_name("B")
_PARENT: COSName = COSName.get_pdf_name("Parent")
_POPUP: COSName = COSName.get_pdf_name("Popup")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_FT: COSName = COSName.get_pdf_name("FT")
_SIG: COSName = COSName.get_pdf_name("Sig")
_V: COSName = COSName.get_pdf_name("V")
_ACROFORM: COSName = COSName.get_pdf_name("AcroForm")
_SIG_FLAGS: COSName = COSName.get_pdf_name("SigFlags")
_FIELDS: COSName = COSName.get_pdf_name("Fields")
_DESTS: COSName = COSName.get_pdf_name("Dests")

# struct-tree clone helpers
_K: COSName = COSName.get_pdf_name("K")
_P: COSName = COSName.get_pdf_name("P")
_PG: COSName = COSName.get_pdf_name("Pg")
_S: COSName = COSName.get_pdf_name("S")
_ID: COSName = COSName.get_pdf_name("ID")
_OBJ: COSName = COSName.get_pdf_name("Obj")
_OBJR: COSName = COSName.get_pdf_name("OBJR")
_MCR: COSName = COSName.get_pdf_name("MCR")
_ANNOT: COSName = COSName.get_pdf_name("Annot")
_LINK: COSName = COSName.get_pdf_name("Link")
_ANNOTS: COSName = COSName.get_pdf_name("Annots")
_ROLE_MAP: COSName = COSName.get_pdf_name("RoleMap")
_CLASS_MAP: COSName = COSName.get_pdf_name("ClassMap")

# resource-pruning helpers
_AP: COSName = COSName.get_pdf_name("AP")
_CHAR_PROCS: COSName = COSName.get_pdf_name("CharProcs")
#: Name-keyed resource categories the pruner may narrow; everything else
#: (``/ProcSet``, exotic keys) is copied through untouched.
_PRUNABLE_CATEGORIES: tuple[str, ...] = (
    "Font",
    "XObject",
    "ExtGState",
    "ColorSpace",
    "Pattern",
    "Shading",
    "Properties",
)

# ---------- fast resource-name scanner (pruning hot path) ----------
#
# ``_prune_page_resources`` only needs the resource names a content stream
# hands to a handful of operators. Building a full ``PDFStreamParser`` token
# list per page (a COSBase per number, string and array) dominated split time,
# so the scanner below tokenizes with one compiled regex and keeps operands as
# lightweight markers. It accepts only a conservative subset of the content
# stream grammar on which its token boundaries provably coincide with
# ``PDFStreamParser``'s; anything else (inline images, ``#`` name escapes,
# numbers glued to other tokens, malformed containers, keywords inside
# arrays, ...) returns ``None`` and the caller re-scans the stream with the
# exact parser, so the collected names are identical either way.

_WS_CLASS = rb"\x00\t\n\x0c\r "
_FAST_TOKEN_RE = re.compile(
    rb"(?P<ws>[" + _WS_CLASS + rb"]+|%[^\r\n]*)"
    rb"|(?P<name>/[^" + _WS_CLASS + rb"()<>\[\]/%]*)"
    rb"|(?P<num>[+\-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)"
    rb"(?=[" + _WS_CLASS + rb"()<>\[\]{}/%]|\Z))"
    # Literal strings: up to two levels of unescaped nesting; deeper or
    # unterminated strings fall through to ``bad``.
    rb"|(?P<str>\((?:[^()\\]|\\.|\((?:[^()\\]|\\.)*\))*\))"
    rb"|(?P<dopen><<)|(?P<dclose>>>)"
    rb"|(?P<hex><[^>]*>)"
    rb"|(?P<aopen>\[)|(?P<aclose>\])"
    rb"|(?P<kw>['\"]|[A-Za-z*][^" + _WS_CLASS + rb"\[<(/%0-9]*)"
    rb"|(?P<bad>.)",
    re.DOTALL,
)
_KW_TAIL_RE = re.compile(rb"[^" + _WS_CLASS + rb"\[<(/%0-9]*")
# Operand-only shortcuts. Each piece below accepts exactly the bytes the
# corresponding ``_FAST_TOKEN_RE`` token accepts (or a subset of them), and
# is possessive / atomic: the alternatives start with disjoint bytes, so that
# never changes what matches, it only rules out backtracking blow-ups on long
# runs that end in an unsupported token. Literal strings are restricted to
# bodies with no ``(`` byte at all, escaped or not: the main loop replays the
# PDFBOX-276 end-of-string look-ahead whenever the body holds one, so those
# take the token-by-token path.
_SHORTCUT_WS = rb"[" + _WS_CLASS + rb"]++|%[^\r\n]*+"
_SHORTCUT_NUM = (
    rb"(?>[+\-]?(?:[0-9]++(?:\.[0-9]*+)?|\.[0-9]++))"
    rb"(?=[" + _WS_CLASS + rb"()<>\[\]{}/%]|\Z)"
)
_SHORTCUT_STR = rb"\((?:[^()\\]|\\[^(])*+\)"
_SHORTCUT_HEX = rb"<(?!<)[^>]*+>"
#: A whole top-level array of numbers, flat literal strings and hex strings
#: (the ``TJ`` / ``d`` operand shape). Every element is a token the main loop
#: accepts inside an array without effect, so matching it in one step is
#: equivalent to tokenizing it: the array contributes a single operand.
#: Anything else (names, strings holding a ``(``, dictionaries, keywords)
#: fails this match and the array is tokenized element by element.
_SHORTCUT_ARRAY = (
    rb"\[(?:" + _SHORTCUT_WS + rb"|" + _SHORTCUT_NUM + rb"|" + _SHORTCUT_STR
    + rb"|" + _SHORTCUT_HEX + rb")*+\]"
)
_SIMPLE_ARRAY_RE = re.compile(_SHORTCUT_ARRAY, re.DOTALL)
#: With no pending operands: a run of name-free operands (numbers, flat
#: strings, hex strings, simple arrays) closed by an operator keyword. No
#: name operand means the operator cannot record a resource name, so the
#: whole run is a no-op for the scan -- provided the keyword is an ordinary
#: operator (the caller checks the keyword group for the special cases).
_PLAIN_RUN_RE = re.compile(
    rb"(?:" + _SHORTCUT_WS + rb"|" + _SHORTCUT_NUM + rb"|" + _SHORTCUT_STR
    + rb"|" + _SHORTCUT_HEX + rb"|" + _SHORTCUT_ARRAY + rb")*+"
    rb"(?P<kw>['\"]|[A-Za-z*][^" + _WS_CLASS + rb"\[<(/%0-9]*+)",
    re.DOTALL,
)
#: Unescaped ``(`` / ``)`` inside a nested literal string; used to replay the
#: parser's PDFBOX-276 ``checkForEndOfString`` look-ahead on nested closers.
_NESTED_CLOSE_EOS_RE = re.compile(rb"\)(?:[\r\n][/>]|\r\n[/>])")
_OPERAND = object()
_FAST_CATEGORY_OPS: dict[bytes, str] = {
    b"Tf": "Font",
    b"Do": "XObject",
    b"gs": "ExtGState",
    b"CS": "ColorSpace",
    b"cs": "ColorSpace",
    b"sh": "Shading",
}


def _fast_scan_resource_names(data: bytes) -> dict[str, set[bytes]] | None:
    """Collect the raw (undecoded) resource names referenced by ``data``.

    Returns ``{category: {name_bytes}}`` mirroring the exact-parser scan in
    :meth:`Splitter._prune_page_resources`, or ``None`` when the stream uses
    any construct outside the fast subset (the caller then falls back to
    ``PDFStreamParser``)."""
    used: dict[str, set[bytes]] = {c: set() for c in _PRUNABLE_CATEGORIES}
    operands: list[Any] = []
    # Container stack: "a" = array, "k" = dict expecting a key,
    # "v" = dict expecting a value.
    stack: list[str] = []
    n = len(data)
    pos = 0
    match = _FAST_TOKEN_RE.match
    simple_array = _SIMPLE_ARRAY_RE.match
    plain_run = _PLAIN_RUN_RE.match
    while pos < n:
        if not operands and not stack:
            run = plain_run(data, pos)
            if run is not None:
                tok = run.group("kw")
                end = run.end()
                if not (
                    tok in (b"true", b"false", b"null")
                    or tok == b"BI"
                    or tok[:1] == b"I"
                    or (tok[-1:] == b"d" and end < n and data[end] in b"01")
                ):
                    pos = end
                    continue
        m = match(data, pos)
        assert m is not None  # ``bad`` matches any single byte
        kind = m.lastgroup
        end = m.end()
        if kind == "ws":
            pos = end
            continue
        if kind == "kw":
            tok = m.group()
            if tok[-1:] == b"d" and end < n and data[end] in b"01":
                # Type 3 ``d0`` / ``d1``: the parser folds the digit into
                # the keyword and keeps reading the run.
                while tok[-1:] == b"d" and end < n and data[end] in b"01":
                    tail = _KW_TAIL_RE.match(data, end + 1)
                    assert tail is not None
                    tok = tok + data[end : tail.end()]
                    end = tail.end()
            if tok in (b"true", b"false", b"null"):
                kind = "operand"
            elif stack or tok == b"BI" or tok[:1] == b"I":
                # Keyword inside a container, or inline image: not in the
                # fast subset.
                return None
            else:
                if operands:
                    _fast_record(tok, operands, used)
                    operands = []
                pos = end
                continue
        elif kind == "name":
            tok = m.group()
            if b"#" in tok:
                return None
            if stack:
                top = stack[-1]
                if top == "k":
                    stack[-1] = "v"
                elif top == "v":
                    stack[-1] = "k"
                pos = end
                continue
            operands.append(tok[1:])
            pos = end
            continue
        elif kind == "str":
            body = m.group()
            if b"(" in body[1:-1] and _NESTED_CLOSE_EOS_RE.search(
                data, m.start(), end - 1
            ):
                return None
            kind = "operand"
        elif kind in ("num", "hex"):
            kind = "operand"
        elif kind == "aopen" or kind == "dopen":
            if not stack and kind == "aopen":
                simple = simple_array(data, m.start())
                if simple is not None:
                    operands.append(_OPERAND)
                    pos = simple.end()
                    continue
            if stack and stack[-1] == "k":
                return None
            stack.append("a" if kind == "aopen" else "k")
            pos = end
            continue
        elif kind == "aclose":
            if not stack or stack.pop() != "a":
                return None
            kind = "operand"
        elif kind == "dclose":
            if not stack or stack.pop() != "k":
                return None
            kind = "operand"
        else:  # bad byte
            return None
        # ``kind == "operand"``: a complete scalar or a closed container.
        if stack:
            top = stack[-1]
            if top == "k":
                return None
            if top == "v":
                stack[-1] = "k"
        else:
            operands.append(_OPERAND)
        pos = end
    if stack:
        return None
    return used


def _fast_record(
    op: bytes, operands: list[Any], used: dict[str, set[bytes]]
) -> None:
    """Apply one operator to the operand list (mirrors ``scan``)."""
    category = _FAST_CATEGORY_OPS.get(op)
    if category is not None:
        first = operands[0]
        if first is not _OPERAND:
            used[category].add(first)
    elif op == b"SCN" or op == b"scn":
        last = operands[-1]
        if last is not _OPERAND:
            used["Pattern"].add(last)
    elif (op == b"BDC" or op == b"DP") and len(operands) >= 2:
        second = operands[1]
        if second is not _OPERAND:
            used["Properties"].add(second)


class Splitter:
    """
    Split a ``PDDocument`` into one or more smaller documents. Mirrors
    ``org.apache.pdfbox.multipdf.Splitter``.

    Public surface:

    - :meth:`set_split_at_page` (alias :meth:`set_split`) — pages per chunk;
    - :meth:`set_start_page`, :meth:`set_end_page` — 1-based inclusive
      page range;
    - :meth:`set_memory_usage_setting` /
      :meth:`set_stream_cache_create_function` — recorded but advisory in
      this port (see ``CHANGES.md``);
    - :meth:`split` — returns ``list[PDDocument]``.

    Subclassing hooks (mirroring upstream ``protected`` methods):
    :meth:`split_at_page`, :meth:`create_new_document`,
    :meth:`process_page`, :meth:`get_source_document`,
    :meth:`get_destination_document`.

    The structure-tree / parent-tree / id-tree / role-map cloning that
    upstream performs after the page walk is implemented here in full —
    see :meth:`clone_structure_tree`. Cross-chunk link-annotation
    destinations are nulled out in :meth:`fix_destinations` so the
    chunk's `/Dest` payloads don't carry refs to pages that didn't
    follow the split.
    """

    # ---------- defaults & sentinels (class constants) ----------
    #
    # Mirrors the field initialisers on upstream
    # ``org.apache.pdfbox.multipdf.Splitter``. Surfacing them as class
    # constants lets callers compare ``get_start_page() ==
    # Splitter.START_PAGE_DEFAULT`` (or use :meth:`has_start_page`) to
    # distinguish "untouched" from "explicitly set to N" — same semantic
    # as upstream's ``Integer.MIN_VALUE`` / ``Integer.MAX_VALUE`` sentinels.

    #: Default split granularity — every page becomes a new document.
    DEFAULT_SPLIT_LENGTH: int = 1

    #: Sentinel meaning "no lower clamp". Mirrors upstream's
    #: ``Integer.MIN_VALUE`` initialiser on ``startPage``.
    START_PAGE_DEFAULT: int = -(2**31)

    #: Sentinel meaning "no upper clamp". Mirrors upstream's
    #: ``Integer.MAX_VALUE`` initialiser on ``endPage``.
    END_PAGE_DEFAULT: int = 2**31 - 1

    def __init__(self) -> None:
        self._source_document: PDDocument | None = None
        self._current_destination_document: PDDocument | None = None

        self._split_length: int = self.DEFAULT_SPLIT_LENGTH
        # Sentinels used to mean "no clamp"; mirror upstream
        # Integer.MIN_VALUE / Integer.MAX_VALUE.
        self._start_page: int = self.START_PAGE_DEFAULT
        self._end_page: int = self.END_PAGE_DEFAULT

        self._destination_documents: list[PDDocument] = []
        self._page_dict_map: dict[int, COSDictionary] = {}
        self._page_dict_maps: list[dict[int, COSDictionary]] = []
        # pageToDocNumMap mirror (PDFBOX-6283): {id(source page dict):
        # index of the destination document that received the page}.
        self._page_to_doc_num_map: dict[int, int] = {}
        self._annot_dict_map: dict[int, COSDictionary] = {}
        self._annot_dict_maps: list[dict[int, COSDictionary]] = []
        # struct-tree clone state, reset per chunk
        self._struct_dict_map: dict[int, COSDictionary] = {}
        self._id_set: set[str] = set()
        self._role_set: set[str] = set()
        # {id(dst_page_dict): page_index} for the chunk currently being
        # struct-cloned. Rebuilt once per chunk in clone_structure_tree so
        # _k_clone_dictionary can test chunk membership in O(1) instead of
        # walking the page tree per struct element. Only trusted when the
        # page_tree threaded into the clone matches the one the map was
        # built from (``_page_index_tree_id``); direct callers that pass a
        # foreign / mock page tree fall back to ``page_tree.index_of``.
        self._page_index_by_id: dict[int, int] = {}
        self._page_index_tree_id: int | None = None
        # Flattened source /ParentTree number map. The source document is
        # immutable during split(); flatten it once (lazily on first chunk)
        # and share the read-only map across every chunk instead of
        # re-flattening per chunk. Reset at split() start, cleared at end.
        self._src_number_tree_map: dict[int, COSBase] | None = None
        # Resource-pruning scan cache: {decoded stream bytes: names}. Holds
        # only bytes and immutable name sets, never COS objects of a
        # destination document. Reset at the start and end of split().
        self._resource_scan_cache: dict[bytes, dict[str, frozenset[str]]] = {}
        # Per-run cache of resolved source structure-element fields
        # ({id(src): [src, /Pg, /K, /Type, has_mcids]}), shared by every
        # chunk's structure-tree clone. ``None`` outside split() so direct
        # helper calls always read the live dictionaries.
        self._k_node_cache: dict[int, list[Any]] | None = None
        # Subtree-skip switch and the chunk index being struct-cloned; set by
        # split() (see _build_k_skip_info).
        self._k_skip_enabled: bool = False
        self._k_skip_pending: bool = False
        self._k_chunk_index: int = 0
        # destToFixMap mirror — list of (cloned_dest_array, source_host_page_dict,
        # source_target_page_dict) per chunk. Deferred to after the page walk
        # so we can decide whether each destination's target page lives in
        # the chunk.
        #
        # ``source_target_page_dict`` is the page the destination *points to*,
        # captured before ``import_page``'s deep-copy replaced the indirect
        # ref's resolved target with a fresh COSDictionary instance. Without
        # that snapshot, the post-pass ``_page_dict_map`` lookup keyed by
        # ``id()`` misses cross-page targets (wave 1294).
        self._dest_to_fix: list[
            tuple[COSArray, COSDictionary, COSDictionary | None]
        ] = []
        self._dest_to_fix_per_chunk: list[
            list[tuple[COSArray, COSDictionary, COSDictionary | None]]
        ] = []
        # Wave-1379 side-table keyed by ``id(cloned_array)`` carrying the
        # cloned link annotation that hosts each cloned destination. Drained
        # by :meth:`fix_destinations` only when the cross-chunk resolver
        # opted into a GoToR rewrite — we need direct access to the
        # annotation dict to swap its ``/Dest`` (or ``/A GoTo``) entry for a
        # ``/A GoToR`` action. Kept separate from ``_dest_to_fix`` so the
        # historical 3-tuple shape (and the legacy 2-tuple fallback in
        # :meth:`fix_destinations`) remain wire-compatible.
        self._dest_to_link_map: dict[int, COSDictionary] = {}
        self._dest_to_link_map_per_chunk: list[dict[int, COSDictionary]] = []
        # Per-chunk queue of (cloned_annotations, source_annots_array,
        # imported_page_dict) tuples populated by ``_process_annotations``'
        # first pass and drained by ``_finalize_annotation_links`` after
        # *every* page in the chunk has been imported. Deferring the
        # second pass lets a markup annotation on chunk page A correctly
        # rewrite its ``/Popup`` to a popup annotation on chunk page B
        # (wave 1373): the per-page run order otherwise meant page A's
        # second pass executed before page B's first pass populated
        # ``_annot_dict_map`` with the cloned popup. Mirrors the upstream
        # invariant that ``annotDictMap`` is chunk-wide; the only behaviour
        # change is that we look up the same map *later* so cross-page
        # annotation refs in the same chunk resolve to cloned dicts.
        self._pending_annot_passes: list[
            tuple[list[Any], COSArray | None, COSDictionary | None]
        ] = []
        self._pending_annot_passes_per_chunk: list[
            list[tuple[list[Any], COSArray | None, COSDictionary | None]]
        ] = []

        self._current_page_number: int = 0

        self._stream_cache_create_function: Callable[[], Any] | None = None
        self._memory_usage_setting: MemoryUsageSetting | None = None

        # Wave 1379: opt-in callback that the post-pass calls when a cloned
        # link's target page lives outside the chunk that hosts the link. The
        # resolver receives the *source* target page COSDictionary and may
        # return:
        #
        #   * ``None`` — keep the historical null-out behaviour (the cloned
        #     destination's ``/D[0]`` slot becomes ``COSNull``);
        #   * ``str`` — interpret the returned value as a relative file name
        #     and rewrite the link's destination into a GoToR action targeting
        #     that file. The original explicit-fit-mode array (``[null /XYZ
        #     left top zoom]`` etc.) is preserved verbatim except for the
        #     ``[0]`` page slot, which is replaced by the *integer page index*
        #     within the target file. The caller is responsible for arranging
        #     the per-chunk filename mapping (typically by computing it from
        #     ``Splitter.split()``'s return order).
        #
        # Mirrors the PDFBox forum / mailing-list pattern of post-processing
        # split outputs to retarget cross-chunk links — upstream's
        # ``Splitter`` ships only the null-out strategy, so this is a strict
        # parity extension.
        self._cross_chunk_destination_resolver: (
            Callable[[COSDictionary], tuple[str, int] | str | None] | None
        ) = None

    # ---------- configuration ----------

    def set_split_at_page(self, split: int) -> Splitter:
        """Set the split granularity. Mirrors upstream
        ``setSplitAtPage(int)`` — rejects ``split <= 0``. Returns ``self``
        so callers can chain configuration calls."""
        if split <= 0:
            raise ValueError("Number of pages is smaller than one")
        self._split_length = split
        return self

    def set_split(self, split: int) -> Splitter:
        """Alias for :meth:`set_split_at_page`. Returns ``self`` for
        fluent chaining."""
        return self.set_split_at_page(split)

    def get_split_at_page(self) -> int:
        """Return the configured split granularity. Defaults to
        :attr:`DEFAULT_SPLIT_LENGTH` (= 1) when no setter has been called.
        Upstream lacks this getter — surfaced here so callers and tests
        don't need to read the private field directly."""
        return self._split_length

    def set_start_page(self, start: int) -> Splitter:
        """Set the 1-based inclusive lower page bound. Mirrors upstream
        ``setStartPage(int)`` — rejects ``start <= 0``. Returns ``self``
        for fluent chaining."""
        if start <= 0:
            raise ValueError("Start page is smaller than one")
        self._start_page = start
        return self

    def get_start_page(self) -> int:
        """Return the configured start page. Defaults to
        :attr:`START_PAGE_DEFAULT` (= ``Integer.MIN_VALUE``) when no
        setter has been called — use :meth:`has_start_page` to
        distinguish "untouched" from "explicitly set"."""
        return self._start_page

    def has_start_page(self) -> bool:
        """``True`` when :meth:`set_start_page` has been called with an
        explicit value (i.e. the field is not the default sentinel).
        Predicate helper that lets callers branch on "user supplied a
        bound" vs "no clamp" without having to know the sentinel value."""
        return self._start_page != self.START_PAGE_DEFAULT

    def set_end_page(self, end: int) -> Splitter:
        """Set the 1-based inclusive upper page bound. Mirrors upstream
        ``setEndPage(int)`` — rejects ``end <= 0`` and ``end <
        startPage`` (when start was explicitly set). Returns ``self``
        for fluent chaining."""
        if end <= 0:
            raise ValueError("End page is smaller than one")
        if end < self._start_page:
            raise ValueError("End page is smaller than startPage")
        self._end_page = end
        return self

    def get_end_page(self) -> int:
        """Return the configured end page. Defaults to
        :attr:`END_PAGE_DEFAULT` (= ``Integer.MAX_VALUE``) when no
        setter has been called — use :meth:`has_end_page` to
        distinguish "untouched" from "explicitly set"."""
        return self._end_page

    def has_end_page(self) -> bool:
        """``True`` when :meth:`set_end_page` has been called with an
        explicit value (i.e. the field is not the default sentinel)."""
        return self._end_page != self.END_PAGE_DEFAULT

    def get_stream_cache_create_function(self) -> Callable[[], Any] | None:
        return self._stream_cache_create_function

    def set_stream_cache_create_function(
        self, fn: Callable[[], Any] | None
    ) -> Splitter:
        """Record the stream-cache factory used for new destination
        documents. Returns ``self`` for fluent chaining."""
        self._stream_cache_create_function = fn
        return self

    def has_stream_cache_create_function(self) -> bool:
        """``True`` when a stream-cache factory has been registered."""
        return self._stream_cache_create_function is not None

    def set_memory_usage_setting(
        self, setting: MemoryUsageSetting | None
    ) -> Splitter:
        """Record a :class:`MemoryUsageSetting` for newly-created destination
        documents. Recorded only — destination ``PDDocument`` construction
        in this port does not yet thread the setting through (see
        ``CHANGES.md``). Returns ``self`` for fluent chaining."""
        self._memory_usage_setting = setting
        return self

    def get_memory_usage_setting(self) -> MemoryUsageSetting | None:
        return self._memory_usage_setting

    def has_memory_usage_setting(self) -> bool:
        """``True`` when a :class:`MemoryUsageSetting` has been registered."""
        return self._memory_usage_setting is not None

    def set_cross_chunk_destination_resolver(
        self,
        resolver: (
            Callable[[COSDictionary], tuple[str, int] | str | None] | None
        ),
    ) -> Splitter:
        """Register a callback used by :meth:`fix_destinations` to rewrite
        cross-chunk link destinations as ``GoToR`` actions.

        Wave-1379 extension closing the DEFERRED entry for the splitter's
        full §12.3.2.3 destination-rewrite coverage. The resolver receives
        the *source* target page :class:`COSDictionary` (the page the cloned
        link points at, captured before ``import_page``'s deep-copy) and
        returns one of:

        * ``None`` — keep historical null-out behaviour;
        * a plain ``str`` — interpret as the relative file name of the
          sibling chunk file that contains the target page; the link's
          ``/D[0]`` slot is replaced by the *integer page index* the
          resolver reports via the second tuple form below, or by ``0``
          when only a string is returned (caller should prefer the tuple
          form to retain page identity);
        * a ``(file_name, page_index)`` tuple — explicit file + 0-based
          page index pair, matching the canonical PDF 32000-1 §12.6.4.3
          ``GoToR`` payload.

        Returns ``self`` for fluent chaining."""
        self._cross_chunk_destination_resolver = resolver
        return self

    def get_cross_chunk_destination_resolver(
        self,
    ) -> Callable[[COSDictionary], tuple[str, int] | str | None] | None:
        """Return the cross-chunk destination resolver registered via
        :meth:`set_cross_chunk_destination_resolver`, or ``None``."""
        return self._cross_chunk_destination_resolver

    def has_cross_chunk_destination_resolver(self) -> bool:
        """``True`` when a cross-chunk destination resolver is registered."""
        return self._cross_chunk_destination_resolver is not None

    # ---------- core ----------

    def split(self, document: PDDocument) -> list[PDDocument]:
        """Split ``document`` and return a list of fresh ``PDDocument``
        instances. The caller owns each returned document and must save
        them before closing ``document`` (cross-document resource sharing
        means the source must outlive its splits)."""
        self._current_page_number = 0
        self._current_destination_document = None
        self._destination_documents = []
        self._source_document = document
        self._page_dict_maps = []
        self._page_to_doc_num_map = {}
        self._annot_dict_maps = []
        self._dest_to_fix_per_chunk = []
        self._dest_to_link_map_per_chunk = []
        self._pending_annot_passes_per_chunk = []
        self._id_set = set()
        self._role_set = set()
        # Flattened source /ParentTree cache — populated lazily on the
        # first tagged chunk, shared read-only across the rest of the run.
        self._src_number_tree_map = None
        self._resource_scan_cache = {}
        self._k_node_cache = {}
        self._k_skip_enabled = False
        self._k_skip_pending = True
        # Track whether any chunk dropped a signature widget; clear
        # /SigFlags + scrub /AcroForm in destination catalogs at the end.
        self._signatures_dropped: bool = False

        self._process_pages()

        # Post-pass per chunk: structure tree clone + destination fix-up.
        for index, destination_document in enumerate(self._destination_documents):
            self._page_dict_map = self._page_dict_maps[index]
            self._annot_dict_map = self._annot_dict_maps[index]
            self._dest_to_fix = self._dest_to_fix_per_chunk[index]
            self._dest_to_link_map = self._dest_to_link_map_per_chunk[index]
            self._pending_annot_passes = (
                self._pending_annot_passes_per_chunk[index]
            )
            # Drain the deferred markup/popup linkage pass once
            # ``_annot_dict_map`` reflects every page in the chunk.
            try:
                self._finalize_annotation_links()
            except Exception:
                _LOG.exception(
                    "annotation linkage finalisation failed for chunk %d; "
                    "popup/markup back-pointers may dangle",
                    index,
                )
            try:
                # Dispatch via the underscored alias so subclasses can
                # override either the public ``clone_structure_tree`` or
                # the upstream-private ``_clone_structure_tree`` and have
                # the override picked up.
                self._k_chunk_index = index
                self._clone_structure_tree(destination_document)
            except Exception:
                _LOG.exception(
                    "structure-tree clone failed for chunk %d; chunk will "
                    "ship without /StructTreeRoot",
                    index,
                )
            try:
                self._fix_destinations(destination_document)
            except Exception:
                _LOG.exception(
                    "destination fix-up failed for chunk %d; cross-chunk "
                    "/Dest links may dangle",
                    index,
                )
            try:
                self._scrub_acroform(destination_document)
            except Exception:
                _LOG.exception(
                    "AcroForm scrub failed for chunk %d; signature flags "
                    "may persist in chunk catalog",
                    index,
                )
        # PDFBOX-6283: carry the named destinations (/Names /Dests name tree
        # and legacy /Root/Dests) over to the chunks that own their pages.
        try:
            self.fix_name_destinations()
        except Exception:
            _LOG.exception(
                "named destinations fix-up failed; chunks will ship "
                "without /Names /Dests"
            )
        try:
            self.fix_name_destinations2()
        except Exception:
            _LOG.exception(
                "named destinations fix-up failed; chunks will ship "
                "without /Root/Dests"
            )
        # Release the shared source-/ParentTree flatten (can be large) once
        # every chunk has been cloned.
        self._src_number_tree_map = None
        self._resource_scan_cache = {}
        self._k_node_cache = None
        self._k_skip_enabled = False
        self._k_skip_pending = False
        return self._destination_documents

    # ---------- named destinations (PDFBOX-6283) ----------

    def fix_name_destinations(self) -> None:
        """PDFBOX-6283: fix the destinations in ``/Root/Names/Dests`` by
        creating clones only for the destinations that are in the
        destination documents.

        Mirrors upstream ``Splitter.fixNameDestinations``. Each entry of the
        source name tree whose target page went into a chunk is cloned (shallow
        array copy), retargeted at that chunk's imported page, and written to
        a fresh ``/Names /Dests`` name tree on that chunk. Entries pointing to
        pages outside the split, and broken entries, are dropped.
        """
        from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
            PDDestination,
        )
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination_name_tree_node import (  # noqa: E501
            PDDestinationNameTreeNode,
        )
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (  # noqa: E501
            PDPageDestination,
        )
        from pypdfbox.pdmodel.pd_document_name_dictionary import (
            PDDocumentNameDictionary,
        )

        src_names = self.get_source_document().get_document_catalog().get_names()
        if src_names is None:
            return
        src_dests = src_names.get_dests()
        if src_dests is None:
            return

        dst_tree_as_map_list: list[dict[str, PDPageDestination]] = [
            {} for _ in self._destination_documents
        ]

        # map all named destinations to the pages in the new documents
        src_tree_as_map = src_dests.get_tree_as_map()
        for key, value in src_tree_as_map.items():
            if value is None:
                # happens with file 000671.pdf, entry "Raff1"
                continue
            page_in_tree_dest = value.get_page()
            # find out in which destination document this should be added
            doc_index = (
                None
                if page_in_tree_dest is None
                else self._page_to_doc_num_map.get(id(page_in_tree_dest))
            )
            if doc_index is None:
                # wasn't part of the split
                continue
            # get appropriate mapping
            self._page_dict_map = self._page_dict_maps[doc_index]
            dst_page_dict = self._page_dict_map.get(id(page_in_tree_dest))

            # clone destination
            src_array = value.get_cos_object()
            cloned_destination_array = COSArray(
                [src_array.get(i) for i in range(src_array.size())]
            )
            dst_destination = PDDestination.create(cloned_destination_array)
            dst_destination.set_page(dst_page_dict)

            # add to the tree map of the appropriate destination document
            dst_tree_as_map_list[doc_index][key] = dst_destination

        # Assign all non empty tree maps to the new documents
        for i, dst_tree_as_map in enumerate(dst_tree_as_map_list):
            if not dst_tree_as_map:
                continue
            destination_document = self._destination_documents[i]
            dst_document_catalog = destination_document.get_document_catalog()
            dst_document_name_dictionary = PDDocumentNameDictionary(
                dst_document_catalog
            )
            dst_dests = PDDestinationNameTreeNode()
            dst_document_name_dictionary.set_dests(dst_dests)
            dst_document_catalog.set_names(dst_document_name_dictionary)
            dst_dests.set_names(dst_tree_as_map)

    def fix_name_destinations2(self) -> None:
        """PDFBOX-6283: fix the destinations in ``/Root/Dests`` by creating
        clones only for the destinations that are in the destination
        documents.

        Mirrors upstream ``Splitter.fixNameDestinations2``. Page
        destinations are cloned and retargeted at the chunk that received
        their page (dropped when the page is outside the split); any other
        resolvable destination doesn't reference a specific page and is
        added to every chunk.
        """
        from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
            PDDestination,
        )
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (  # noqa: E501
            PDPageDestination,
        )
        from pypdfbox.pdmodel.pd_document_name_destination_dictionary import (
            PDDocumentNameDestinationDictionary,
        )

        name_destination_dictionary = (
            self.get_source_document().get_document_catalog().get_dests()
        )
        if (
            name_destination_dictionary is None
            or name_destination_dictionary.get_cos_object().size() == 0
        ):
            return

        dst_dests: list[COSDictionary] = [
            COSDictionary() for _ in self._destination_documents
        ]

        # map all named destinations to the pages in the new documents
        for key in list(name_destination_dictionary.get_cos_object().key_set()):
            dest = name_destination_dictionary.get_destination(key.get_name())
            if isinstance(dest, PDPageDestination):
                page_in_tree_dest = dest.get_page()
                # find out in which destination document this should be added
                doc_index = (
                    None
                    if page_in_tree_dest is None
                    else self._page_to_doc_num_map.get(id(page_in_tree_dest))
                )
                if doc_index is None:
                    # wasn't part of the split
                    continue
                # get appropriate mapping
                self._page_dict_map = self._page_dict_maps[doc_index]
                dst_page_dict = self._page_dict_map.get(id(page_in_tree_dest))

                # clone destination
                src_array = dest.get_cos_object()
                cloned_destination_array = COSArray(
                    [src_array.get(i) for i in range(src_array.size())]
                )
                dst_destination = PDDestination.create(cloned_destination_array)
                dst_destination.set_page(dst_page_dict)

                # add to the dictionary of the appropriate destination document
                dst_dests[doc_index].set_item(
                    key, dst_destination.get_cos_object()
                )
            elif dest is not None:
                # add it everywhere, it doesn't reference a specific page
                for dst_dict in dst_dests:
                    dst_dict.set_item(key, dest.get_cos_object())

        # Assign all non empty dictionaries to the new documents
        for i, dst_dict in enumerate(dst_dests):
            if dst_dict.size() == 0:
                continue
            destination_document = self._destination_documents[i]
            dst_document_catalog = destination_document.get_document_catalog()
            # catalog.setDests() doesn't exist upstream, maybe because it
            # feels obsolete
            dst_document_catalog.get_cos_object().set_item(
                _DESTS,
                PDDocumentNameDestinationDictionary(dst_dict).get_cos_object(),
            )

    # ---------- pagination loop ----------

    def _process_pages(self) -> None:
        assert self._source_document is not None
        for page in self._source_document.get_pages():
            page_one_based = self._current_page_number + 1
            if self._start_page <= page_one_based <= self._end_page:
                self.process_page(page)
                self._current_page_number += 1
            else:
                if self._current_page_number > self._end_page:
                    break
                self._current_page_number += 1

    def process_pages(self) -> None:
        """Public-named hook for the pagination loop.

        Mirrors upstream ``processPages`` (protected in Java). Subclasses
        can override either this method or the underscored
        :py:meth:`_process_pages`; the default :py:meth:`split` driver
        always calls the underscored variant so internal callers do not
        accidentally pick up a subclass override they didn't ask for.
        """
        self._process_pages()

    # ---------- subclass hooks (mirror upstream protected methods) ----------

    def split_at_page(self, page_number: int) -> bool:
        """Return ``True`` when a new destination document should be
        created before processing ``page_number`` (0-based). Default
        behaviour matches upstream:

            (page_number + 1 - max(1, start_page)) % split_length == 0
        """
        return (
            page_number + 1 - max(1, self._start_page)
        ) % self._split_length == 0

    def create_new_document(self) -> PDDocument:
        """Build the next destination ``PDDocument``. Copies version and
        a sanitised ``/Info`` dictionary from the source, plus the
        catalog-level entries upstream copies (``/ViewerPreferences``,
        ``/Lang``, ``/MarkInfo``, ``/Metadata``) when the corresponding
        accessors are available."""
        from pypdfbox.pdmodel.pd_document import PDDocument
        from pypdfbox.pdmodel.pd_document_information import (
            PDDocumentInformation,
        )

        assert self._source_document is not None
        document = PDDocument()
        document.get_document().set_version(
            self.get_source_document().get_version()
        )

        src_info = self.get_source_document().get_document_information()
        if src_info is not None:
            src_info_dict = src_info.get_cos_object()
            dst_info_dict = COSDictionary()
            src_catalog_dict = (
                self.get_source_document().get_document_catalog().get_cos_object()
            )
            for key in list(src_info_dict.key_set()):
                value = src_info_dict.get_dictionary_object(key)
                if isinstance(value, COSDictionary):
                    _LOG.warning(
                        "Nested entry for key '%s' skipped in document "
                        "information dictionary",
                        key.get_name(),
                    )
                    if src_catalog_dict is src_info_dict:
                        _LOG.warning("/Root and /Info share the same dictionary")
                    continue
                if key == _TYPE:
                    continue
                dst_info_dict.set_item(key, value)
            document.set_document_information(
                PDDocumentInformation(dst_info_dict)
            )

        dst_catalog = document.get_document_catalog()
        src_catalog = self.get_source_document().get_document_catalog()
        with contextlib.suppress(AttributeError, NotImplementedError):
            dst_catalog.set_viewer_preferences(src_catalog.get_viewer_preferences())
        with contextlib.suppress(AttributeError, NotImplementedError):
            dst_catalog.set_language(src_catalog.get_language())
        with contextlib.suppress(AttributeError, NotImplementedError):
            dst_catalog.set_mark_info(src_catalog.get_mark_info())
        with contextlib.suppress(AttributeError, NotImplementedError):
            dst_catalog.set_metadata(src_catalog.get_metadata())
        # PDFBOX-6203: reset the object keys of everything imported from the
        # source catalog (viewer preferences, metadata, ...) so the writer
        # mints fresh contiguous keys for the split output instead of reusing
        # the source document's object numbers, which would leave gaps in the
        # chunk's cross-reference table. Mirrors upstream
        # ``Splitter.createNewDocument``.
        dst_catalog.get_cos_object().reset_imported_object_keys()
        return document

    def process_page(self, page: PDPage) -> None:
        """Import ``page`` into the current destination document, opening
        a fresh destination first when :meth:`split_at_page` says so."""
        self._create_new_document_if_necessary()
        assert self._current_destination_document is not None

        imported = self._current_destination_document.import_page(page)

        # Materialise the inheritable page-geometry attributes on the
        # imported page dict. Upstream's ``Splitter.processPage`` gets this
        # for free because ``PDDocument.importPage`` (PDDocument.java lines
        # 700-702) explicitly re-applies ``setCropBox`` / ``setMediaBox`` /
        # ``setRotation`` from the *resolved* source values right after the
        # shallow page-dict copy + ``/Parent`` removal. Our port's
        # ``PDDocument.import_page`` does a deep-copy + ``/Parent`` strip but
        # does NOT re-apply those three setters, so a source page that
        # *inherited* its ``/MediaBox`` / ``/CropBox`` / ``/Rotate`` from a
        # page-tree node loses them once detached from the source tree and
        # falls back to the Letter / 0 defaults. Re-applying here keeps the
        # Splitter (and the PageExtractor that delegates to it) byte-for-byte
        # aligned with upstream's importPage materialisation. Each setter is
        # guarded because a malformed source page may raise while resolving
        # the inherited value — upstream would throw, but we prefer to ship
        # the chunk with whatever geometry survived rather than abort the
        # whole split.
        try:
            imported.set_crop_box(page.get_crop_box())
        except Exception as exc:
            _LOG.debug("set_crop_box failed during split: %s", exc)
        try:
            imported.set_media_box(page.get_media_box())
        except Exception as exc:
            _LOG.debug("set_media_box failed during split: %s", exc)
        try:
            imported.set_rotation(page.get_rotation())
        except Exception as exc:
            _LOG.debug("set_rotation failed during split: %s", exc)

        # Mirror upstream: if the source page had a /Resources but the
        # imported one didn't carry it through (because the inheritable
        # path was used), copy the resources dict directly so the chunk
        # is self-sufficient.
        try:
            page_resources = page.get_resources()
        except Exception:
            page_resources = None
        if (
            page_resources is not None
            and not page.get_cos_object().contains_key(_RESOURCES)
        ):
            try:
                imported.set_resources(page_resources)
                _LOG.info("Resources imported in Splitter")
            except Exception:
                pass

        if imported.get_cos_object().contains_key(_B):
            imported.get_cos_object().remove_item(_B)
            _LOG.warning("/B entry (beads) removed by splitter")

        self._process_annotations(page, imported)

        try:
            self._prune_page_resources(imported)
        except Exception:  # pruning must never break a split
            _LOG.exception(
                "resource pruning failed for page %d; full resource "
                "dictionary kept",
                self._current_page_number + 1,
            )

        self._page_dict_map[id(page.get_cos_object())] = imported.get_cos_object()
        self._page_to_doc_num_map[id(page.get_cos_object())] = (
            len(self._destination_documents) - 1
        )

    def get_source_document(self) -> PDDocument:
        assert self._source_document is not None
        return self._source_document

    def get_destination_document(self) -> PDDocument:
        assert self._current_destination_document is not None
        return self._current_destination_document

    # ---------- internals ----------

    def _create_new_document_if_necessary(self) -> None:
        if (
            self.split_at_page(self._current_page_number)
            or self._current_destination_document is None
        ):
            self._current_destination_document = self.create_new_document()
            self._destination_documents.append(self._current_destination_document)
            self._page_dict_map = {}
            self._page_dict_maps.append(self._page_dict_map)
            self._annot_dict_map = {}
            self._annot_dict_maps.append(self._annot_dict_map)
            self._dest_to_fix = []
            self._dest_to_fix_per_chunk.append(self._dest_to_fix)
            self._dest_to_link_map = {}
            self._dest_to_link_map_per_chunk.append(self._dest_to_link_map)
            self._pending_annot_passes = []
            self._pending_annot_passes_per_chunk.append(
                self._pending_annot_passes
            )

    def create_new_document_if_necessary(self) -> None:
        """Public-named hook mirroring upstream ``createNewDocumentIfNecessary``.

        Allocates the next destination document when :py:meth:`split_at_page`
        signals a chunk boundary (or when no destination has been
        created yet). Delegates to :py:meth:`_create_new_document_if_necessary`.
        """
        self._create_new_document_if_necessary()

    def process_annotations(self, imported: PDPage) -> None:
        """Public-named hook for annotation handling.

        Mirrors upstream protected ``processAnnotations(PDPage)`` —
        accepts the imported page only (upstream signature) and delegates
        to the underscored impl with a ``None`` source page. Most
        subclasses will simply override this entry point; the internal
        :py:meth:`_process_annotations` retains its richer signature so
        the default link-destination plumbing still has access to the
        original source page.
        """
        self._process_annotations(imported, imported)

    def _process_annotations(self, source_page: PDPage, imported: PDPage) -> None:
        """Shallow-clone every annotation on ``imported`` so structure-tree
        edits and ``/Parent`` rewrites (e.g. for widget annotations) don't
        bleed back into the source document. Mirrors upstream's
        ``processAnnotations``.

        Signature widgets are dropped entirely (split documents have a
        different byte range, so any contained signature would be invalid
        anyway — see :meth:`_is_signature_widget`).

        Annotation ``/P`` back-pointers are rewritten to the *imported*
        page's COSDictionary so ``ann.get_page() == dst_doc.get_page(N)``
        holds for callers walking the chunk (upstream relies on Java
        default ``Object.equals`` = identity; we mirror that by replacing
        the back-pointer with the cloned page's dict).

        Each cloned annot dict is mapped from BOTH its source-annot id and
        the imported (deep-copy) annot id in ``_annot_dict_map`` so the
        second pass's ``/Popup`` lookup hits regardless of whether the
        deep-copy's cycle-break path returned the source instance or a
        fresh clone for cross-annotation refs in the same page.
        """
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation import (
            PDAnnotation,
        )
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
            PDAnnotationLink,
        )

        try:
            annotations = imported.get_annotations()
        except Exception:
            return
        if not annotations:
            return
        try:
            imported_page_dict = imported.get_cos_object()
        except AttributeError:
            imported_page_dict = None

        # Source-side /Annots array (when available) lets us index into
        # the original annot dicts. Upstream iterates the imported page
        # which still shares /Annots with the source (shallow page copy);
        # our import_page does a deep page-graph clone, so the source
        # array gives us the only handle on the original-identity annot
        # dicts that downstream consumers (e.g. struct-tree clone's OBJR
        # rewrites) expect as keys.
        source_annots_array = None
        try:
            source_page_dict = source_page.get_cos_object()
        except AttributeError:
            source_page_dict = None
        if isinstance(source_page_dict, COSDictionary):
            value = source_page_dict.get_dictionary_object(_ANNOTS)
            if isinstance(value, COSArray):
                source_annots_array = value

        cloned: list[PDAnnotation] = []
        for index, ann in enumerate(annotations):
            ann_dict = ann.get_cos_object()

            # Skip signature widgets entirely. Either the widget IS the
            # field (merged) and /FT=Sig, or its /Parent chain leads to
            # a /FT=Sig field, or it has /V pointing at a signature dict.
            if self._is_signature_widget(ann_dict):
                self._signatures_dropped = True
                continue

            cloned_dict = COSDictionary(list(ann_dict.entry_set()))
            self._annot_dict_map[id(ann_dict)] = cloned_dict
            # Map the source-side annot dict too — downstream consumers
            # (struct-tree clone's OBJR lookup, popup back-ref rewriting)
            # use source ids as keys.
            if source_annots_array is not None and index < source_annots_array.size():
                source_ann_dict = source_annots_array.get_object(index)
                if isinstance(source_ann_dict, COSDictionary):
                    self._annot_dict_map[id(source_ann_dict)] = cloned_dict
            cloned_ann = PDAnnotation.create(cloned_dict)
            cloned.append(cloned_ann)

            # Drop /Parent for widget annotations to avoid orphan /Parent
            # references into form fields that didn't follow the split.
            try:
                subtype = cloned_dict.get_name(_SUBTYPE)
            except AttributeError:
                subtype = None
            if subtype == "Widget" and cloned_dict.contains_key(_PARENT):
                cloned_dict.remove_item(_PARENT)

            # Link annotations: clone /Dest (or the action's /D) and
            # remember the cloned destination so the post-pass can either
            # rewrite its /D[0] to the cloned destination page or null it
            # out when the target page is in a different chunk.
            #
            # Pass the *source* annot dict (when available) so the staging
            # step can resolve the destination's target page through the
            # un-deep-copied source object graph. ``import_page``'s deep-copy
            # replaces each indirect-ref target with a fresh COSDictionary,
            # so reading ``/A /D [0]`` off ``cloned_ann`` (which wraps the
            # imported annot's clone) would lose source-page identity and
            # break the post-pass ``_page_dict_map`` lookup.
            if isinstance(cloned_ann, PDAnnotationLink):
                source_link_dict: COSDictionary | None = None
                if (
                    source_annots_array is not None
                    and index < source_annots_array.size()
                ):
                    candidate = source_annots_array.get_object(index)
                    if isinstance(candidate, COSDictionary):
                        source_link_dict = candidate
                self._stage_link_destination(
                    cloned_ann,
                    source_page.get_cos_object(),
                    source_link_dict,
                )

            # Rewrite the cloned annot's /P back-pointer to the imported
            # page dict whenever the source had a page back-ref. Mirrors
            # upstream ``processAnnotations`` (Splitter.java line 921-924):
            # ``if (annotation.getPage() != null) annotationClone.setPage(imported)``.
            # Without this, the deep-copy cycle-break path in
            # ``_deep_copy_cos`` leaves /P pointing at the *source* page,
            # breaking annotation/page identity for chunk consumers.
            if (
                imported_page_dict is not None
                and hasattr(ann, "get_page")
                and ann.get_page() is not None
            ):
                cloned_ann.set_page(imported_page_dict)

        # Second pass (popup/markup linkage) is deferred to
        # :meth:`_finalize_annotation_links`. Running it inline here would
        # only see this page's contribution to ``_annot_dict_map`` — a
        # markup on chunk page A whose ``/Popup`` lives on chunk page B
        # would be processed before page B's first pass populated the
        # cloned popup dict, so the second-pass lookup would miss and
        # leave the markup's ``/Popup`` pointing at a deep-copy dict that
        # isn't the chunk's actual popup (wave 1373). Stash the per-page
        # context and drain after every page in the chunk has been
        # imported.
        self._pending_annot_passes.append(
            (cloned, source_annots_array, imported_page_dict)
        )

        with contextlib.suppress(Exception):
            imported.set_annotations(cloned)

    def _finalize_annotation_links(self) -> None:
        """Run the deferred markup/popup second pass for every page in
        the current chunk.

        Mirrors upstream ``processAnnotations`` second loop
        (Splitter.java lines 926-967) — rewrites ``/Popup`` on markup
        annots to the chunk's cloned popup dict, ``/Parent`` on popups
        to the chunk's cloned markup dict, and clones orphan popups (not
        in any page's ``/Annots``) re-linking them via ``/Popup`` ↔
        ``/Parent`` with ``/P`` pinned to the markup's imported page.
        Defers the second-pass walk relative to upstream so the lookup
        sees ``_annot_dict_map`` populated by *every* page in the chunk,
        not just the page that hosts the markup — without this, a markup
        on page A whose popup lives on page B of the same chunk would
        leave the markup's ``/Popup`` pointing at the deep-copied source
        popup instead of the chunk's cloned popup.

        Popup-side ``/Parent`` resolution still falls back to nulling the
        entry when the markup annotation didn't follow the split, per
        upstream's ``setItem(PARENT, null)`` behaviour for orphan markups.
        """
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
            PDAnnotationMarkup,
        )
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation_popup import (
            PDAnnotationPopup,
        )

        for entry in self._pending_annot_passes:
            cloned, source_annots_array, imported_page_dict = entry
            clone_index = 0
            for ann in cloned:
                ann_dict = ann.get_cos_object()
                source_ann_dict: COSBase | None = None
                if source_annots_array is not None:
                    while clone_index < source_annots_array.size():
                        candidate = source_annots_array.get_object(clone_index)
                        clone_index += 1
                        if not isinstance(candidate, COSDictionary):
                            continue
                        if self._is_signature_widget(candidate):
                            continue
                        source_ann_dict = candidate
                        break

                if isinstance(ann, PDAnnotationMarkup):
                    source_popup_value: Any = None
                    if isinstance(source_ann_dict, COSDictionary):
                        source_popup_value = (
                            source_ann_dict.get_dictionary_object(_POPUP)
                        )
                    popup_value = (
                        source_popup_value
                        if isinstance(source_popup_value, COSDictionary)
                        else ann_dict.get_dictionary_object(_POPUP)
                    )
                    if isinstance(popup_value, COSDictionary):
                        cloned_popup = self._annot_dict_map.get(
                            id(popup_value)
                        )
                        if cloned_popup is not None:
                            ann_dict.set_item(_POPUP, cloned_popup)
                        else:
                            # Orphan popup — not in any /Annots array of
                            # any chunk page. Clone it, hook /P back to
                            # the markup's imported page, re-link
                            # Popup ↔ Parent. Mirrors upstream
                            # ``Splitter.java:944-954``.
                            cloned_popup = COSDictionary(
                                list(popup_value.entry_set())
                            )
                            self._annot_dict_map[id(popup_value)] = (
                                cloned_popup
                            )
                            popup_clone = PDAnnotationPopup(cloned_popup)
                            popup_clone.set_parent(ann_dict)
                            ann_dict.set_item(_POPUP, cloned_popup)
                            if (
                                imported_page_dict is not None
                                and popup_clone.get_page() is not None
                            ):
                                popup_clone.set_page(imported_page_dict)

                if isinstance(ann, PDAnnotationPopup):
                    source_parent_value: Any = None
                    if isinstance(source_ann_dict, COSDictionary):
                        source_parent_value = (
                            source_ann_dict.get_dictionary_object(_PARENT)
                        )
                    parent_value = (
                        source_parent_value
                        if isinstance(source_parent_value, COSDictionary)
                        else ann_dict.get_dictionary_object(_PARENT)
                    )
                    if isinstance(parent_value, COSDictionary):
                        cloned_markup = self._annot_dict_map.get(
                            id(parent_value)
                        )
                        if cloned_markup is not None:
                            ann_dict.set_item(_PARENT, cloned_markup)
                        else:
                            ann_dict.remove_item(_PARENT)

    @staticmethod
    def _is_signature_widget(ann_dict: COSDictionary) -> bool:
        """Return ``True`` when ``ann_dict`` is a Widget annotation that
        is part of a signature field. Tested in three ways:

        - the widget IS the field (merged form field+widget) and
          ``/FT == /Sig``;
        - the widget's ``/Parent`` chain ends at a field with
          ``/FT == /Sig``;
        - ``/V`` resolves to a signature dictionary
          (``/Type == /Sig`` or contains ``/ByteRange``).

        Split documents have a different byte range than the source, so
        any signature carried into them would be invalid; upstream's
        approach is to leave AcroForm out of the chunk catalog entirely
        (we mirror that in :meth:`_scrub_acroform`), but defensively
        dropping the widget itself avoids orphan annotations on the
        page when an AcroForm cleanup is incomplete.
        """
        try:
            subtype = ann_dict.get_name(_SUBTYPE)
        except AttributeError:
            return False
        if subtype != "Widget":
            return False

        # Direct merged widget+field: /FT lives on the widget dict itself.
        ft = ann_dict.get_name(_FT)
        if ft == "Sig":
            return True

        # Walk /Parent chain.
        seen: set[int] = set()
        parent = ann_dict.get_dictionary_object(_PARENT)
        while isinstance(parent, COSDictionary) and id(parent) not in seen:
            seen.add(id(parent))
            ft = parent.get_name(_FT)
            if ft == "Sig":
                return True
            if ft is not None:
                # Field with a non-Sig FT — definitely not a sig widget.
                return False
            parent = parent.get_dictionary_object(_PARENT)

        # /V signature dictionary check (handles fields with no /FT but a
        # populated signature value — unusual but seen in the wild).
        v = ann_dict.get_dictionary_object(_V)
        if isinstance(v, COSDictionary):
            v_type = v.get_name(_TYPE)
            if v_type == "Sig":
                return True
            if v.contains_key(COSName.get_pdf_name("ByteRange")):
                return True
        return False

    def _scrub_acroform(self, destination_document: PDDocument) -> None:
        """Remove signature-bearing state from the destination catalog.
        Mirrors upstream's "split documents lose AcroForm" behaviour:

        - if any signature widget was dropped, clear ``/SigFlags`` and
          remove signature-typed fields from the chunk's ``/AcroForm
          /Fields`` array;
        - if the resulting fields list is empty, remove ``/AcroForm``
          from the catalog entirely.

        Upstream's :class:`Splitter` doesn't carry AcroForm into chunks
        at all because :meth:`create_new_document` only copies a small
        whitelist of catalog entries (``/ViewerPreferences``, ``/Lang``,
        ``/MarkInfo``, ``/Metadata``). We follow that approach but also
        defensively scrub if a subclass added ``/AcroForm`` via an
        override.
        """
        catalog = destination_document.get_document_catalog()
        cos_catalog = catalog.get_cos_object()
        acroform_dict = cos_catalog.get_dictionary_object(_ACROFORM)
        if not isinstance(acroform_dict, COSDictionary):
            return

        # Always clear /SigFlags — split chunks have invalid signatures.
        if acroform_dict.contains_key(_SIG_FLAGS):
            acroform_dict.remove_item(_SIG_FLAGS)

        fields = acroform_dict.get_dictionary_object(_FIELDS)
        if isinstance(fields, COSArray):
            kept = COSArray()
            for i in range(fields.size()):
                field = fields.get_object(i)
                if isinstance(field, COSDictionary) and field.get_name(_FT) == "Sig":
                    continue
                if field is not None:
                    kept.add(field)
            if kept.size() == 0:
                acroform_dict.remove_item(_FIELDS)
            else:
                acroform_dict.set_item(_FIELDS, kept)

        # If AcroForm is now effectively empty, drop it.
        remaining_keys = [
            k for k in acroform_dict.key_set() if k != _TYPE
        ]
        if not remaining_keys:
            cos_catalog.remove_item(_ACROFORM)

    # ---------- unused-resource pruning (pypdfbox extension) ----------

    def _prune_page_resources(self, imported: PDPage) -> None:
        """Rebuild ``imported``'s ``/Resources`` with only the entries its
        content actually references.

        pypdfbox divergence from upstream ``Splitter`` (see CHANGES.md),
        applied unconditionally: upstream copies the page's — possibly
        inherited, document-wide — resource dictionary wholesale, so a
        one-page split of a document whose pages share a page-tree-level
        ``/Resources`` weighs as much as the whole source. Pruning keeps
        only the ``/Font``, ``/XObject``, ``/ExtGState``, ``/ColorSpace``,
        ``/Pattern``, ``/Shading``, and ``/Properties`` entries the page
        can actually reach.

        The used-name sets are gathered by tokenizing the page's content
        streams and every dependent stream that can (or, per fallback
        behaviour in real-world viewers, may) resolve names against the
        page's resource dictionary: form XObjects, tiling patterns,
        Type 3 ``/CharProcs``, and annotation appearance streams that
        lack their own ``/Resources``. Discovery runs to a fixpoint so a
        form XObject referenced only from another form still keeps its
        dependencies. Any tokenization failure propagates to the caller,
        which keeps the full dictionary (conservative default).

        A fresh ``COSDictionary`` is always installed — the incoming
        ``/Resources`` may be the *source document's* shared dictionary
        (inherited-resources path), which must not be mutated.
        """
        from pypdfbox.cos import COSStream

        page_dict = imported.get_cos_object()
        res_dict = page_dict.get_dictionary_object(_RESOURCES)
        if not isinstance(res_dict, COSDictionary):
            return

        used: dict[str, set[str]] = {c: set() for c in _PRUNABLE_CATEGORIES}

        def merge(found: dict[str, frozenset[str]]) -> None:
            for category, names in found.items():
                if names:
                    used[category].update(names)

        def scan(data: bytes) -> None:
            # The scan is a pure function of the decoded bytes, and form
            # XObjects, patterns, glyph procs and appearance streams are
            # routinely shared by many pages (import_page copies them, so
            # identity is not stable). Tokenize each distinct byte string
            # once per split() run.
            if not isinstance(data, bytes):
                data = bytes(data)
            cache = self._resource_scan_cache
            found = cache.get(data)
            if found is None:
                found = self._scan_resource_names(data)
                cache[data] = found
            merge(found)

        def scan_stream(stream: COSStream) -> None:
            scan(stream.to_byte_array())

        def resolve(category: str, name: str) -> COSBase | None:
            sub = res_dict.get_dictionary_object(COSName.get_pdf_name(category))
            if isinstance(sub, COSDictionary):
                return sub.get_dictionary_object(COSName.get_pdf_name(name))
            return None

        scan(imported.get_contents())
        for ap_stream in self._iter_appearance_streams(page_dict):
            if not ap_stream.contains_key(_RESOURCES):
                scan_stream(ap_stream)

        # Fixpoint walk: streams reachable through used resources may pull
        # further names from the page dictionary.
        scanned: set[tuple[str, str]] = set()
        progress = True
        while progress:
            progress = False
            for name in list(used["XObject"]):
                if ("XObject", name) in scanned:
                    continue
                scanned.add(("XObject", name))
                progress = True
                xobj = resolve("XObject", name)
                if (
                    isinstance(xobj, COSStream)
                    and xobj.get_name(_SUBTYPE) == "Form"
                ):
                    scan_stream(xobj)
            for name in list(used["Pattern"]):
                if ("Pattern", name) in scanned:
                    continue
                scanned.add(("Pattern", name))
                progress = True
                pattern = resolve("Pattern", name)
                if isinstance(pattern, COSStream):
                    scan_stream(pattern)
            for name in list(used["Font"]):
                if ("Font", name) in scanned:
                    continue
                scanned.add(("Font", name))
                progress = True
                font = resolve("Font", name)
                if (
                    isinstance(font, COSDictionary)
                    and font.get_name(_SUBTYPE) == "Type3"
                ):
                    char_procs = font.get_dictionary_object(_CHAR_PROCS)
                    if isinstance(char_procs, COSDictionary):
                        for glyph_key in list(char_procs.key_set()):
                            proc = char_procs.get_dictionary_object(glyph_key)
                            if isinstance(proc, COSStream):
                                scan_stream(proc)

        pruned = COSDictionary()
        for key in list(res_dict.key_set()):
            category = key.get_name()
            if category in used:
                sub = res_dict.get_dictionary_object(key)
                if isinstance(sub, COSDictionary):
                    kept = COSDictionary()
                    for sub_key in list(sub.key_set()):
                        if sub_key.get_name() in used[category]:
                            kept.set_item(sub_key, sub.get_item(sub_key))
                    if kept.size() > 0:
                        pruned.set_item(key, kept)
                    continue
            # ProcSet, unknown categories, and non-dictionary values are
            # kept wholesale — pruning only what we can prove is name-keyed.
            pruned.set_item(key, res_dict.get_item(key))
        page_dict.set_item(_RESOURCES, pruned)

    @staticmethod
    def _scan_resource_names(data: bytes) -> dict[str, frozenset[str]]:
        """Return ``{category: names}`` for the resource names ``data``
        hands to name-consuming operators. Uses the regex fast path when the
        stream stays inside its grammar subset, else the exact
        ``PDFStreamParser`` scan; both yield the same names. Parse errors
        propagate (the caller then keeps the full resource dictionary)."""
        fast = _fast_scan_resource_names(data)
        if fast is None:
            return Splitter._exact_scan_resource_names(data)
        return {
            category: frozenset(
                COSName.get_pdf_name(raw).get_name() for raw in names
            )
            for category, names in fast.items()
        }

    @staticmethod
    def _exact_scan_resource_names(data: bytes) -> dict[str, frozenset[str]]:
        """Reference scan: tokenize ``data`` with ``PDFStreamParser`` and
        collect the resource names used by ``Tf`` / ``Do`` / ``gs`` /
        ``CS`` / ``cs`` / ``SCN`` / ``scn`` / ``sh`` / ``BDC`` / ``DP`` and
        inline-image colour spaces."""
        from pypdfbox.pdfparser.pdf_stream_parser import (
            Operator,
            PDFStreamParser,
        )

        used: dict[str, set[str]] = {c: set() for c in _PRUNABLE_CATEGORIES}
        operands: list[Any] = []
        for token in PDFStreamParser.from_bytes(data).parse():
            if not isinstance(token, Operator):
                operands.append(token)
                continue
            op = token.get_name()
            if op == "Tf" and operands and isinstance(operands[0], COSName):
                used["Font"].add(operands[0].get_name())
            elif op == "Do" and operands and isinstance(operands[0], COSName):
                used["XObject"].add(operands[0].get_name())
            elif op == "gs" and operands and isinstance(operands[0], COSName):
                used["ExtGState"].add(operands[0].get_name())
            elif op in ("CS", "cs") and operands and isinstance(
                operands[0], COSName
            ):
                used["ColorSpace"].add(operands[0].get_name())
            elif op in ("SCN", "scn") and operands and isinstance(
                operands[-1], COSName
            ):
                used["Pattern"].add(operands[-1].get_name())
            elif op == "sh" and operands and isinstance(operands[0], COSName):
                used["Shading"].add(operands[0].get_name())
            elif op in ("BDC", "DP") and len(operands) >= 2 and isinstance(
                operands[1], COSName
            ):
                used["Properties"].add(operands[1].get_name())
            elif op in ("BI", "ID") and token.image_parameters is not None:
                # Inline image: a named (non-device) colour space
                # resolves against the page's /ColorSpace resources.
                for cs_key in ("CS", "ColorSpace"):
                    cs_value = token.image_parameters.get_dictionary_object(
                        COSName.get_pdf_name(cs_key)
                    )
                    if isinstance(cs_value, COSName):
                        used["ColorSpace"].add(cs_value.get_name())
            operands = []
        return {category: frozenset(names) for category, names in used.items()}

    @staticmethod
    def _iter_appearance_streams(page_dict: COSDictionary) -> list[Any]:
        """Collect every appearance-stream ``COSStream`` reachable via the
        page's ``/Annots`` → ``/AP`` entries (both direct streams and
        state-keyed sub-dictionary streams)."""
        from pypdfbox.cos import COSStream

        streams: list[Any] = []
        annots = page_dict.get_dictionary_object(_ANNOTS)
        if not isinstance(annots, COSArray):
            return streams
        for i in range(annots.size()):
            annot = annots.get_object(i)
            if not isinstance(annot, COSDictionary):
                continue
            ap = annot.get_dictionary_object(_AP)
            if not isinstance(ap, COSDictionary):
                continue
            for ap_key in list(ap.key_set()):
                value = ap.get_dictionary_object(ap_key)
                if isinstance(value, COSStream):
                    streams.append(value)
                elif isinstance(value, COSDictionary):
                    for state_key in list(value.key_set()):
                        state = value.get_dictionary_object(state_key)
                        if isinstance(state, COSStream):
                            streams.append(state)
        return streams

    def _stage_link_destination(
        self,
        link: Any,
        source_page_dict: COSDictionary,
        source_link_dict: COSDictionary | None = None,
    ) -> None:
        """Clone the link's destination array, install the clone, and
        remember it for the :meth:`fix_destinations` post-pass.

        Mirrors upstream's ``destToFixMap`` book-keeping. Named
        destinations are kept as-is (PDFBOX-6283: the chunk's named
        destinations are rebuilt by :meth:`fix_name_destinations` /
        :meth:`fix_name_destinations2`), except when the name contains a
        NUL character (a "broken string", e.g. 0xAD decoded to 0 in
        PDFBOX-5840-410609.pdf): those are resolved via the source catalog's
        ``find_named_destination_page`` (``/Names /Dests`` name tree first,
        then legacy catalog ``/Dests``) into a concrete
        :class:`PDPageDestination`, because the name would no longer match
        the entry in the chunk's name tree.

        ``source_link_dict`` is the *un-deep-copied* link annot dict from
        the source document. When supplied, the destination's target page
        is resolved through that source dict so the captured page-dict
        identity stays stable across ``import_page``'s deep-copy. Upstream
        gets this for free (its ``import_page`` does a shallow page-graph
        copy that preserves indirect-ref identities); our deep-copy clones
        each indirect-ref target into a fresh ``COSDictionary``, so reading
        the destination off the imported link would point at that fresh
        dict instead of the source page (wave 1294).
        """
        from pypdfbox.pdmodel.interactive.action.pd_action_go_to import (
            PDActionGoTo,
        )
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
            PDAnnotationLink,
        )
        from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
            PDDestination,
        )
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (  # noqa: E501
            PDNamedDestination,
        )
        from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (  # noqa: E501
            PDPageDestination,
        )

        # Prefer the source-side link wrapper for destination resolution so
        # we don't trip over ``import_page``'s deep-copied page targets. Fall
        # back to the cloned link when no source dict was supplied (e.g.
        # subclass override that calls this directly).
        if source_link_dict is not None:
            resolution_link: Any = PDAnnotationLink(source_link_dict)
        else:
            resolution_link = link

        try:
            src_destination = resolution_link.get_destination()
        except Exception:
            _LOG.warning(
                "Incorrect destination in link annotation on page %d "
                "is removed",
                self._current_page_number + 1,
            )
            link.set_destination(None)
            return

        action = None
        if src_destination is None:
            try:
                action = resolution_link.get_action()
            except Exception:
                action = None
            if isinstance(action, PDActionGoTo):
                try:
                    src_destination = action.get_destination()
                except Exception:
                    _LOG.warning(
                        "GoToAction with incorrect destination in link "
                        "annotation on page %d is removed",
                        self._current_page_number + 1,
                    )
                    link.set_action(None)
                    src_destination = None

        # PDFBOX-5840 / PDFBOX-6283: keep the named destination (the chunk's
        # /Names /Dests and /Root/Dests are rebuilt by
        # ``fix_name_destinations`` / ``fix_name_destinations2``). In a few
        # cases, e.g. in PDFBOX-5840-410609.pdf, 0xAD becomes 0 so the name
        # would no longer match the entry in the new name tree, so we replace
        # the name with the actual destination.
        #
        # PDActionGoTo.get_destination() / PDAnnotationLink.get_destination()
        # return a ``PDNamedDestination`` for a name/string ``/D`` (upstream
        # parity — see wave 1491). (A bare ``str`` is tolerated defensively
        # for any caller still handing one in.)
        if isinstance(src_destination, str):
            src_destination = PDNamedDestination(src_destination)
        if isinstance(src_destination, PDNamedDestination):
            named_destination_string = src_destination.get_named_destination()
            if (
                named_destination_string is not None
                and "\x00" in named_destination_string
            ):
                try:
                    src_catalog = self.get_source_document().get_document_catalog()
                    src_destination = src_catalog.find_named_destination_page(
                        src_destination
                    )
                except Exception:
                    src_destination = None

        # Skip non-page destinations — including kept named destinations,
        # which the cloned link already carries verbatim.
        if not isinstance(src_destination, PDPageDestination):
            return

        src_dest_array = src_destination.get_cos_object()
        if not isinstance(src_dest_array, COSArray):
            return

        # Snapshot the *source* target-page dict before any cloning. This
        # is what ``_page_dict_map`` is keyed by (every ``process_page``
        # stores ``id(page.get_cos_object())``); reading the deep-copied
        # ``cloned_array.get_object(0)`` later would miss because the deep
        # copy minted a fresh dict per indirect-ref target.
        source_target_page_dict: COSDictionary | None = None
        try:
            candidate_target = src_destination.get_page()
            if isinstance(candidate_target, COSDictionary):
                source_target_page_dict = candidate_target
        except Exception:
            source_target_page_dict = None

        # Clone destination as a flat shallow array (just rewrite /D[0]
        # later — leave fit / params alone).
        cloned_array = COSArray()
        for i in range(src_dest_array.size()):
            cloned_array.add(src_dest_array.get(i))
        try:
            cloned_destination = PDDestination.create(cloned_array)
        except Exception:
            return
        if cloned_destination is None:
            return

        # Re-read the *cloned* link's action when we have one, so the
        # cloned destination installs onto the chunk-side annot rather
        # than mutating the source link.
        cloned_action = None
        if action is not None:
            try:
                cloned_action = link.get_action()
            except Exception:
                cloned_action = None

        if isinstance(action, PDActionGoTo):
            base_action_dict = (
                cloned_action.get_cos_object()
                if isinstance(cloned_action, PDActionGoTo)
                else action.get_cos_object()
            )
            cloned_action_dict = COSDictionary(list(base_action_dict.entry_set()))
            cloned_action_wrapper = PDActionGoTo(cloned_action_dict)
            cloned_action_wrapper.set_destination(cloned_destination)
            with contextlib.suppress(Exception):
                link.set_action(cloned_action_wrapper)
        else:
            with contextlib.suppress(Exception):
                link.set_destination(cloned_destination)

        self._dest_to_fix.append(
            (cloned_array, source_page_dict, source_target_page_dict)
        )
        # Wave-1379: remember which cloned link annotation hosts this
        # destination so the post-pass can rewrite it into a /A GoToR action
        # when the cross-chunk resolver opts in. Defaults to a no-op when
        # the resolver isn't registered (the link reference simply isn't
        # consulted).
        with contextlib.suppress(AttributeError):
            self._dest_to_link_map[id(cloned_array)] = link.get_cos_object()

    # ---------- destination fix-up post-pass ----------

    def fix_destinations(self, destination_document: PDDocument) -> None:
        """Rewrite or null out staged ``/Dest`` arrays per upstream's
        ``fixDestinations``. For each cloned destination array:

        - if the *source page that hosts the link* doesn't live in this
          chunk, leave it (caller already discarded the link as part of
          a different chunk's import);
        - if the *destination page the link points to* lives in this
          chunk, rewrite the array's first slot to the cloned page dict;
        - otherwise null out the array's first slot so the destination
          becomes a no-op rather than dangling into the source doc.
        """
        if not self._dest_to_fix:
            return
        from pypdfbox.cos import COSNull

        page_tree = destination_document.get_pages()
        for entry in self._dest_to_fix:
            # Backwards-compatible unpacking — older subclass overrides that
            # called the pre-wave-1294 two-tuple form still work.
            if len(entry) == 3:
                cloned_array, source_page_dict, source_target_page_dict = entry
            else:  # pragma: no cover - legacy two-tuple form
                cloned_array, source_page_dict = entry  # type: ignore[misc]
                source_target_page_dict = None
            # Where did the link itself originate? If the host page isn't
            # in this chunk, skip — another chunk owns this rewrite.
            cloned_host_dict = self._page_dict_map.get(id(source_page_dict))
            if cloned_host_dict is None:
                continue
            if page_tree.index_of(cloned_host_dict) < 0:
                continue
            # Resolve the target page through the source-side snapshot
            # captured at staging time (wave 1294) — the deep-copied
            # cloned_array[0] doesn't keep source-page identity, so we
            # can't key ``_page_dict_map`` off it.
            target_source: COSDictionary | None = source_target_page_dict
            if target_source is None and cloned_array.size() > 0:
                # Legacy fallback: if no source snapshot, try the cloned
                # array's first entry. Matches pre-wave-1294 behavior.
                raw_target = cloned_array.get_object(0)
                if isinstance(raw_target, COSDictionary):
                    target_source = raw_target
            if target_source is None:
                # Integer / null target — nothing to fix.
                continue
            cloned_target = self._page_dict_map.get(id(target_source))
            if cloned_target is not None and page_tree.index_of(cloned_target) >= 0:
                cloned_array.set(0, cloned_target)
            else:
                # Cross-chunk target. Wave-1379 cross-chunk resolver path:
                # when registered, let the caller retarget the link as a
                # /A GoToR action pointing at the chunk file that owns
                # ``target_source``. Falls back to the historical null-out
                # behaviour when the resolver returns ``None`` (or isn't
                # registered).
                if not self._rewrite_cross_chunk_destination(
                    cloned_array, target_source
                ):
                    cloned_array.set(0, COSNull.NULL)

    def _rewrite_cross_chunk_destination(
        self,
        cloned_array: COSArray,
        source_target_page_dict: COSDictionary,
    ) -> bool:
        """Apply the registered cross-chunk destination resolver to a single
        out-of-chunk destination array. Returns ``True`` when the resolver
        opted into a rewrite (in which case ``cloned_array``'s ``/D[0]``
        slot has been replaced with the integer page index inside the
        target file and the hosting link annotation's ``/A`` has been set
        to a fresh ``GoToR`` action), or ``False`` when no resolver is
        registered / the resolver returned ``None`` (null-out fallback
        path).
        """
        resolver = self._cross_chunk_destination_resolver
        if resolver is None:
            return False
        try:
            resolved = resolver(source_target_page_dict)
        except Exception:  # defensive: resolver is caller code
            _LOG.exception(
                "cross_chunk_destination_resolver raised for target page; "
                "falling back to null-out"
            )
            return False
        if resolved is None:
            return False

        if isinstance(resolved, tuple):
            if len(resolved) != 2:
                _LOG.warning(
                    "cross_chunk_destination_resolver returned a tuple of "
                    "length %d; expected 2 (filename, page_index). Falling "
                    "back to null-out.",
                    len(resolved),
                )
                return False
            file_name_obj, page_index_obj = resolved
            if not isinstance(file_name_obj, str) or not isinstance(
                page_index_obj, int
            ):
                _LOG.warning(
                    "cross_chunk_destination_resolver returned non-(str,int) "
                    "tuple; falling back to null-out"
                )
                return False
            file_name = file_name_obj
            page_index = page_index_obj
        elif isinstance(resolved, str):
            file_name = resolved
            page_index = 0
        else:
            _LOG.warning(
                "cross_chunk_destination_resolver returned unsupported type "
                "%s; falling back to null-out",
                type(resolved).__name__,
            )
            return False

        from pypdfbox.pdmodel.interactive.action.pd_action_remote_go_to import (
            PDActionRemoteGoTo,
        )

        # Replace ``/D[0]`` with the integer page index inside the target
        # file. The remaining slots (fit type + coordinates) are preserved
        # so explicit-fit-mode destinations (XYZ / FitH / FitV / FitB /
        # FitBH / FitBV / FitR) round-trip through the rewrite unchanged.
        cloned_array.set(0, COSInteger.get(page_index))

        link_dict = self._dest_to_link_map.get(id(cloned_array))
        if link_dict is None:
            # No link record — the destination is orphaned (e.g. from a
            # legacy /Dests entry promoted into a chunk by a subclass).
            # Mutating ``cloned_array`` alone is the best we can do.
            return True

        # Build a fresh /A GoToR action carrying the file + dest array.
        # Mirrors upstream's typical user pattern: an explicit
        # ``PDActionRemoteGoTo`` with ``/F`` (string) + ``/D`` (array).
        action = PDActionRemoteGoTo()
        action.set_file(file_name)
        action.set_destination(cloned_array)
        link_dict.set_item(
            COSName.get_pdf_name("A"), action.get_cos_object()
        )
        # Remove the historical /Dest if present — /A takes precedence
        # per PDF 32000-1 §12.5.6.5 Table 173 but a redundant /Dest
        # confuses some viewers (Foxit) into picking the now-stale array.
        link_dict.remove_item(COSName.get_pdf_name("Dest"))
        return True

    # ---------- structure-tree cloning ----------

    def clone_structure_tree(self, destination_document: PDDocument) -> None:
        """Clone the source ``/StructTreeRoot`` into ``destination_document``,
        keeping only structure elements that pertain to pages in this
        chunk. Mirrors upstream ``Splitter.cloneStructureTree``.

        Uses the per-chunk ``_page_dict_map`` / ``_annot_dict_map`` to
        translate page and annotation references; produces a fresh
        ``/ParentTree``, ``/IDTree``, ``/RoleMap``, and ``/ClassMap`` for
        the chunk.
        """
        from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_tree_root import (
            PDStructureElementNameTreeNode,
            PDStructureElementNumberTreeNode,
            PDStructureTreeRoot,
        )

        src_catalog = self.get_source_document().get_document_catalog()
        src_struct_root = src_catalog.get_struct_tree_root()
        if src_struct_root is None:
            return

        # Reset per-chunk struct-clone state. Note: ``_id_set`` and
        # ``_role_set`` are intentionally NOT reset here — upstream
        # initialises them once in ``split()`` and lets them accumulate
        # across chunks (Splitter.java lines 136-137 vs line 200), so a
        # chunk's /RoleMap and /IDTree can include entries first
        # introduced by an earlier chunk. Resetting per chunk produced
        # off-by-one role-map narrowing on PDFBOX-5792-240045.pdf (wave
        # 1295).
        self._struct_dict_map = {}

        dst_struct_root = PDStructureTreeRoot()
        dst_struct_root_cos = dst_struct_root.get_cos_object()
        page_tree = destination_document.get_pages()

        # Snapshot the chunk's pages once and, when the page tree is a real
        # iterable/mappable tree, precompute a {id(page_dict): index} map so
        # _k_clone_dictionary can test chunk membership in O(1) rather than
        # re-walking the tree per struct element (the old page_tree.index_of
        # scan was O(chunk)). Foreign / mock page trees (used by direct unit
        # tests) that aren't iterable — or whose pages don't expose
        # get_cos_object — fall back to the upstream index_of path.
        pages: list[Any] | None
        try:
            pages = list(page_tree)
        except TypeError:
            pages = None
        page_index_map: dict[int, int] | None = None
        if pages is not None:
            try:
                page_index_map = {
                    id(page.get_cos_object()): idx
                    for idx, page in enumerate(pages)
                }
            except Exception:  # foreign page object; use index_of
                page_index_map = None
        if page_index_map is not None:
            self._page_index_by_id = page_index_map
            self._page_index_tree_id = id(page_tree)
        else:
            self._page_index_by_id = {}
            self._page_index_tree_id = None
            if pages is None:
                pages = [page_tree.get(i) for i in range(len(page_tree))]

        # Clone /K, also fills _struct_dict_map.
        src_k = src_struct_root.get_cos_object().get_dictionary_object(_K)
        if self._k_skip_pending:
            self._k_skip_pending = False
            self._build_k_skip_info(src_k)
        cloned_k = self._k_create_clone(
            src_k, dst_struct_root_cos, None, page_tree
        )
        if cloned_k is not None:
            dst_struct_root_cos.set_item(_K, cloned_k)

        # Build a fresh /ParentTree containing only entries referenced by
        # this chunk's pages. The source /ParentTree is immutable during
        # split(), so flatten it exactly once and share the read-only map
        # across every chunk (was re-flattened per chunk — O(chunks * n)).
        src_parent_tree = src_struct_root.get_parent_tree()
        if src_parent_tree is not None:
            if self._src_number_tree_map is None:
                self._src_number_tree_map = self._get_number_tree_as_map(
                    src_parent_tree
                )
            src_numbers = self._src_number_tree_map
        else:
            src_numbers = {}
        dst_numbers: dict[int, COSBase] = {}

        for page in pages:
            try:
                sp1 = page.get_struct_parents()
            except Exception:
                sp1 = -1
            if sp1 != -1:
                self.clone_tree_element(src_numbers, dst_numbers, sp1)
            try:
                annots = page.get_annotations()
            except Exception:
                annots = []
            for ann in annots:
                try:
                    sp2 = ann.get_struct_parent()
                except Exception:
                    sp2 = -1
                if sp2 != -1:
                    self.clone_tree_element(src_numbers, dst_numbers, sp2)
                # Mirrors upstream Splitter.cloneStructureTree (Java
                # line 229-234): walk an annotation's normal appearance
                # stream resources for /StructParent links.
                try:
                    normal_app = ann.get_normal_appearance_stream()
                except Exception:
                    normal_app = None
                if normal_app is not None:
                    try:
                        app_resources = normal_app.get_resources()
                    except Exception:
                        app_resources = None
                    self.process_resources(
                        app_resources, src_numbers, dst_numbers, set()
                    )
            # Walk page resources for /StructParent / /StructParents
            # references used by Form/Image XObjects (Java line 235).
            try:
                page_resources = page.get_resources()
            except Exception:
                page_resources = None
            self.process_resources(
                page_resources, src_numbers, dst_numbers, set()
            )

        if dst_numbers:
            # Build a fresh number-tree leaf node from the filtered map.
            dst_pt_dict = COSDictionary()
            dst_pt_node = PDStructureElementNumberTreeNode(dst_pt_dict)
            # Wrap raw COS values so the number-tree set_numbers path
            # stores them verbatim (PDStructureElementNumberTreeNode
            # convert_value_to_cos returns the value unchanged for
            # COSBase inputs).
            dst_pt_node.set_numbers(dst_numbers)
            dst_struct_root.set_parent_tree(dst_pt_node)
            upper = dst_pt_node.get_upper_limit()
            if upper is not None:
                dst_struct_root.set_parent_tree_next_key(upper + 1)

        # /ClassMap — carry verbatim from source. Class entries may be
        # referenced by retained struct elements via /C.
        src_class_map = src_struct_root.get_cos_object().get_dictionary_object(
            _CLASS_MAP
        )
        if isinstance(src_class_map, COSDictionary):
            dst_struct_root_cos.set_item(_CLASS_MAP, src_class_map)

        # /RoleMap — narrow to roles actually used by retained elements.
        self.clone_role_map(src_struct_root, dst_struct_root)

        # /IDTree — filter to ids actually referenced by retained
        # elements, mapped through _struct_dict_map.
        self.clone_id_tree(
            src_struct_root, dst_struct_root, PDStructureElementNameTreeNode
        )

        destination_document.get_document_catalog().set_struct_tree_root(
            dst_struct_root
        )

    # ---- structure-tree helpers (private; mirror upstream KCloner) ----

    def _build_k_skip_info(self, src_k: COSBase | None) -> None:
        """Annotate every source structure element once per split() run so
        each chunk's clone can skip subtrees that cannot contribute to it.

        Upstream ``Splitter`` (KCloner) re-walks the complete source /K tree
        for every output document, which makes an N-chunk split of a tagged
        file O(N * tree). For each element reachable from /K this records,
        in ``_k_node_cache``, ``[src, /Pg, /K, /Type, has_mcids, mask,
        live]``:

        * ``mask`` — bit ``i`` set when some /Pg in the subtree is a page of
          destination document ``i``;
        * ``live`` — the subtree can yield a non-``None`` clone (or has
          observable side effects) even when no /Pg in it belongs to the
          chunk and no ancestor supplied an in-chunk page.

        With ``current_page_dict is None`` the parent clone carries no /Pg,
        so a subtree with neither the chunk's bit nor ``live`` deterministically
        clones to ``None`` with no side effects; :meth:`_k_clone_dictionary`
        returns that result without walking it. ``live`` mirrors the clone
        rules for that context: scalars survive; ``MCR`` and ``OBJR`` never do
        (without an inherited page an ``OBJR`` is dropped after the
        annotation lookup, and ``_remove_possible_orphan_annotation`` returns
        before logging because there is no host page); an element whose
        out-of-chunk /Pg carries MCIDs is dropped; otherwise an element
        survives iff its /K does. If any element or array is reachable twice
        (shared node or cycle), the per-chunk ``_struct_dict_map`` reuse
        could resurrect a skipped node, so skipping is disabled for the run.
        """
        node_cache = self._k_node_cache
        if node_cache is None:
            return
        page_chunk = self._page_to_doc_num_map
        seen: set[int] = set()
        shared = False

        def visit(node: COSBase | None, depth: int) -> tuple[int, bool]:
            nonlocal shared
            if node is None:
                return 0, False
            if isinstance(node, COSObject):
                return visit(node.get_object(), depth)
            if isinstance(node, (COSArray, COSDictionary)):
                if id(node) in seen or depth > 500:
                    shared = True
                    return 0, True
                seen.add(id(node))
            else:
                return 0, True
            if isinstance(node, COSArray):
                mask = 0
                live = False
                for i in range(node.size()):
                    entry = node.get(i)
                    m, alive = visit(entry, depth + 1)
                    mask |= m
                    live = live or alive
                return mask, live
            src_page_dict = node.get_dictionary_object(_PG)
            if not isinstance(src_page_dict, COSDictionary):
                src_page_dict = None
            kid = node.get_dictionary_object(_K)
            type_name = node.get_name(_TYPE)
            kid_mask, kid_live = visit(kid, depth + 1)
            mask = kid_mask
            has_mcids: bool | None = None
            if src_page_dict is not None:
                chunk = page_chunk.get(id(src_page_dict))
                if chunk is not None:
                    mask |= 1 << chunk
            if type_name == "MCR" or type_name == "OBJR":
                live = False
            elif src_page_dict is not None:
                has_mcids = self._has_mcids(kid)
                live = False if has_mcids else kid_live
            else:
                live = kid_live
            node_cache[id(node)] = [
                node, src_page_dict, kid, type_name, has_mcids, mask, live
            ]
            return mask, live

        try:
            visit(src_k, 0)
        except RecursionError:
            shared = True
        self._k_skip_enabled = not shared

    def _k_create_clone(
        self,
        src: COSBase | None,
        dst_parent: COSBase,
        current_page_dict: COSDictionary | None,
        page_tree: Any,
    ) -> COSBase | None:
        if src is None:
            return None
        if isinstance(src, COSObject):
            return self._k_create_clone(
                src.get_object(), dst_parent, current_page_dict, page_tree
            )
        if isinstance(src, COSArray):
            return self._k_clone_array(src, dst_parent, current_page_dict, page_tree)
        if isinstance(src, COSDictionary):
            return self._k_clone_dictionary(
                src, dst_parent, current_page_dict, page_tree
            )
        return src

    def _k_clone_array(
        self,
        src: COSArray,
        dst_parent: COSBase,
        current_page_dict: COSDictionary | None,
        page_tree: Any,
    ) -> COSBase | None:
        dst = COSArray()
        for i in range(src.size()):
            entry = src.get(i)
            if isinstance(entry, COSObject):
                cloned = self._k_create_clone(
                    entry.get_object(), dst_parent, current_page_dict, page_tree
                )
            else:
                cloned = self._k_create_clone(
                    entry, dst_parent, current_page_dict, page_tree
                )
            if cloned is not None:
                dst.add(cloned)
        return dst if dst.size() > 0 else None

    def _k_clone_dictionary(
        self,
        src: COSDictionary,
        dst_parent: COSBase,
        current_page_dict: COSDictionary | None,
        page_tree: Any,
    ) -> COSDictionary | None:
        existing = self._struct_dict_map.get(id(src))
        if existing is not None:
            return existing

        # The source structure tree is read-only during split() and every
        # chunk re-walks it (upstream KCloner does the same), so resolve each
        # element's /Pg, /K and /Type once per run instead of once per chunk.
        # The entry pins ``src`` so a recycled id() can never match.
        node_cache = self._k_node_cache
        info = node_cache.get(id(src)) if node_cache is not None else None
        if info is None or info[0] is not src:
            src_page_dict = src.get_dictionary_object(_PG)
            if not isinstance(src_page_dict, COSDictionary):
                src_page_dict = None
            info = [src, src_page_dict, src.get_dictionary_object(_K),
                    src.get_name(_TYPE), None]
            if node_cache is not None:
                node_cache[id(src)] = info
        # Subtree skip (see _build_k_skip_info): with no in-chunk page above
        # (``current_page_dict is None``) and none anywhere below, a subtree
        # whose clone is provably ``None`` is not walked at all.
        if (
            current_page_dict is None
            and self._k_skip_enabled
            and len(info) > 5
            and not info[6]
            and not (info[5] >> self._k_chunk_index) & 1
        ):
            return None
        src_page_dict = info[1]
        kid = info[2]
        type_name = info[3]
        dst_page_dict: COSDictionary | None = None

        if src_page_dict is not None:
            dst_page_dict = self._page_dict_map.get(id(src_page_dict))
            if dst_page_dict is not None:
                # O(1) chunk-membership test via the precomputed
                # {id(page_dict): index} map (equivalent to the upstream
                # page_tree.index_of(...) == -1 check, which walked the
                # tree). Only trusted when ``page_tree`` is the exact object
                # the map was built from in clone_structure_tree; direct
                # callers passing a foreign page tree fall back to index_of.
                if id(page_tree) == self._page_index_tree_id:
                    not_in_chunk = id(dst_page_dict) not in self._page_index_by_id
                else:
                    not_in_chunk = page_tree.index_of(dst_page_dict) == -1
                if not_in_chunk:
                    return None
            else:
                # PDFBOX-6009: src has /Pg pointing somewhere not in this
                # chunk. Quit on MCID/MCR/OBJR — they need a /Pg — else
                # keep as an intermediate.
                if type_name == "MCR" or type_name == "OBJR":
                    return None
                has_mcids = info[4]
                if has_mcids is None:
                    has_mcids = info[4] = self._has_mcids(kid)
                if has_mcids:
                    return None

        # MCR with no resolvable destination page and no inherited /Pg
        # from parent — drop it (PAC rule).
        if (
            type_name == "MCR"
            and dst_page_dict is None
            and isinstance(dst_parent, COSDictionary)
            and dst_parent.get_dictionary_object(_PG) is None
        ):
            return None

        dst = COSDictionary()
        self._struct_dict_map[id(src)] = dst
        for key, value in src.entry_set():
            if key != _K and key != _PG and key != _P:
                dst.set_item(key, value)

        # OBJR special handling — replace /Obj with the cloned annotation
        # dict (or remove when the source annotation isn't on the page).
        if type_name == "OBJR":
            src_obj = src.get_dictionary_object(_OBJ)
            if isinstance(src_obj, COSDictionary):
                dst_obj = self._annot_dict_map.get(id(src_obj))
                if dst_obj is not None:
                    dst.set_item(_OBJ, dst_obj)
                else:
                    self._remove_possible_orphan_annotation(
                        src_obj, src, current_page_dict, dst
                    )
            if dst.size() == 1:
                # Only a /Type entry remains — no useful payload.
                self._struct_dict_map.pop(id(src), None)
                return None
            if (
                dst_page_dict is None
                and isinstance(dst_parent, COSDictionary)
                and dst_parent.get_dictionary_object(_PG) is None
            ):
                self._struct_dict_map.pop(id(src), None)
                return None

        if type_name != "OBJR" and type_name != "MCR":
            dst.set_item(_P, dst_parent)

        if dst_page_dict is not None:
            dst.set_item(_PG, dst_page_dict)

        next_page_dict = dst_page_dict if dst_page_dict is not None else current_page_dict
        cloned_kid = self._k_create_clone(kid, dst, next_page_dict, page_tree)
        if cloned_kid is None and kid is not None:
            # The kids array wasn't empty, but became empty after narrowing —
            # this element is now an orphan, drop its placeholder so the
            # /IDTree / /ParentTree narrowing doesn't surface a half-empty
            # struct dict.
            self._struct_dict_map.pop(id(src), None)
            return None

        # Orphan check: no parent page, no own page, and no kids.
        if dst_page_dict is None and cloned_kid is None and current_page_dict is None:
            self._struct_dict_map.pop(id(src), None)
            return None

        if cloned_kid is not None:
            dst.set_item(_K, cloned_kid)

        # Track ids and roles for /IDTree / /RoleMap narrowing.
        id_value = dst.get_string(_ID)
        if id_value is not None:
            self._id_set.add(id_value)
        role = dst.get_name(_S)
        if role is not None:
            self._role_set.add(role)
        return dst

    @staticmethod
    def _has_mcids(kid: COSBase | None) -> bool:
        if isinstance(kid, COSInteger):
            return True
        if isinstance(kid, COSArray):
            for i in range(kid.size()):
                entry = kid.get_object(i)
                if isinstance(entry, COSInteger):
                    return True
        return False

    def _remove_possible_orphan_annotation(
        self,
        src_obj: COSDictionary,
        src_dict: COSDictionary,
        current_page_dict: COSDictionary | None,
        dst_dict: COSDictionary,
    ) -> None:
        obj_type = src_obj.get_dictionary_object(_TYPE)
        obj_subtype = src_obj.get_dictionary_object(_SUBTYPE)
        is_annot = isinstance(obj_type, COSName) and obj_type.get_name() == "Annot"
        is_link = isinstance(obj_subtype, COSName) and obj_subtype.get_name() == "Link"
        if not is_annot and not is_link:
            return
        host_page = src_dict.get_dictionary_object(_PG)
        if not isinstance(host_page, COSDictionary):
            host_page = current_page_dict
        if host_page is None:
            return
        annots_array = host_page.get_dictionary_object(_ANNOTS)
        if not isinstance(annots_array, COSArray):
            _LOG.warning(
                "An annotation OBJ that isn't in the page has been removed "
                "from the structure tree"
            )
            dst_dict.remove_item(_OBJ)
            return
        for i in range(annots_array.size()):
            if annots_array.get_object(i) is src_obj:
                return
        _LOG.warning(
            "An annotation OBJ that isn't in the page has been removed "
            "from the structure tree"
        )
        dst_dict.remove_item(_OBJ)

    def clone_tree_element(
        self,
        src_numbers: dict[int, COSBase],
        dst_numbers: dict[int, COSBase],
        sp: int,
    ) -> None:
        src_obj = src_numbers.get(sp)
        if src_obj is None:
            return
        if isinstance(src_obj, COSArray):
            cloned_arr = COSArray()
            for i in range(src_obj.size()):
                element = src_obj.get_object(i)
                cloned_entry = self._struct_dict_map.get(id(element))
                if cloned_entry is not None:
                    cloned_arr.add(cloned_entry)
                else:
                    # null placeholder — the array is indexed by MCID, so
                    # holes must be preserved.
                    from pypdfbox.cos import COSNull

                    cloned_arr.add(COSNull.NULL)
            dst_numbers[sp] = cloned_arr
        elif isinstance(src_obj, COSDictionary):
            cloned_entry = self._struct_dict_map.get(id(src_obj))
            if cloned_entry is None:
                _LOG.warning("ParentTree index %d dictionary not found in /K", sp)
                return
            dst_numbers[sp] = cloned_entry
        else:
            _LOG.warning(
                "tree element neither dictionary nor array, but %s",
                type(src_obj).__name__,
            )

    def clone_role_map(self, src_root: Any, dst_root: Any) -> None:
        src_dict = src_root.get_cos_object().get_dictionary_object(_ROLE_MAP)
        if not isinstance(src_dict, COSDictionary):
            return
        dst_dict = COSDictionary()
        for key, value in src_dict.entry_set():
            if key.get_name() in self._role_set:
                dst_dict.set_item(key, value)
        dst_root.get_cos_object().set_item(_ROLE_MAP, dst_dict)

    def clone_id_tree(
        self, src_root: Any, dst_root: Any, name_tree_cls: type
    ) -> None:
        src_id_tree = src_root.get_id_tree()
        if src_id_tree is None:
            return
        src_id_map = self._get_id_tree_as_map(src_id_tree)
        if not src_id_map:
            return
        from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
            PDStructureElement,
        )

        dst_names: dict[str, PDStructureElement] = {}
        for key, val in src_id_map.items():
            if key not in self._id_set:
                continue
            src_dict = (
                val.get_cos_object() if hasattr(val, "get_cos_object") else val
            )
            cloned_dict = self._struct_dict_map.get(id(src_dict))
            if cloned_dict is not None:
                dst_names[key] = PDStructureElement(cloned_dict)
        if not dst_names:
            return
        dst_id_tree = name_tree_cls()
        dst_id_tree.set_names(dst_names)
        dst_root.set_id_tree(dst_id_tree)

    @staticmethod
    def _get_number_tree_as_map(node: Any) -> dict[int, COSBase]:
        """Walk a number-tree node into a flat ``{int: COSBase}`` map.
        Local mirror of upstream ``PDFMergerUtility.getNumberTreeAsMap``
        — kept private so we don't have to wait on the merger-utility
        helper to land."""
        out: dict[int, COSBase] = {}
        Splitter._walk_number_tree(node, out)
        return out

    @staticmethod
    def _walk_number_tree(node: Any, out: dict[int, COSBase]) -> None:
        try:
            numbers = node.get_numbers()
        except Exception:
            numbers = None
        if numbers:
            for key, value in numbers.items():
                base = value.get_cos_object() if hasattr(value, "get_cos_object") else value
                out[int(key)] = base
            return
        try:
            kids = node.get_kids()
        except Exception:
            kids = None
        if kids:
            for child in kids:
                Splitter._walk_number_tree(child, out)

    @staticmethod
    def _get_id_tree_as_map(node: Any) -> dict[str, Any]:
        """Walk an ID name-tree into a flat ``{str: PDStructureElement}``
        map. Local mirror of upstream ``PDFMergerUtility.getIDTreeAsMap``."""
        out: dict[str, Any] = {}
        Splitter._walk_id_tree(node, out)
        return out

    @staticmethod
    def _walk_id_tree(node: Any, out: dict[str, Any]) -> None:
        try:
            names = node.get_names()
        except Exception:
            names = None
        if names:
            out.update(names)
            return
        try:
            kids = node.get_kids()
        except Exception:
            kids = None
        if kids:
            for child in kids:
                Splitter._walk_id_tree(child, out)

    # ---------- resource walking ----------

    def process_resources(
        self,
        resources: Any,
        src_numbers: dict[int, COSBase],
        dst_numbers: dict[int, COSBase],
        visited: set[int],
    ) -> None:
        """Walk ``resources`` for Form/Image XObjects with ``/StructParent``
        or ``/StructParents`` references, copying any retained entries
        from ``src_numbers`` into ``dst_numbers`` (mirrors upstream
        ``Splitter.processResources`` at Java line 586).

        ``visited`` tracks resource dictionary identities to break cycles
        — upstream PDFBox guards 002874.pdf this way.
        """
        if resources is None:
            return
        try:
            resources_cos = resources.get_cos_object()
        except AttributeError:
            return
        cos_id = id(resources_cos)
        if cos_id in visited:
            return
        visited.add(cos_id)

        try:
            x_object_names = resources.get_xobject_names()
        except Exception:
            return
        for name in x_object_names:
            try:
                x_object = resources.get_x_object(name)
            except Exception:
                continue
            sp = -1
            # Form XObjects carry /StructParents (note plural) and have
            # nested /Resources of their own that need recursion.
            from pypdfbox.pdmodel.graphics.form.pd_form_x_object import (
                PDFormXObject,
            )
            from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
                PDImageXObject,
            )

            if isinstance(x_object, PDFormXObject):
                try:
                    sp = x_object.get_struct_parents()
                except Exception:
                    sp = -1
                try:
                    nested = x_object.get_resources()
                except Exception:
                    nested = None
                self.process_resources(nested, src_numbers, dst_numbers, visited)
            elif isinstance(x_object, PDImageXObject):
                try:
                    sp = x_object.get_struct_parent()
                except Exception:
                    sp = -1
            if sp != -1:
                self.clone_tree_element(src_numbers, dst_numbers, sp)

    # ---------- private-name aliases (back-compat) ----------
    #
    # Upstream Splitter exposes the structure-tree clone helpers as
    # ``private``. We mirror them as public methods so the Java naming
    # round-trips through the parity tracker and so subclasses can hook
    # the same surface area as upstream subclasses do (e.g. via
    # ``protected`` accessors). The leading-underscore aliases below
    # preserve compatibility with internal callers and existing tests
    # that exercise the implementation directly.
    _clone_structure_tree = clone_structure_tree
    _clone_tree_element = clone_tree_element
    _clone_role_map = clone_role_map
    _clone_id_tree = clone_id_tree
    _fix_destinations = fix_destinations


__all__ = ["Splitter"]
