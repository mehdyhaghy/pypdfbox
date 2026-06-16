from __future__ import annotations

import contextlib
import logging
from typing import Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSObjectKey,
    COSStream,
    COSString,
)
from pypdfbox.io import RandomAccessRead, RandomAccessReadBuffer

from .base_parser import BaseParser
from .cos_parser import (
    COSParser,
    _parse_xref_entry_line,
    _read_object_stream_offsets,
    _validate_xref_index_pair,
)
from .endstream_filter_stream import EndstreamFilterStream
from .parse_error import PDFParseError
from .xref_trailer_resolver import XrefEntry, XrefTrailerResolver, XrefType

_LOG = logging.getLogger(__name__)


class _HeaderNotFoundError(PDFParseError):
    """Raised by :meth:`PDFParser.parse_header` when the ``%PDF-`` / ``%FDF-``
    marker is absent from the leading scan window.

    A ``PDFParseError`` subclass so existing ``except PDFParseError`` callers
    (and the standalone-method contract tests) keep treating a header-less file
    as a parse failure, while :meth:`PDFParser.parse` can distinguish the
    *marker-not-found* case (recoverable via brute-force in lenient mode, per
    upstream ``COSParser.parseHeader`` returning ``false``) from a
    *malformed-version* failure (always fatal, per upstream's
    ``IOException("Error getting header version:")``).
    """


# How many trailing bytes to scan for ``startxref`` / ``%%EOF``. Mirrors the
# upstream ``COSParser.DEFAULT_TRAIL_BYTECOUNT`` knob (default 2048 in PDFBox;
# pypdfbox bumps the floor to 4096 to absorb noisier tails). Per-instance
# overrides go through :meth:`PDFParser.set_eof_lookup_range`.
_TAIL_SCAN_BYTES: int = 4096

# Upstream system-property name that lets callers override the EOF lookup
# range without code changes (``-Dorg.apache.pdfbox.pdfparser…``). Exposed
# verbatim for source-level parity with PDFBox; pypdfbox does not consult
# environment variables on its own — callers wire up the override
# explicitly via :meth:`PDFParser.set_eof_lookup_range` when desired.
SYSPROP_EOFLOOKUPRANGE: str = (
    "org.apache.pdfbox.pdfparser.nonSequentialPDFParser.eofLookupRange"
)


class PDFParser:
    """
    Top-level PDF document parser.

    Pipeline:
      1. ``parse_header()`` validates the ``%PDF-x.y`` magic and records
         the version.
      2. ``find_startxref_offset()`` scans the trailing bytes for
         ``startxref <int> %%EOF``.
      3. ``parse_xref_chain()`` walks the xref → trailer → ``/Prev`` chain
         via ``XrefTrailerResolver``, populating one entry per indirect
         object from traditional xref tables and PDF 1.5+ xref streams.
      4. ``populate_document()`` registers every xref entry as a
         ``COSObject`` in the document's pool with a lazy loader that
         seeks to the entry's offset on demand and parses the body.

    The convenience method ``parse()`` runs all four steps and returns
    the populated ``COSDocument``.
    """

    def __init__(
        self,
        source: RandomAccessRead,
        decryption_password: str | bytes | None = None,
        scratch_file: Any | None = None,
    ) -> None:
        """Construct a parser around ``source``.

        ``decryption_password`` mirrors the upstream
        ``PDFParser(RandomAccessRead, String)`` constructor overload (Java
        line 58): when supplied, the password is staged the same way
        :meth:`set_password` does, so the eager-decrypt path can stand up
        a security handler before encrypted xref-stream bodies are
        decoded. ``None`` preserves the lazy post-load decryption flow
        driven by ``PDDocument.decrypt``.

        ``scratch_file`` is the ``ScratchFile`` instance backing every
        ``COSStream`` in the parsed object graph — typically constructed
        from a caller-supplied :class:`MemoryUsageSetting`. ``None``
        falls back to a default heap-backed scratch file built lazily
        by :class:`COSDocument`."""
        self._src = source
        self._scratch_file = scratch_file
        self._base = BaseParser(source)
        self._resolver = XrefTrailerResolver()
        self._document: COSDocument | None = None
        self._version: float | None = None
        self._cos_parser: COSParser | None = None
        # Optional decryption material — when set via ``set_password`` the
        # parser instantiates a security handler eagerly (as soon as the
        # trailer's ``/Encrypt`` + ``/ID`` are available) so encrypted
        # xref-stream bodies can be deciphered before their entries are
        # decoded. Mirrors the upstream ``PDFParser(source, password, …)``
        # ctor overload. ``None`` (the default) preserves the lazy
        # post-load decryption flow driven by ``PDDocument.decrypt``.
        self._password: str | bytes | None = decryption_password
        # Populated by ``_prepare_security_handler_if_needed`` once the
        # trailer's ``/Encrypt`` is in scope. Reused for every subsequent
        # xref-stream object in the chain.
        self._security_handler: Any | None = None
        # Set to ``True`` whenever the parser observes an indirect object
        # whose dictionary advertises ``/Type /XRef`` while the document
        # carries an ``/Encrypt`` entry. Diagnostic surface for callers
        # that want to know whether the early-handler path was exercised.
        self._has_encrypted_xref_streams: bool = False
        # Lenient parsing toggle. Mirrors upstream
        # ``PDFParser.setLenient(boolean)``. The pypdfbox parser already
        # operates in a permissive (lenient) mode — this flag is exposed
        # for API parity so callers staging documents through PDFBox-style
        # entry points can round-trip the value. Stored only; no behaviour
        # branches off it yet.
        self._lenient: bool = True
        # Set by :meth:`_parse_traditional_xref_section` when a classic xref
        # table breaks mid-parse (malformed subsection header / entry row,
        # upstream's "Unexpected XRefTable Entry"). The chain walker then runs
        # a brute-force object merge so the incomplete table is repaired,
        # mirroring upstream COSParser's post-break recovery.
        self._xref_table_recovery_needed: bool = False
        # Cache for the lazy brute-force object scan used by the lenient
        # free/missing-key resolution fallback (mirrors upstream
        # ``COSParser.bfCOSObjectKeyOffsets``). ``None`` until the first
        # dangling reference forces a ``bf_search_for_objects`` scan.
        self._bf_offsets_cache: dict[COSObjectKey, int] | None = None
        # Lazy ``PDDocument`` wrapper around the parsed ``COSDocument``.
        # Built on first call to :meth:`get_pd_document`; mirrors upstream
        # ``PDFParser.getPDDocument()``.
        self._pd_document: Any | None = None
        # How many trailing bytes :meth:`find_startxref_offset` reads when
        # hunting for the ``startxref`` directive. Mirrors upstream
        # ``COSParser.readTrailBytes`` and the ``setEOFLookupRange`` knob.
        self._eof_lookup_range: int = _TAIL_SCAN_BYTES
        # Optional linearization parameter dictionary (PDF 32000-1 Annex F).
        # Populated by :meth:`_detect_linearization` when the **first**
        # indirect object after the header carries a truthy ``/Linearized``
        # entry. Advisory metadata only — the regular xref-walk path is
        # unaffected by linearization (the trailing xref still wins).
        self.linearization_dict: COSDictionary | None = None
        # Raw bytes of the primary hint stream, slurped via the offset+
        # length pair in the linearization dict's ``/H`` entry. Hint
        # streams encode the page-offset / shared-object / thumbnail
        # tables that web-streaming viewers consult to fetch only the
        # bytes they need; pypdfbox does not interpret the hint table
        # body — exposed as raw bytes for downstream tooling.
        self.hint_table_bytes: bytes | None = None

    # ---------- public entry point ----------

    @staticmethod
    def load(
        source: Any,
        password: str | bytes | None = None,
    ) -> Any:
        """Deprecated static factory mirroring upstream
        ``PDFParser.load(File [, String password])`` (Java lines 212 / 231).

        Upstream this is a thin delegate to ``Loader.loadPDF`` retained for
        binary compatibility with PDFBox 1.x / 2.x call sites; pypdfbox
        mirrors the surface for source-level parity. Prefer
        :func:`pypdfbox.loader.Loader.load_pdf` (or :class:`PDDocument`
        wrappers) in new code.

        Accepts any source form :func:`Loader.load_pdf` accepts — paths,
        ``bytes`` / ``bytearray`` / ``memoryview`` buffers, file-like
        streams, or a pre-built :class:`RandomAccessRead`. Returns a
        :class:`PDDocument` wrapping the parsed :class:`COSDocument` (the
        upstream return type) so callers can drive page enumeration /
        decryption directly.
        """
        # Local import — pdfparser must not depend on the loader / pdmodel
        # layers at import time (both live one layer up).
        from pypdfbox.loader import Loader  # noqa: PLC0415
        from pypdfbox.pdmodel.pd_document import PDDocument  # noqa: PLC0415

        document = Loader.load_pdf(source, password)
        return PDDocument(document)

    def parse(self, lenient: bool | None = None) -> COSDocument:
        """Parse the document end-to-end. Returns a populated COSDocument
        whose object pool is ready for lazy resolution.

        ``lenient`` mirrors upstream ``PDFParser.parse(boolean)`` (Java
        line 149): when supplied, the lenient flag is toggled before the
        body of the parse runs (matches the upstream
        ``setLenient(lenient)`` first line). ``None`` (the default)
        preserves whatever value ``set_lenient`` last recorded — which
        starts at ``True`` per upstream's "Lenient mode is active by
        default" note on the no-arg overload."""
        if lenient is not None:
            self.set_lenient(lenient)
        self._document = COSDocument(scratch_file=self._scratch_file)
        self._cos_parser = COSParser(self._src, document=self._document)
        # Mirror upstream ``PDFParser.parse(boolean)`` (PDFBox 3.0.7,
        # PDFParser.java ~L150): if neither the %PDF- nor the %FDF- header is
        # located in the scan window, a *lenient* parse logs a warning and
        # falls through with the COSDocument's default version (1.4) so
        # brute-force recovery can still rebuild a body whose header was
        # pushed past the window by leading garbage; a *strict* parse raises
        # "Error: Header doesn't contain versioninfo". ``parse_pdf_header``
        # checks both the %PDF- and %FDF- markers in one scan (upstream splits
        # this across parsePDFHeader()/parseFDFHeader()), records the version
        # on the COSDocument on success, and propagates a malformed-version
        # ``PDFParseError`` (upstream IOException) in either mode.
        if not self.parse_pdf_header():
            if not self._lenient:
                raise PDFParseError("Error: Header doesn't contain versioninfo")
            _LOG.warning("Error: Header doesn't contain versioninfo")
        self._version = self._document.get_version()
        # Detect linearization (PDF 32000-1 Annex F): the **first**
        # indirect object after the header is the linearization
        # parameter dictionary. Advisory only — the regular xref-walk
        # path below is unaffected (trailing xref still wins).
        self._detect_linearization()
        # ``full_rebuild`` marks the no-locatable-xref path (a complete
        # brute-force reconstruction of the cross-reference) as distinct from
        # the missing-/Root path, where the located xref's entries are valid
        # and only the trailer's /Root needed repairing. Only the full
        # rebuild eagerly resolves every recovered object — the missing-/Root
        # path keeps the regular lenient offset check + lazy resolution.
        full_rebuild = False
        # ---- locate the xref (startxref directive + shape check) ----
        # In lenient mode, an *unlocatable* xref (no ``startxref`` keyword,
        # or one whose offset can't be corrected to a real xref section)
        # falls back to a full brute-force rebuild — mirrors upstream
        # COSParser.retrieveTrailer. A located-but-malformed xref STREAM is
        # NOT recovered here: its content errors propagate from
        # ``parse_xref_chain`` below, preserving the strict-on-bad-structure
        # contract. Strict (non-lenient) mode re-raises location failures.
        startxref = -1
        try:
            startxref = self.find_startxref_offset(
                validate_bounds=not self._lenient
            )
            startxref = self._recover_xref_offset_if_needed(startxref)
            located = self._xref_section_starts_at(startxref)
        except PDFParseError:
            if not self._lenient:
                raise
            located = False
        if located:
            self._cos_parser.set_xref_offset(startxref)
            # Record so the incremental writer can chain its appended xref
            # via /Prev (PRD §6.5 cluster #2).
            self._document.set_start_xref(startxref)
            self.parse_xref_chain(startxref)
            # A classic xref table that broke mid-parse (malformed subsection
            # header / entry row) leaves an incomplete object map. Mirror
            # upstream COSParser, which after an "Unexpected XRefTable Entry"
            # break recovers the missing objects via bfSearchForObjects and
            # merges them into the xref — so the orphaned / mislabelled object
            # (e.g. the catalog itself) is still reachable. Also fires when a
            # cleanly parsed table left the trailer's /Root pointing at a
            # *reference* that doesn't resolve to a catalog (e.g. the catalog
            # object mislabelled free): upstream relocates it via the same
            # brute-force scan. A NON-reference /Root (an integer / name
            # scalar) is left untouched — there is no object to relocate, so it
            # stays dangling exactly as upstream's resolve finds it. Only fires
            # when a break occurred or /Root needs relocation, so well-formed
            # tables pay nothing.
            if self._lenient and (
                self._xref_table_recovery_needed
                or self._located_root_needs_relocation()
            ):
                self._merge_brute_force_objects()
            # Mirror upstream COSParser.retrieveTrailer: a trailer that
            # parsed cleanly but carries NO /Root item (the key is absent —
            # checked raw via getItem, not resolved) triggers a brute-force
            # rebuild in lenient mode. The catalog is then relocated by
            # scanning every recovered object for /Type /Catalog and the
            # trailer's /Root is repaired. A trailer whose /Root key IS
            # present but dangles (points at a missing/non-catalog object)
            # is NOT rebuilt — upstream lets that surface as "Missing root"
            # at initialParse time.
            located_trailer = self._resolver.get_trailer()
            if self._lenient and (
                located_trailer is None
                or located_trailer.get_item(COSName.ROOT) is None
            ):
                self._rebuild_trailer_for_missing_root()
        elif self._lenient:
            self._rebuild_document_from_brute_force()
            full_rebuild = True
        else:
            raise PDFParseError(
                f"startxref offset {startxref} does not point to xref"
            )
        trailer = self._resolver.get_trailer()
        if trailer is not None:
            self._document.set_trailer(trailer)
        # Record whether the document's most-recent cross-reference is an
        # xref STREAM (vs a classic table). Mirrors upstream
        # ``COSParser.parseXref``: ``document.setIsXRefStream(
        # XRefType.STREAM == xrefTrailerResolver.getXrefType())``. The
        # resolved type is the kind of the section the last ``startxref``
        # points to; reading it via ``get_xref_type_at`` avoids the heavier
        # ``set_startxref`` resolve. The flag drives the incremental writer's
        # choice of appended xref encoding — an xref-stream source must
        # receive an xref-stream increment, not a classic table
        # (``COSWriter.doWriteXRefInc``). Only meaningful on the located-xref
        # path; a brute-force rebuild has no resolvable section type and
        # stays at the default (table).
        if located:
            section_type = self._resolver.get_xref_type_at(startxref)
            if section_type is XrefType.STREAM:
                self._document.set_is_xref_stream(True)
        self.populate_document()
        if full_rebuild:
            # Upstream BruteForceParser.searchForTrailerItems (driven by
            # rebuildTrailer) eagerly DEREFERENCES every recovered object
            # to inspect its /Type / /Root / /Info candidacy. That eager
            # resolution is why a brute-force-recovered file whose body
            # holds a broken object (e.g. a stream with no ``endstream``)
            # still surfaces the parse error at load time rather than
            # silently "recovering". Mirror that so our rebuild outcome
            # matches PDFBox's PARSE_FAIL vs success decision. Only the
            # full (no-locatable-xref) rebuild does this; the missing-/Root
            # path leaves the valid located entries to lazy resolution.
            self._resolve_recovered_objects()
            # Upstream ``Loader.loadPDF`` → ``PDFParser.parse(boolean)`` always
            # ends in ``initialParse()``, which calls ``retrieveTrailer()`` and
            # then validates the trailer's ``/Root`` — raising
            # ``IOException("Missing root object specification in trailer.")``
            # when the (possibly rebuilt) trailer has no resolvable catalog.
            # pypdfbox defers ``initial_parse`` from the *located-xref* path so
            # lazy /Root + stream resolution still works, but the full
            # brute-force rebuild is precisely the path where upstream's eager
            # rejection fires: a header-less, catalog-less buffer that carries
            # only decoy ``n g obj`` tokens rebuilds a trailer with NO /Root and
            # must fail at load time, not yield a silent 0-page document. Mirror
            # that here (full-rebuild only — the lazy fixtures take the
            # located-xref branch and are untouched).
            self._reject_full_rebuild_without_root()
            # initialParse also runs checkPages(root) right after the /Root
            # validation. On the rebuilt-trailer path this prunes /Kids whose
            # targets are missing or truncated (a page object cut off mid-body
            # by a truncation that landed past its ``n g obj`` header but before
            # ``endobj``) and rewrites /Count, so the recovered page tally
            # matches upstream. Without it the dangling kid would still be
            # counted (pypdfbox defers initial_parse on the located-xref path,
            # but the full rebuild mirrors initialParse end-to-end). The
            # located-xref path is untouched — its kids are valid.
            self._check_pages_after_full_rebuild()
        elif self._lenient:
            # PDFBox's COSParser.checkXrefOffsets: in lenient mode every
            # parsed xref offset is verified to point at its ``n g obj``
            # header; entries that don't are brute-force-corrected so a
            # single bad subsection offset doesn't strand an object.
            self._check_xref_offsets_lenient()
        # ``initial_parse()`` is intentionally **not** auto-invoked here.
        # Upstream PDFBox does call it from ``parse()``, but pypdfbox's
        # historical contract has been that ``parse()`` returns the
        # populated COSDocument and lazy resolution of ``/Root`` /
        # streams happens on demand — eagerly resolving the catalog
        # would force every stream-typed indirect on the /Root path to
        # be parsed at load time, breaking lazy-error fixtures. Strict
        # callers should invoke :meth:`initial_parse` explicitly to
        # surface ``Missing root`` / catalog-type repairs.
        self._document.get_document_state().set_parsing(False)
        return self._document

    def initial_parse(self) -> None:
        """Validate the trailer's ``/Root`` pointer and (in lenient mode)
        ensure the catalog dictionary advertises ``/Type /Catalog``.
        Mirrors upstream ``PDFParser.initialParse`` (Java line 105).

        Raises :class:`PDFParseError` when ``/Root`` is missing — matches
        the upstream "Missing root object specification in trailer."
        message. The cos_parser's ``initial_parse_done`` flag is flipped
        to ``True`` on success so callers introspecting parse state can
        distinguish "trailer loaded but root not validated" from "fully
        bootstrapped"."""
        trailer = self._resolver.get_trailer()
        if trailer is None:
            raise PDFParseError("Missing trailer; cannot run initial_parse")
        root = trailer.get_dictionary_object(COSName.ROOT)  # type: ignore[attr-defined]
        if not isinstance(root, COSDictionary):
            raise PDFParseError("Missing root object specification in trailer.")
        # In some pdfs the type value "Catalog" is missing in the root
        # object — repair it when lenient (matches upstream PDFBox).
        if self._lenient and not root.contains_key(COSName.TYPE):
            root.set_item(COSName.TYPE, COSName.CATALOG)
        # Validate the page tree (and, when the trailer was rebuilt, prune
        # dangling /Kids). Mirrors upstream PDFParser.initialParse's
        # checkPages(root) call right after the /Type repair: a /Root that
        # resolves to a dictionary lacking a /Pages tree (e.g. a /Root that
        # was mis-pointed at a non-catalog object) raises "Page tree root
        # must be a dictionary" here rather than silently yielding a
        # zero-page document.
        if self._cos_parser is not None:
            self._cos_parser.check_pages(root)
            self._cos_parser.set_initial_parse_done(True)

    def create_document(self) -> Any:
        """Build the resulting :class:`PDDocument` wrapper around the
        parsed :class:`COSDocument`. Mirrors upstream
        ``PDFParser.createDocument()`` (Java line 194) — exposed as a
        public hook so subclasses (and tests) can override the wrapper
        type. The default implementation returns the same instance
        cached by :meth:`get_pd_document`."""
        return self.get_pd_document()

    # ---------- document accessors ----------

    def get_document(self) -> COSDocument | None:
        """Return the parsed ``COSDocument`` or ``None`` if :meth:`parse`
        has not been called yet. Mirrors upstream
        ``PDFParser.getDocument()``."""
        return self._document

    def get_xref_offset(self) -> int:
        """Return the ``startxref`` byte offset recorded during
        :meth:`parse`, or ``-1`` before parsing. Mirrors the
        upstream ``COSParser.getXrefOffset`` surface inherited by
        ``PDFParser`` in PDFBox."""
        if self._cos_parser is None:
            return -1
        return self._cos_parser.get_xref_offset()

    def get_pd_document(self) -> Any:
        """Return a ``PDDocument`` wrapper around the parsed
        ``COSDocument``. Lazily constructed and cached on the parser
        instance so repeated calls return the same wrapper. Mirrors
        upstream ``PDFParser.getPDDocument()``.

        Must be called after :meth:`parse`."""
        if self._pd_document is not None:
            return self._pd_document
        if self._document is None:
            raise PDFParseError(
                "get_pd_document() called before parse(); no document yet"
            )
        # Local import — pdfparser must not depend on pdmodel at import
        # time (PDDocument lives one layer up).
        from pypdfbox.pdmodel.pd_document import PDDocument  # noqa: PLC0415

        self._pd_document = PDDocument(self._document)
        return self._pd_document

    # ---------- trailer / root accessors ----------

    def get_trailer(self) -> COSDictionary | None:
        """Return the consolidated trailer dictionary (the merged view of
        every parsed xref section's trailer fragment) or ``None`` before
        :meth:`parse` has run. Mirrors upstream
        ``COSParser.retrieveTrailer()``'s return surface — pypdfbox keeps
        the trailer permanently on :class:`COSDocument`, this accessor just
        forwards through the ``XrefTrailerResolver`` for parity with code
        that talks to the parser directly."""
        return self._resolver.get_trailer()

    def get_root(self) -> COSDictionary | None:
        """Resolve the trailer's ``/Root`` entry to its dictionary.

        Returns ``None`` when the trailer is absent or ``/Root`` is missing
        / not a dictionary. Mirrors the ``trailer.getCOSDictionary(ROOT)``
        access pattern in upstream ``PDFParser.initialParse``."""
        trailer = self._resolver.get_trailer()
        if trailer is None:
            return None
        root = trailer.get_dictionary_object(COSName.ROOT)  # type: ignore[attr-defined]
        return root if isinstance(root, COSDictionary) else None

    def get_xref_trailer_resolver(self) -> XrefTrailerResolver:
        """Return the parser's ``XrefTrailerResolver``. Diagnostic surface
        — upstream PDFBox exposes the resolver via a protected field
        (``COSParser.xrefTrailerResolver``); pypdfbox surfaces it through
        an explicit accessor so tests / callers can introspect the merged
        xref table after :meth:`parse`."""
        return self._resolver

    # ---------- EOF lookup range (PDFBox-style knob) ----------

    def set_eof_lookup_range(self, byte_count: int) -> None:
        """Adjust how many trailing bytes :meth:`find_startxref_offset`
        scans. Mirrors upstream ``COSParser.setEOFLookupRange(int)``;
        values ``<= 15`` are ignored (matches the upstream guard)."""
        if byte_count > 15:
            self._eof_lookup_range = int(byte_count)

    def get_eof_lookup_range(self) -> int:
        """Return the current EOF-lookup byte count (the window
        :meth:`find_startxref_offset` uses to locate ``startxref``)."""
        return self._eof_lookup_range

    # ---------- lenient mode ----------

    def set_lenient(self, lenient: bool) -> None:
        """Toggle lenient parsing mode. Mirrors upstream
        ``PDFParser.setLenient(boolean)``. The pypdfbox parser is already
        permissive by default — the flag is stored for API parity."""
        self._lenient = bool(lenient)

    def is_lenient(self) -> bool:
        """Return whether lenient parsing is enabled. Mirrors upstream
        ``PDFParser.isLenient()``."""
        return self._lenient

    # ---------- linearization (PDF 32000-1 Annex F) ----------

    def is_linearized(self) -> bool:
        """``True`` when a linearization parameter dictionary was detected
        as the first indirect object after the header. Mirrors the
        conceptual surface PDFBox exposes through
        ``COSDocument.getLinearizedDictionary()`` returning non-null.

        Set during :meth:`parse` (more precisely, by
        :meth:`_detect_linearization`)."""
        return self.linearization_dict is not None

    def get_linearization_dictionary(self) -> COSDictionary | None:
        """Return the parsed linearization parameter dictionary, or
        ``None`` when the document is not linearized."""
        return self.linearization_dict

    def get_hint_table_bytes(self) -> bytes | None:
        """Return the raw bytes of the primary hint stream (offset +
        length taken from the linearization dict's ``/H`` array), or
        ``None`` when the document is not linearized or the hint table
        could not be located. The body is **not** interpreted — hint
        stream parsing (page-offset, shared-object, thumbnail tables)
        is left to higher-level callers."""
        return self.hint_table_bytes

    def decode_page_offset_hint_table(self) -> Any | None:
        """Decode the Page Offset Hint Table out of the primary hint
        stream (PDF 32000-1 Annex F.3).

        Locates the hint stream object via the byte offset stored in
        ``/H[0]`` of the linearization dictionary, runs the stream's
        ``/Filter`` chain through ``COSStream.create_input_stream`` (so
        the typical ``/FlateDecode`` body is unwound), and decodes the
        12-byte Page Offset header plus one per-page record per page
        listed in ``/N``.

        Returns the typed :class:`~pypdfbox.pdfparser.linearization_hint_table.PageOffsetHintTable`
        on success, or ``None`` when the document is not linearized, the
        hint stream cannot be located, or the body is malformed. Mirrors
        the "lite decoder" pattern PDFBox upstream omits — pypdfbox
        ships it for web-streaming consumers who need page-level byte
        ranges without a full xref walk.

        Apache PDFBox upstream does **not** decode the hint stream at
        all; this is a pypdfbox enrichment over the deferral noted in
        CHANGES.md under "Wave 41 round-out — read-only linearization"."""
        from .linearization_hint_table import (  # noqa: PLC0415
            HintTableParseError,
            parse_page_offset_hint_table,
        )

        lin = self.linearization_dict
        if lin is None:
            return None
        # /N — total page count, needed to size the per-page block.
        n_obj = lin.get_dictionary_object(COSName.get_pdf_name("N"))
        if not isinstance(n_obj, (COSInteger, COSFloat)):
            return None
        page_count = int(n_obj.value)
        if page_count <= 0:
            return None
        # /H — primary hint stream offset (and length we don't strictly
        # need for the decode path, since the stream's own /Length wins).
        h_arr = lin.get_dictionary_object(COSName.get_pdf_name("H"))
        if not isinstance(h_arr, COSArray) or h_arr.size() < 2:
            return None
        h_off_obj = h_arr.get(0)
        if not isinstance(h_off_obj, (COSInteger, COSFloat)):
            return None
        hint_stream_byte_offset = int(h_off_obj.value)
        # Locate the hint stream object by scanning the resolver for an
        # entry whose offset matches /H[0]. PDFBox upstream does no such
        # lookup (it never decodes the hint stream); we do because the
        # filter chain must run before we can interpret the body.
        target_key: COSObjectKey | None = None
        for key, entry in self._resolver.get_xref_table().items():
            if (
                entry.type is XrefType.TABLE or entry.type is XrefType.STREAM
            ) and entry.offset == hint_stream_byte_offset:
                target_key = key
                break
        if target_key is None:
            return None
        document = self._document
        if document is None:
            return None
        target_obj = document.get_object(target_key)
        if target_obj is None:
            return None
        resolved = target_obj.get_object()
        if not isinstance(resolved, COSStream):
            return None
        body = resolved
        try:
            with body.create_input_stream() as src:
                decoded = src.read()
        except (OSError, ValueError):
            return None
        try:
            return parse_page_offset_hint_table(decoded, page_count=page_count)
        except HintTableParseError:
            return None

    def _read_hint_stream_decoded(self) -> bytes | None:
        """Locate the primary hint stream object via the byte offset
        stored in ``/H[0]`` of the linearization parameter dictionary,
        run its ``/Filter`` chain (typically ``/FlateDecode``), and
        return the decoded body. Returns ``None`` when the document is
        not linearized, the hint stream cannot be located, or the
        filter chain fails to decode.

        Shared between :meth:`decode_shared_object_hint_table` and
        :meth:`decode_thumbnail_hint_table` — both sub-tables live in
        the same decoded hint stream body, just at different byte
        offsets."""
        lin = self.linearization_dict
        if lin is None:
            return None
        h_arr = lin.get_dictionary_object(COSName.get_pdf_name("H"))
        if not isinstance(h_arr, COSArray) or h_arr.size() < 2:
            return None
        h_off_obj = h_arr.get(0)
        if not isinstance(h_off_obj, (COSInteger, COSFloat)):
            return None
        hint_stream_byte_offset = int(h_off_obj.value)
        target_key: COSObjectKey | None = None
        for key, entry in self._resolver.get_xref_table().items():
            if (
                entry.type is XrefType.TABLE or entry.type is XrefType.STREAM
            ) and entry.offset == hint_stream_byte_offset:
                target_key = key
                break
        if target_key is None:
            return None
        document = self._document
        if document is None:
            return None
        target_obj = document.get_object(target_key)
        if target_obj is None:
            return None
        resolved = target_obj.get_object()
        if not isinstance(resolved, COSStream):
            return None
        try:
            with resolved.create_input_stream() as src:
                return src.read()
        except (OSError, ValueError):
            return None

    def _hint_subtable_offset(self, h_index: int) -> int | None:
        """Return the byte offset into the decoded hint stream body
        where a non-Page-Offset sub-table starts, derived from
        ``/H[h_index]`` of the linearization parameter dictionary.

        pypdfbox treats ``/H[2]`` as the byte offset of the Shared
        Object Hint Table within the decoded hint stream, and ``/H[3]``
        as the byte offset of the Thumbnail Hint Table. Both are
        optional; returns ``None`` when missing, non-numeric, or
        negative. Apache PDFBox upstream never decodes the hint stream
        so this convention is pypdfbox-specific."""
        lin = self.linearization_dict
        if lin is None:
            return None
        h_arr = lin.get_dictionary_object(COSName.get_pdf_name("H"))
        if not isinstance(h_arr, COSArray) or h_arr.size() <= h_index:
            return None
        slot = h_arr.get(h_index)
        if not isinstance(slot, (COSInteger, COSFloat)):
            return None
        value = int(slot.value)
        if value < 0:
            return None
        return value

    def decode_shared_object_hint_table(self) -> Any | None:
        """Decode the Shared Object Hint Table out of the primary hint
        stream (PDF 32000-1 Annex F.4).

        The Shared Object table follows the Page Offset table in the
        decoded hint stream body. pypdfbox lets producers signal its
        start via ``/H[2]`` of the linearization parameter dictionary
        (a pypdfbox-specific convention — the spec's /H array is
        documented as [primary_off primary_len overflow_off overflow_len],
        and slots 2-3 are absent on every-hint-in-the-primary-stream
        PDFs); when absent, callers should call
        :func:`parse_shared_object_hint_table` directly with the body
        sliced past the page-offset table.

        Returns the typed
        :class:`~pypdfbox.pdfparser.linearization_hint_table.SharedObjectHintTable`
        on success, or ``None`` when the document is not linearized, the
        hint stream cannot be located, ``/H[2]`` is missing, or the body
        is malformed."""
        from .linearization_hint_table import (  # noqa: PLC0415
            HintTableParseError,
            parse_shared_object_hint_table,
        )

        decoded = self._read_hint_stream_decoded()
        if decoded is None:
            return None
        offset = self._hint_subtable_offset(2)
        if offset is None or offset >= len(decoded):
            return None
        try:
            return parse_shared_object_hint_table(decoded[offset:])
        except HintTableParseError:
            return None

    def decode_thumbnail_hint_table(self) -> Any | None:
        """Decode the Thumbnail Hint Table out of the primary hint
        stream (PDF 32000-1 Annex F.5).

        The Thumbnail table sits after the Shared Object table in the
        decoded hint stream body. pypdfbox lets producers signal its
        start via ``/H[3]`` of the linearization parameter dictionary
        (a pypdfbox-specific convention paralleling
        :meth:`decode_shared_object_hint_table`).

        Returns the typed
        :class:`~pypdfbox.pdfparser.linearization_hint_table.ThumbnailHintTable`
        on success, or ``None`` when the document is not linearized, the
        hint stream cannot be located, ``/H[3]`` is missing, or the body
        is malformed. Many linearized PDFs ship without thumbnails — a
        ``None`` return is a normal, non-error outcome."""
        from .linearization_hint_table import (  # noqa: PLC0415
            HintTableParseError,
            parse_thumbnail_hint_table,
        )

        decoded = self._read_hint_stream_decoded()
        if decoded is None:
            return None
        offset = self._hint_subtable_offset(3)
        if offset is None or offset >= len(decoded):
            return None
        try:
            return parse_thumbnail_hint_table(decoded[offset:])
        except HintTableParseError:
            return None

    def _detect_linearization(self) -> None:
        """Parse the first indirect object after the header. If it is a
        dictionary carrying a truthy ``/Linearized`` entry, record it on
        :attr:`linearization_dict` and slurp the primary hint stream's
        bytes into :attr:`hint_table_bytes`. Quiet on every failure path
        — linearization is advisory metadata, never load-blocking.

        Cursor is restored to its post-header position before returning
        so :meth:`find_startxref_offset` (which scans from EOF anyway)
        and the rest of :meth:`parse` are unaffected."""
        saved = self._src.get_position()
        try:
            self._base.skip_whitespace()
            # An indirect-object header reads ``<num> <gen> obj``. Bail
            # out quietly if the first non-whitespace byte isn't a
            # decimal digit (some producers prepend comments — we
            # could call ``skip_comment`` here but per spec the
            # linearization dict, if present, is the very first object).
            peek = self._base.peek_byte()
            # pragma: no cover - linearization scan early-out on non-digit start
            if peek == RandomAccessRead.EOF or not (0x30 <= peek <= 0x39):  # pragma: no cover
                return
            try:
                obj_num = self._base.read_int()
                self._base.skip_whitespace()
                gen_num = self._base.read_int()
            except PDFParseError:
                return
            self._base.skip_whitespace()
            try:
                kw = self._base.read_keyword()
            except PDFParseError:
                return
            if kw != b"obj":
                return
            assert self._cos_parser is not None
            try:
                body = self._cos_parser.parse_direct_object()
            except PDFParseError:
                return
            if not isinstance(body, COSDictionary):
                return
            lin = body.get_dictionary_object(COSName.get_pdf_name("Linearized"))
            if not isinstance(lin, (COSInteger, COSFloat)):
                return
            if lin.value == 0:
                return
            # Genuine linearization dict — record it.
            self.linearization_dict = body
            # Slurp the primary hint stream's raw bytes (don't decode the
            # hint-table body; that's a deeper task). /H is an array of
            # 2 ints (primary only) or 4 ints (primary + overflow).
            h_arr = body.get_dictionary_object(COSName.get_pdf_name("H"))
            if isinstance(h_arr, COSArray) and h_arr.size() >= 2:
                h_off = h_arr.get(0)
                h_len = h_arr.get(1)
                if isinstance(h_off, (COSInteger, COSFloat)) and isinstance(
                    h_len, (COSInteger, COSFloat)
                ):
                    offset = int(h_off.value)
                    length = int(h_len.value)
                    file_len = self._src.length()
                    if 0 <= offset < file_len and 0 <= length <= file_len - offset:
                        # Snapshot cursor again — read_into moves it.
                        cursor_snap = self._src.get_position()
                        try:
                            self._src.seek(offset)
                            buf = bytearray(length)
                            n = self._src.read_into(buf)
                            self.hint_table_bytes = bytes(buf[: max(n, 0)])
                        finally:
                            self._src.seek(cursor_snap)
            # Discard the obj_num / gen_num to silence "unused" linters
            # without losing the parse-side validation above.
            del obj_num, gen_num
        finally:
            # Always restore the cursor to where the caller left it.
            self._src.seek(saved)

    # ---------- encryption / id introspection ----------

    def get_encryption_dictionary(self) -> COSDictionary | None:
        """Return the trailer's ``/Encrypt`` dictionary (resolved through
        an indirect reference if necessary) or ``None`` when the document
        is not encrypted. Mirrors PDFBox ``PDFParser.getEncryption()``.

        Must be called after :meth:`parse` so the trailer is populated."""
        trailer = self._resolver.get_trailer()
        if trailer is None:
            return None
        enc = trailer.get_dictionary_object(COSName.ENCRYPT)  # type: ignore[attr-defined]
        return enc if isinstance(enc, COSDictionary) else None

    def get_document_id(self) -> bytes | None:
        """Return the first element of the trailer's ``/ID`` array (the
        permanent file identifier per PDF 32000-1 §14.4) as bytes, or
        ``None`` when no ``/ID`` is present. The standard security handler
        keys file-encryption-key derivation off of this value."""
        trailer = self._resolver.get_trailer()
        if trailer is None:
            return None
        ids = trailer.get_dictionary_object(COSName.get_pdf_name("ID"))
        if not isinstance(ids, COSArray) or ids.size() == 0:
            return None
        first = ids.get(0)
        if isinstance(first, COSString):
            return first.get_bytes()
        return None

    # ---------- early-decryption surface (PDF 1.5+ encrypted xref streams) ----------

    def set_password(self, password: str | bytes | None) -> None:
        """Stage a password so the parser can instantiate a security
        handler the moment the trailer's ``/Encrypt`` becomes available.
        Required for documents whose xref *itself* is an encrypted stream
        — the handler must decipher the body before entries can be parsed.

        Pass ``None`` (the default) to keep the legacy flow where loading
        finishes first and ``PDDocument.decrypt`` walks the pool to attach
        a handler retroactively. Mirrors the ``password`` argument of
        upstream's ``PDFParser`` constructor overloads."""
        self._password = password

    def get_password(self) -> str | bytes | None:
        return self._password

    def get_security_handler(self) -> Any | None:
        """Return the security handler instantiated by the eager-decrypt
        path (see :meth:`set_password`), or ``None`` when no password was
        supplied or the document is not encrypted."""
        return self._security_handler

    def has_encrypted_xref_streams(self) -> bool:
        """``True`` when the parser saw at least one xref-stream object in
        a document that carries an ``/Encrypt`` entry. Set during
        :meth:`parse_xref_chain`; useful for tests and diagnostics."""
        return self._has_encrypted_xref_streams

    def _prepare_security_handler_if_needed(self) -> Any | None:
        """If the trailer carries ``/Encrypt`` and a password has been
        staged via :meth:`set_password`, build (and cache) a
        ``StandardSecurityHandler`` ready to decipher subsequent xref-stream
        bodies / objects. Returns the cached handler on subsequent calls."""
        if self._security_handler is not None:
            return self._security_handler
        if self._password is None:
            return None
        trailer = self._resolver.get_trailer()
        if trailer is None:
            return None
        # The trailer's /Encrypt entry is almost always an indirect ref
        # (``/Encrypt 4 0 R``) that hasn't been loader-attached yet —
        # ``populate_document`` runs after the xref chain is fully walked.
        # Resolve it manually here so the handler can stand up before any
        # downstream xref-stream body is touched.
        enc_dict = self._resolve_dict_entry(trailer, COSName.ENCRYPT)  # type: ignore[attr-defined]
        if not isinstance(enc_dict, COSDictionary):
            return None
        # Local imports — pdfparser must not depend on pdmodel at import
        # time (encryption lives one layer up).
        from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption  # noqa: PLC0415
        from pypdfbox.pdmodel.encryption.standard_security_handler import (  # noqa: PLC0415
            StandardDecryptionMaterial,
            StandardSecurityHandler,
        )

        encryption = PDEncryption(enc_dict)
        document_id = self._resolve_document_id(trailer) or b""
        # Pass the raw str through so the decryption material applies the
        # revision-aware charset (Latin-1 for r2-r4, UTF-8 for r5-r6) *and* the
        # r6 SaslPrep canonicalisation (PDF 32000-2 §7.6.4.3.4). Eagerly
        # UTF-8-encoding here would bypass both, so a password with a
        # compatibility character (e.g. the ``ﬀ`` ligature) hashed differently
        # from PDFBox. ``bytes`` callers pass already-encoded material through.
        password_material: str | bytes = (
            self._password
            if isinstance(self._password, str)
            else bytes(self._password)
        )
        handler = StandardSecurityHandler(encryption)
        handler.prepare_for_decryption(
            encryption,
            document_id,
            StandardDecryptionMaterial(password_material),
        )
        self._security_handler = handler
        return handler

    def _resolve_dict_entry(
        self, container: COSDictionary, key: COSName
    ) -> COSBase | None:
        """Return ``container[key]`` resolved through the parser's
        already-known xref entries, even when ``populate_document`` has
        not yet attached loaders. Direct values pass through unchanged.
        Used during the eager-decrypt bootstrap where the trailer is
        available but the object pool is still being assembled."""
        item = container.get_item(key)
        if item is None:
            return None
        if not isinstance(item, COSObject):
            return item
        if item.is_object_loaded():
            return item.get_object()
        # Look up the entry in the resolver and parse it inline. We do
        # NOT register a loader on the COSObject here — populate_document
        # will do that for the whole pool when the chain is complete.
        target_key = COSObjectKey(
            item.get_object_number(), item.get_generation_number()
        )
        xref = self._resolver.get_xref_table()
        entry = xref.get(target_key)
        if entry is None or entry.compressed_index == -1:
            return None
        if entry.type is XrefType.COMPRESSED:
            # Object lives inside an object stream — that decoder runs
            # later; leave the eager bootstrap dormant in that case.
            # ``XrefType.STREAM`` (uncompressed entry from an xref stream)
            # still carries a real byte offset and can be loaded inline,
            # which is exactly the path encrypted PDF 1.5+ documents need:
            # /Encrypt object is referenced by an xref-STREAM entry, and
            # we have to materialise it here so the security handler can
            # be built before any other xref-stream body is decoded.
            return None
        # Snapshot cursor, parse the indirect, restore cursor so the
        # outer xref walker isn't disturbed.
        saved = self._src.get_position()
        try:
            return self._load_indirect_object_at(entry.offset, item)
        finally:
            self._src.seek(saved)

    def _resolve_document_id(self, trailer: COSDictionary) -> bytes | None:
        """``/ID`` companion to :meth:`_resolve_dict_entry`. Returns the
        first element of the ID array as bytes, or ``None``."""
        ids = trailer.get_dictionary_object(COSName.get_pdf_name("ID"))
        if not isinstance(ids, COSArray) or ids.size() == 0:
            return None
        first = ids.get(0)
        if isinstance(first, COSString):
            return first.get_bytes()
        return None

    # ---------- step 1: header ----------

    def parse_header(self) -> float:
        """Validate the ``%PDF-x.y`` (or ``%FDF-x.y``) magic and return the
        version as a float. Tolerates up to 1024 bytes of leading garbage
        (some producers prepend MIME envelopes / shebangs / etc.).

        FDF (Forms Data Format) files share PDF's object/xref/trailer wire
        structure but begin with ``%FDF-`` instead of ``%PDF-``. Accepting
        both markers here lets the same xref-walking machinery parse an FDF
        — matching upstream PDFBox, whose generic ``COSParser.parseHeader``
        is parametrised over the marker string for exactly this reason."""
        scan_window = 1024
        self._src.seek(0)
        head = bytearray()
        while len(head) < scan_window:
            b = self._src.read()
            if b == RandomAccessRead.EOF:
                break
            head.append(b)
        idx = bytes(head).find(b"%PDF-")
        marker_len = len(b"%PDF-")
        if idx < 0:
            # FDF files carry an %FDF- header; the rest of the structure is
            # identical, so fall through to the same version parse.
            idx = bytes(head).find(b"%FDF-")
            if idx < 0:
                # Mirrors upstream COSParser.parseHeader (PDFBox 3.0.7,
                # COSParser.java ~L1619) returning ``false`` — NOT throwing —
                # when the marker is absent from the scan window. The "not a
                # PDF" decision is deferred to PDFParser.parse(boolean), which
                # in lenient mode logs a warning and falls through to
                # brute-force recovery (so leading binary garbage that pushes
                # the header past the window still recovers), and in strict
                # mode raises. ``_HeaderNotFoundError`` is the in-band signal
                # for that distinction; a *malformed version* (marker present)
                # still raises ``PDFParseError`` below, matching upstream's
                # IOException("Error getting header version:").
                raise _HeaderNotFoundError(
                    "missing %PDF- header (not a PDF file)"
                )
        # Position the cursor just past the 5-byte marker for version parsing.
        self._src.seek(idx + marker_len)
        version_bytes = bytearray()
        while True:
            b = self._src.read()
            if b == RandomAccessRead.EOF or b in (0x0A, 0x0D, 0x20):
                break
            version_bytes.append(b)
        try:
            return float(version_bytes.decode("ascii"))
        except ValueError as exc:
            raise PDFParseError(f"malformed %PDF version {version_bytes!r}") from exc

    def parse_pdf_header(self) -> bool:
        """Validate the ``%PDF-x.y`` magic and record the version on the
        underlying :class:`COSDocument` (when one has been instantiated).
        Returns ``True`` on success, ``False`` when no header is found.

        Java-style boolean alias for :meth:`parse_header` — mirrors
        upstream ``COSParser.parsePDFHeader()`` whose contract is "did we
        find a PDF header?". A *malformed version* (marker present, digits
        unparseable) still propagates as ``PDFParseError`` — matching upstream
        ``parseHeader`` throwing ``IOException("Error getting header
        version:")`` rather than returning ``false`` for that case."""
        try:
            version = self.parse_header()
        except _HeaderNotFoundError:
            # Upstream COSParser.parseHeader rewinds to the document start
            # before returning false; mirror that so the fall-through to
            # linearization detection / startxref location / brute-force
            # recovery sees a clean cursor.
            self._src.seek(0)
            return False
        if self._document is not None:
            self._document.set_version(version)
        self._version = version
        return True

    # ---------- step 2: locate startxref ----------

    def find_startxref_offset(self, *, validate_bounds: bool = True) -> int:
        """Return the byte offset given by the ``startxref`` directive
        near the end of the file. Raises ``PDFParseError`` if not found.

        The trailing-byte scan window honours :meth:`get_eof_lookup_range`
        (default :data:`_TAIL_SCAN_BYTES`), matching upstream's
        ``readTrailBytes`` knob. ``validate_bounds=False`` is used by the
        lenient parse path so an invalid declared offset can still be
        corrected by the brute-force xref search."""
        length = self._src.length()
        scan_from = max(0, length - self._eof_lookup_range)
        self._src.seek(scan_from)
        tail = bytearray(length - scan_from)
        n = self._src.read_into(tail)
        tail_bytes = bytes(tail[: n if n > 0 else 0])
        marker = b"startxref"
        idx = tail_bytes.rfind(marker)
        if idx < 0:
            raise PDFParseError("missing 'startxref' directive near EOF")
        # Re-position absolute and skip past the keyword.
        self._src.seek(scan_from + idx + len(marker))
        self._base.skip_whitespace()
        offset = self._base.read_int()
        # Defensive: ensure the offset is plausible.
        if validate_bounds and not 0 <= offset < length:
            raise PDFParseError(f"startxref offset {offset} out of file bounds")
        return offset

    # ---------- step 3: xref chain ----------

    def parse_xref_chain(self, start_offset: int) -> None:
        """Walk xref → trailer → ``/Prev`` until the chain terminates or a
        cycle is detected."""
        offset = start_offset
        while offset >= 0:
            offset = self._recover_xref_offset_if_needed(offset)
            if self._resolver.has_visited(offset):
                # Cycle in /Prev — stop instead of looping.
                break
            self._resolver.begin_section(offset)
            self.parse_xref_section_at(offset)
            trailer = self._resolver.get_current_trailer()
            # The /Prev pointer for the *current* iteration must come from
            # the section we just parsed, not the merged trailer (which is
            # built up over all sections).
            current_prev = -1
            if trailer is not None and trailer.contains_key(COSName.get_pdf_name("Prev")):
                prev_obj = trailer.get_dictionary_object(COSName.get_pdf_name("Prev"))
                if isinstance(prev_obj, COSInteger):
                    current_prev = prev_obj.value
            offset = current_prev

    def _recover_xref_offset_if_needed(self, offset: int) -> int:
        """Return a usable xref offset, recovering in lenient mode when
        ``startxref`` or ``/Prev`` points near but not at the section.

        PDFBox's lenient parser falls back to ``bfSearchForXRef`` when a
        declared xref position is malformed. Keep the correction before
        ``XrefTrailerResolver.begin_section`` so visited-offset tracking
        records the real section start."""
        if self._xref_section_starts_at(offset):
            return offset
        if not self._lenient or self._cos_parser is None:
            return offset
        recovered = self._cos_parser.bf_search_for_xref(offset)
        if recovered >= 0 and self._xref_section_starts_at(recovered):
            return recovered
        return offset

    def _xref_section_starts_at(self, offset: int) -> bool:
        """Lightweight shape check for a traditional xref table or xref
        stream object at ``offset``. Cursor position is preserved."""
        if offset < 0 or offset >= self._src.length():
            return False
        saved = self._src.get_position()
        try:
            self._src.seek(offset)
            self._base.skip_whitespace()
            peek = self._base.peek_byte()
            if peek == 0x78:  # 'x'
                return self._base.read_keyword() == b"xref"
            if not (0x30 <= peek <= 0x39) or self._cos_parser is None:
                return False
            # Xref streams start as indirect-object definitions whose
            # dictionary advertises /Type /XRef.
            self._base.read_int()
            self._base.skip_whitespace()
            self._base.read_int()
            self._base.skip_whitespace()
            if self._base.read_keyword() != b"obj":
                return False
            self._base.skip_whitespace()
            if self._base.peek_byte() != 0x3C:  # '<'
                return False
            body = self._cos_parser.parse_cos_dictionary()
            type_obj = body.get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
            return isinstance(type_obj, COSName) and type_obj.name == "XRef"
        except PDFParseError:
            return False
        finally:
            self._src.seek(saved)

    def parse_xref_section_at(self, offset: int) -> None:
        """Parse one xref section + trailer starting at ``offset``."""
        self._src.seek(offset)
        self._base.skip_whitespace()
        # Distinguish traditional ``xref`` keyword from an xref stream
        # (PDF 1.5+: an indirect object whose dict has /Type /XRef).
        peek = self._base.peek_byte()
        if peek == 0x78:  # 'x' — likely the "xref" keyword
            self._parse_traditional_xref_section()
            # PDF 1.5 hybrid layout (PDF 32000-1 §7.5.8.4): when the
            # trailer carries ``/XRefStm`` alongside a traditional xref
            # table, also parse that supplementary xref stream into the
            # *same* section so its compressed-object entries overwrite
            # the legacy table's free-list stubs for the same object
            # numbers. Mirrors upstream ``COSParser`` lines 372..414.
            trailer = self._resolver.get_current_trailer()
            if trailer is not None and trailer.contains_key(
                COSName.get_pdf_name("XRefStm")
            ):
                stm_obj = trailer.get_dictionary_object(
                    COSName.get_pdf_name("XRefStm")
                )
                if isinstance(stm_obj, COSInteger) and stm_obj.value > 0:
                    try:
                        self._handle_xref_stream_at(
                            stm_obj.value, is_hybrid=True
                        )
                        # pragma: parse() always sets _document before
                        # parse_xref_chain runs, so the False arm is unreachable.
                        if self._document is not None:  # pragma: no branch
                            self._document.set_has_hybrid_xref()
                    except PDFParseError:
                        if not self._lenient:
                            raise
                        _LOG.exception(
                            "failed to parse hybrid /XRefStm at offset %d",
                            stm_obj.value,
                        )
            # Once the trailer has been merged, eagerly stand up the
            # security handler if the caller staged a password — the next
            # iteration of /Prev may land on an xref STREAM, and that
            # body has to be deciphered before its entries decode.
            self._prepare_security_handler_if_needed()
        else:
            # PDF 1.5+ xref-stream (an indirect object whose dict carries
            # /Type /XRef and whose body holds packed xref entries).
            # The handler also wires the early-decryption bootstrap needed
            # before encrypted object bodies are parsed later.
            self._handle_xref_stream_at(offset)

    def _handle_xref_stream_at(self, offset: int, is_hybrid: bool = False) -> None:
        """Parse one xref-stream object (PDF 32000-1 §7.5.8): read its
        dictionary, decode the body via ``COSStream.create_input_stream``
        (so /Filter chains — typically ``/FlateDecode`` with a PNG
        predictor — are unwound), and register one xref entry per packed
        record.

        Also doubles as the early-decryption surface: when the stream
        dictionary carries ``/Encrypt`` (which can only happen in a
        hybrid layout, since the stream itself can't reference the
        document's own /Encrypt), or when the trailer of a previous
        section already had it, the staged password (see
        :meth:`set_password`) is used to attach a security handler to
        the stream before the body is decoded.

        ``is_hybrid=True`` is the PDF 1.5 hybrid path (xref stream
        supplementing a traditional xref table within the same section).
        In that mode we skip the trailer-set / encrypt-bootstrap branches
        — the traditional table already supplied them — and only add the
        stream's entries to the current section."""
        # Reset cursor to the indirect-object header and parse the
        # ``n g obj`` line + dictionary + ``stream`` body.
        self._src.seek(offset)
        self._base.skip_whitespace()
        self._base.read_int()
        self._base.skip_whitespace()
        self._base.read_int()
        self._base.skip_whitespace()
        kw = self._base.read_keyword()
        if kw != b"obj":
            raise PDFParseError(
                f"expected 'obj' at offset {offset}, got {kw!r}",
                position=self._base.position,
            )
        assert self._cos_parser is not None
        body = self._cos_parser.parse_direct_object()
        if not isinstance(body, COSDictionary):
            raise PDFParseError(
                "xref-stream object body is not a dictionary",
                position=self._base.position,
            )
        type_obj = body.get_dictionary_object(COSName.TYPE)  # type: ignore[attr-defined]
        if not (isinstance(type_obj, COSName) and type_obj.name == "XRef"):
            raise PDFParseError(
                "xref-stream dict missing /Type /XRef",
                position=self._base.position,
            )
        # Convert the parsed dict to a stream and read its body using the
        # same machinery the regular indirect-object loader uses.
        stream = self._convert_dict_to_stream(body)
        # The dictionary may reference /Length indirectly; the body-read
        # path through ``_read_stream_body`` already handles that.
        self._base.skip_whitespace()
        peek = self._base.peek_byte()
        if peek != 0x73:
            raise PDFParseError(
                "xref-stream object missing 'stream' keyword",
                position=self._base.position,
            )
        kw2 = self._base.read_keyword()
        if kw2 != b"stream":
            raise PDFParseError(
                f"expected 'stream' in xref-stream object, got {kw2!r}",
                position=self._base.position,
            )
        self._read_stream_body(stream)
        # Per ISO 32000-2 §7.6.2 cross-reference streams "shall not be
        # encrypted". Mark this stream so the COSStream decode path skips
        # the security-handler pass even after the document-level handler
        # walk in ``PDDocument.decrypt`` retroactively wires one onto
        # every other stream — otherwise the same body would be deciphered
        # twice (once now during xref load, once later) and the second
        # pass would garble the entries.
        stream.set_skip_encryption(True)
        if not is_hybrid:
            # Tag the section currently being built as an xref STREAM so the
            # resolved document advertises ``is_xref_stream()``. A hybrid
            # /XRefStm supplements a traditional table within the SAME logical
            # section and must NOT flip that section's type — upstream
            # classifies a hybrid file as a TABLE for incremental-save xref
            # encoding (``COSWriter.doWriteXRefInc`` treats hasHybridXRef as a
            # table), so the ``is_hybrid`` guard leaves the type at TABLE.
            self._resolver.set_current_xref_type(XrefType.STREAM)
            # Treat the xref-stream dict as a trailer fragment so /Encrypt /ID
            # /Root /Size are visible to /Prev walking and the early-handler
            # bootstrap. Existing trailer keys from previously-parsed sections
            # still win — the resolver merges newest-first.
            self._resolver.set_trailer(stream)
            # Diagnostic flag for callers / tests.
            if stream.contains_key(COSName.ENCRYPT):  # type: ignore[attr-defined]
                self._has_encrypted_xref_streams = True
        # Decode the body and walk the packed entries — this populates
        # the resolver with byte offsets for every object, including the
        # /Encrypt object itself. Has to run BEFORE the handler bootstrap
        # because ``_prepare_security_handler_if_needed`` resolves
        # ``/Encrypt`` through the resolver to grab its dict.
        self._decode_xref_stream_entries(stream)
        if is_hybrid:
            return
        # Now that entries are registered, eagerly stand up the security
        # handler if /Encrypt is in scope and a password was staged. The
        # handler isn't used to decrypt THIS stream (xref streams are
        # exempt — see set_skip_encryption above), but it must exist
        # before subsequent /Prev-chained sections or downstream pool
        # objects are touched.
        if stream.contains_key(COSName.ENCRYPT):  # type: ignore[attr-defined]
            self._prepare_security_handler_if_needed()

    def _decode_xref_stream_entries(self, stream: COSStream) -> None:
        """Decode an xref stream's body and register one xref entry per
        record. PDF 32000-1 §7.5.8.3."""
        # /W [w1 w2 w3] — field widths in bytes. w1=0 means "type defaults
        # to 1 (uncompressed in-use)"; w3=0 means "generation defaults to 0".
        w_obj = stream.get_dictionary_object(COSName.get_pdf_name("W"))
        if not isinstance(w_obj, COSArray) or w_obj.size() < 3:
            raise PDFParseError("xref stream missing or malformed /W")
        widths: list[int] = []
        for i in range(3):
            wi = w_obj.get(i)
            if not isinstance(wi, COSInteger):
                raise PDFParseError(f"xref stream /W[{i}] is not an integer")
            widths.append(wi.value)
        w1, w2, w3 = widths
        if any(width < 0 for width in widths):
            raise PDFParseError("xref stream /W contains a negative width")
        # /Index [first1 count1 first2 count2 ...]; default = [0 /Size].
        index_pairs: list[tuple[int, int]] = []
        idx_obj = stream.get_dictionary_object(COSName.get_pdf_name("Index"))
        if isinstance(idx_obj, COSArray):
            if idx_obj.size() % 2 != 0:
                raise PDFParseError("xref stream /Index has odd length")
            for i in range(0, idx_obj.size(), 2):
                first_obj = idx_obj.get(i)
                count_obj = idx_obj.get(i + 1)
                if not isinstance(first_obj, COSInteger) or not isinstance(
                    count_obj, COSInteger
                ):
                    raise PDFParseError("xref stream /Index entries must be integers")
                first = first_obj.value
                count = count_obj.value
                _validate_xref_index_pair(first, count)
                index_pairs.append((first, count))
        else:
            size_obj = stream.get_dictionary_object(COSName.SIZE)  # type: ignore[attr-defined]
            if not isinstance(size_obj, COSInteger):
                raise PDFParseError("xref stream missing /Size and /Index")
            _validate_xref_index_pair(0, size_obj.value)
            index_pairs.append((0, size_obj.value))
        # Decode the body through any /Filter chain (and the security
        # handler, when one is attached).
        with stream.create_input_stream() as src:
            body = src.read()
        record_size = w1 + w2 + w3
        if record_size <= 0:
            raise PDFParseError("xref stream /W field widths sum to zero")
        # PDFBOX-6037: cap the entry width at 20 bytes — anything wider
        # is malformed and would tend to mask attacker-supplied size
        # explosions. Mirrors upstream
        # ``PDFXrefStreamParser.initParserValues``.
        if record_size > 20:
            raise PDFParseError(
                f"xref stream /W defines an entry wider than 20 bytes: {widths!r}"
            )
        cursor = 0
        for first_obj_num, object_count in index_pairs:
            for object_index in range(object_count):
                if cursor + record_size > len(body):
                    raise PDFParseError(
                        "xref stream body truncated relative to /Index"
                    )
                record = body[cursor : cursor + record_size]
                cursor += record_size
                # Slice each field; honour the spec's defaults when w_i==0.
                field1 = (
                    1 if w1 == 0 else int.from_bytes(record[0:w1], "big")
                )
                field2 = int.from_bytes(record[w1 : w1 + w2], "big")
                field3 = (
                    0
                    if w3 == 0
                    else int.from_bytes(record[w1 + w2 : w1 + w2 + w3], "big")
                )
                obj_num = first_obj_num + object_index
                if field1 == 0:
                    # Free entry — record it but flag with compressed_index=-1
                    # so populate_document() skips it (matches the traditional
                    # 'f' flag path).
                    self._resolver.set_entry(
                        COSObjectKey(obj_num, field3),
                        XrefEntry(
                            type=XrefType.STREAM,
                            offset=field2,
                            compressed_index=-1,
                        ),
                    )
                elif field1 == 1:
                    # Uncompressed: field2 = byte offset, field3 = generation.
                    self._resolver.set_entry(
                        COSObjectKey(obj_num, field3),
                        XrefEntry(type=XrefType.STREAM, offset=field2),
                    )
                elif field1 == 2:
                    # Compressed: field2 = ObjStm obj number, field3 = index
                    # within stream. Generation is always 0 per spec.
                    self._resolver.set_entry(
                        COSObjectKey(obj_num, 0),
                        XrefEntry(
                            type=XrefType.COMPRESSED,
                            offset=field2,
                            compressed_index=field3,
                        ),
                    )
                else:
                    # PDF 32000-1 §7.5.8.3: "any other value of the type
                    # field shall be interpreted as a reference to the null
                    # object." Treat as a free slot.
                    self._resolver.set_entry(
                        COSObjectKey(obj_num, 0),
                        XrefEntry(
                            type=XrefType.STREAM,
                            offset=0,
                            compressed_index=-1,
                        ),
                    )

    def _parse_traditional_xref_section(self) -> None:
        """Parse ``xref <subsections> trailer << ... >>``.

        Mirrors upstream ``COSParser.parseXrefTable``'s leniency: each
        subsection header is read as a line and split on whitespace; a header
        that is not exactly two integers (an orphan entry left over from a wrong
        ``/count``, or a non-numeric / mistyped header), and likewise a
        malformed entry row inside the declared count (wrong field count, an
        unknown type char other than ``n`` / ``f``), is NOT a hard error —
        upstream logs "Unexpected XRefTable Entry" and *breaks* the subsection
        loop, then recovers the (possibly incomplete) object set with a
        brute-force scan. We reproduce that: a malformed table breaks early and
        sets ``_xref_table_recovery_needed`` so the chain walker merges the
        brute-force object map afterwards, instead of raising."""
        kw = self._base.read_keyword()
        if kw != b"xref":
            raise PDFParseError(f"expected 'xref', got {kw!r}", position=self._base.position)
        # Some producers omit the EOL after 'xref' but the spec requires it
        # and PDFBox tolerates either way; skip whitespace defensively.
        self._base.skip_whitespace()
        broke_early = False
        while True:
            self._base.skip_whitespace()
            peek = self._base.peek_byte()
            if peek == 0x74:  # 't' — start of 'trailer'
                break
            if peek == RandomAccessRead.EOF:
                raise PDFParseError("unexpected EOF inside xref section")
            header = self._read_xref_subsection_header()
            if header is None:
                # Malformed subsection header (upstream's "Unexpected
                # XRefTable Entry" break): stop consuming subsections; the
                # trailer keyword is located below and recovery fills gaps.
                broke_early = True
                break
            first_obj, count = header
            for i in range(count):
                # Defensive stop: an entry line that turns out to be the
                # 'trailer' keyword (an over-long declared count) must not be
                # consumed as an entry. Upstream guards with the same peek.
                self._base.skip_whitespace()
                p = self._base.peek_byte()
                if p == 0x74 or p == RandomAccessRead.EOF:  # 't' / EOF
                    break
                try:
                    self._read_xref_entry(first_obj + i)
                except PDFParseError:
                    # Malformed entry row (wrong field count / unknown type
                    # char): upstream's "Unexpected XRefTable Entry" break.
                    # Stop this subsection and recover the rest by brute force.
                    broke_early = True
                    break
            if broke_early:
                break
        if broke_early:
            self._xref_table_recovery_needed = True
        # A malformed break may leave the cursor before an orphan entry line
        # rather than at 'trailer'; scan forward to the 'trailer' keyword the
        # way upstream's readLine loop does.
        self._base.skip_whitespace()
        if self._base.peek_byte() != 0x74:  # not at 't'
            self._seek_to_trailer_keyword()
        # The scan above may have run to EOF (no 'trailer' keyword in the
        # file at all). read_keyword would raise on an empty span; in lenient
        # mode that is a recoverable "trailer absent" condition, not a hard
        # error — mark recovery and let the rebuild path supply a trailer.
        if self._base.peek_byte() == RandomAccessRead.EOF:
            if self._lenient:
                self._xref_table_recovery_needed = True
                return
            raise PDFParseError("xref table not followed by a trailer")
        kw = self._base.read_keyword()
        if kw != b"trailer":
            # Upstream COSParser.parseXrefTable does NOT hard-fail when the
            # 'trailer' keyword is absent (e.g. a producer that wrote the xref
            # table but no trailer at all, or whose trailer was truncated): in
            # lenient mode it logs and continues, leaving the section's trailer
            # unset so retrieveTrailer's rebuild (driven by a missing /Root)
            # reconstructs it from the brute-force object scan. Reproduce that
            # here — mark recovery and return so parse() rebuilds the trailer
            # rather than raising. Strict mode still surfaces the error.
            if self._lenient:
                self._xref_table_recovery_needed = True
                return
            raise PDFParseError(
                f"expected 'trailer', got {kw!r}", position=self._base.position
            )
        self._base.skip_whitespace()
        assert self._cos_parser is not None  # established by parse()
        try:
            trailer = self._cos_parser.parse_cos_dictionary()
        except PDFParseError:
            # A trailer dictionary that opened but never closed ('<<' with no
            # matching '>>') / is otherwise unparseable: upstream tolerates the
            # broken trailer in lenient mode and falls back to the brute-force
            # rebuild. Mark recovery and leave the section trailer unset so the
            # rebuild path supplies a reconstructed trailer; re-raise in strict.
            if self._lenient:
                self._xref_table_recovery_needed = True
                return
            raise
        self._resolver.set_trailer(trailer)

    def _read_xref_subsection_header(self) -> tuple[int, int] | None:
        """Read one ``<first> <count>`` subsection header.

        Returns ``(first_obj, count)`` on success, or ``None`` when the line
        is not exactly two integers — mirroring upstream
        ``COSParser.parseXrefTable``'s ``splitString.length != 2`` /
        ``NumberFormatException`` "Unexpected XRefTable Entry" break. The
        cursor is left at the start of the offending line so the caller's
        trailer-keyword scan can recover. Note an orphan *entry* line such as
        ``0000000115 00000 n`` splits into THREE tokens and so is correctly
        rejected as a header here."""
        saved = self._base.position
        line = self._base.read_until_eol()
        self._base.skip_eol()
        parts = line.split()
        if len(parts) != 2:
            self._src.seek(saved)
            return None
        try:
            first_obj = int(parts[0].decode("ascii"))
            count = int(parts[1].decode("ascii"))
        except ValueError:
            self._src.seek(saved)
            return None
        if count < 0:
            self._src.seek(saved)
            return None
        return first_obj, count

    def _seek_to_trailer_keyword(self) -> None:
        """Advance the cursor to the next ``trailer`` keyword, skipping over
        orphan xref-entry lines left behind by a lenient subsection break.

        Mirrors upstream's ``readLine`` loop, which keeps consuming lines after
        an "Unexpected XRefTable Entry" until it reaches ``trailer`` (or EOF).
        Bounded by a sane line budget so a pathological file can't spin."""
        for _ in range(1 << 16):
            self._base.skip_whitespace()
            peek = self._base.peek_byte()
            if peek == 0x74 or peek == RandomAccessRead.EOF:  # 't' / EOF
                return
            self._base.read_until_eol()
            self._base.skip_eol()

    def _read_xref_entry(self, object_number: int) -> None:
        """Read one traditional xref entry line."""
        line = self._base.read_until_eol()
        self._base.skip_eol()
        offset, generation, flag = _parse_xref_entry_line(line)
        if flag == "n":
            self._resolver.set_entry(
                COSObjectKey(object_number, generation),
                XrefEntry(type=XrefType.TABLE, offset=offset),
            )
        elif flag == "f":
            # Free entry — record it so a later /Prev section's "n" can be
            # detected as superseding it. Storing the offset (which is
            # actually "next free object number") is mostly informational
            # at this stage; the writer will care later.
            self._resolver.set_entry(
                COSObjectKey(object_number, generation),
                XrefEntry(type=XrefType.TABLE, offset=offset, compressed_index=-1),
            )
        else:
            raise PDFParseError(f"unknown xref entry flag {flag!r}")

    # ---------- step 4: populate document ----------

    def populate_document(self) -> None:
        """Walk the consolidated xref and attach a loader to every
        in-use COSObject in the document pool.

        Also mirrors what Apache PDFBox does after consolidating the xref:
        copy the resolved byte-offset map into ``COSDocument`` so
        ``getXrefTable()`` reflects the parsed object set. Upstream
        ``COSParser`` calls ``document.addXRefTable(...)``; pypdfbox builds
        the same ``COSObjectKey -> offset`` map here following the upstream
        offset convention — a positive value is the absolute file offset of
        the object definition; a negative value encodes object-stream
        membership as ``-objstm_object_number``."""
        assert self._document is not None
        xref = self._resolver.get_xref_table()
        offset_table: dict[COSObjectKey, int] = {}
        for key, entry in xref.items():
            if entry.compressed_index == -1:
                # Free entry — skip; PDFBox does not register a placeholder
                # for free slots in the regular object pool. A LENIENT-mode
                # reference to a free slot whose ``n g obj`` body still exists
                # in the file is resolved on demand via the brute-force
                # fallback installed below (mirrors COSParser's lazy
                # bfSearchForObjects path), not via a pre-attached loader.
                continue
            cos_obj = self._document.get_object_from_pool(key)
            cos_obj.set_loader(self._make_loader(entry))
            if entry.type is XrefType.COMPRESSED:
                # Compressed object: ``entry.offset`` holds the owning ObjStm
                # object number. Record it as ``-objstm_object_number`` to
                # match the COSDocument/PDFBox convention.
                offset_table[key] = -entry.offset
            else:
                offset_table[key] = entry.offset
        if offset_table:
            self._document.add_xref_table(offset_table)
        # Install the lenient free/missing-key resolution fallback so a
        # reference to a free (or absent) xref slot whose ``n g obj`` body
        # still exists in the file resolves on demand. Mirrors upstream
        # ``COSParser.parseObjectDynamically``'s ``bfSearchForObjects``
        # fallback (only in lenient mode).
        if self._lenient and self._cos_parser is not None:
            self._cos_parser.set_missing_object_resolver(
                self._resolve_missing_object
            )

    def _resolve_missing_object(self, key: COSObjectKey) -> COSBase | None:
        """Brute-force-resolve a referenced object that the consolidated xref
        does not carry as a usable in-use entry (a free slot, or a key beyond
        the table) but whose ``n g obj`` body is present in the file.

        Mirrors the lenient branch of upstream
        ``COSParser.parseObjectDynamically``: when the xref yields no offset
        for a referenced key, PDFBox runs ``bfSearchForObjects`` (cached) and
        resolves from the recovered offset, returning null when the scan never
        found the object. Generation must match — the brute-force scan keys on
        ``(object_number, generation)`` exactly, so a wrong-generation
        reference still resolves to null."""
        offsets = self._brute_force_offsets()
        offset = offsets.get(key)
        if offset is None or offset <= 0:
            return None
        cos_obj = self._document.get_object_from_pool(key)
        try:
            return self._load_indirect_object_at(offset, cos_obj)
        except PDFParseError:
            return None

    def _brute_force_offsets(self) -> dict[COSObjectKey, int]:
        """Cached brute-force object scan for the lenient free/missing
        resolution fallback. Mirrors upstream ``COSParser`` caching the scan
        in ``bfCOSObjectKeyOffsets`` so a document with several dangling
        references scans the body only once.

        Uses :meth:`_brute_force_recovered_offsets` (the EOF-aware variant
        with upstream's deferred-final-object drop) rather than the raw
        ``bf_search_for_objects`` — upstream ``bfSearchForObjects`` applies the
        same ``bfSearchForLastEOFMarker`` rule, so a trailing object header
        that runs to EOF with no ``endobj`` / ``%%EOF`` must NOT be recovered."""
        if self._bf_offsets_cache is None:
            try:
                self._bf_offsets_cache = self._brute_force_recovered_offsets()
            except PDFParseError:
                self._bf_offsets_cache = {}
        return self._bf_offsets_cache

    def _brute_force_recovered_offsets(self) -> dict[COSObjectKey, int]:
        """``bf_search_for_objects`` with upstream's final-object EOF rule.

        Mirrors the deferred-``put`` shape of upstream
        ``BruteForceParser.bfSearchForObjects``: each ``n g obj`` header is only
        committed to the offset map once the NEXT object header is seen, and the
        final deferred object is committed at loop end ONLY when either the file
        contained a ``%%EOF`` marker (``bfSearchForLastEOFMarker`` returned a
        real position rather than its ``Long.MAX_VALUE`` "none found" sentinel)
        OR that last object was terminated by ``endobj`` / ``endstream``
        (``endOfObjFound``). A trailing object that runs straight to EOF with no
        ``endobj`` and no ``%%EOF`` anywhere in the file is therefore DROPPED —
        upstream treats it as an incomplete tail, not a recoverable object.

        ``bf_search_for_objects`` itself records every header unconditionally
        (it has no document-level view of the EOF marker), so the
        whole-document rebuild applies the drop here. The dropped key is the one
        whose header offset is the largest — i.e. the last header in scan order
        — matching the single deferred slot upstream never flushes."""
        assert self._cos_parser is not None
        offsets = self._cos_parser.bf_search_for_objects()
        if not offsets:
            return offsets
        data = self._read_source_bytes()
        if data is None:
            return offsets
        # A real ``%%EOF`` anywhere → upstream always flushes the last object.
        if data.rfind(b"%%EOF") != -1:
            return offsets
        # No ``%%EOF``: the last object (highest header offset) is flushed only
        # if it was ``endobj`` / ``endstream`` terminated. Find the object whose
        # body is the file tail and check for a terminator after its header.
        last_key = max(offsets, key=lambda k: offsets[k])
        last_offset = offsets[last_key]
        tail = data[last_offset:]
        if b"endobj" in tail or b"endstream" in tail:
            return offsets
        # Drop the unterminated trailing object (return a fresh dict so the
        # caller's later mutations don't leak back into the parser).
        return {k: v for k, v in offsets.items() if k != last_key}

    def _read_source_bytes(self) -> bytes | None:
        """Snapshot the whole source as ``bytes`` (position preserved), or
        ``None`` if it cannot be read. Used by the brute-force recovery
        helpers that need a document-level view of the raw file."""
        try:
            saved = self._src.get_position()
        except Exception:  # noqa: BLE001 - source without a position cursor
            return None
        try:
            length = self._src.length()
            self._src.seek(0)
            buf = bytearray(length)
            read = 0
            while read < length:
                n = self._src.read_into(buf, read, length - read)
                if n <= 0:
                    break
                read += n
            return bytes(buf[:read])
        except Exception:  # noqa: BLE001 - unreadable source: skip the EOF rule
            return None
        finally:
            with contextlib.suppress(Exception):
                self._src.seek(saved)

    def _rebuild_document_from_brute_force(self) -> None:
        """Reconstruct the cross-reference + trailer entirely from a
        brute-force ``n g obj`` scan of the body.

        Mirrors the recovery half of upstream ``COSParser.retrieveTrailer``
        / ``rebuildTrailer``: used when ``startxref`` is missing or the
        located xref section cannot be parsed. Every recovered object
        becomes a TABLE entry in a fresh resolver section so the standard
        :meth:`populate_document` machinery can attach lazy loaders, and the
        rebuilt trailer (with brute-force ``/Root`` / ``/Info`` detection)
        is registered on that section."""
        assert self._cos_parser is not None
        offsets = self._brute_force_recovered_offsets()
        if not offsets:
            # No ``n g obj`` definition anywhere in the body: there is nothing
            # to rebuild a cross-reference from. PDFBox's brute-force recovery
            # likewise gives up here (Loader.loadPDF raises), so a file that is
            # only a header + trailing garbage must surface a parse failure
            # rather than "recover" into an empty, rootless document.
            raise PDFParseError(
                "no recoverable objects found during brute-force rebuild"
            )
        trailer = self._cos_parser.rebuild_trailer()
        # Register a synthetic section (start offset -1: position unknown)
        # holding one TABLE entry per recovered object. ``begin_section``
        # with a negative offset keeps it out of visited-offset tracking.
        self._resolver.begin_section(-1)
        for key, offset in offsets.items():
            self._resolver.set_entry(
                key, XrefEntry(type=XrefType.TABLE, offset=offset)
            )
        # When the plain-object scan recovered no /Root, the catalog may be
        # packed inside an object stream — mirror upstream
        # ``BruteForceParser.rebuildTrailer`` (BruteForceParser.java line 840-848):
        # ``if (!bfSearchForTrailer && !searchForTrailerItems) {
        # bfSearchForObjStreams(); searchForTrailerItems(); }``. Recover the
        # ObjStm members, register them as COMPRESSED entries, and re-derive
        # /Root + /Info from the now-reachable compressed catalog candidate.
        if trailer.get_item(COSName.ROOT) is None:
            self._recover_obj_stream_trailer_items(offsets, trailer)
        self._resolver.set_trailer(trailer)
        self._cos_parser.set_trailer_was_rebuild(True)
        # ``startxref`` is unknown after a full rebuild. Leave the
        # COSDocument's start-xref at its default (0 — the "no trailing
        # startxref" sentinel the incremental writer already treats as
        # "synthesised / unsaved"); the setter rejects the upstream -1
        # sentinel, and a bogus positive offset would mislead a later
        # incremental /Prev chain.

    _INFO_KEYS = (
        "CreationDate",
        "ModDate",
        "Producer",
        "Creator",
        "Title",
        "Author",
        "Subject",
        "Keywords",
    )

    def _recover_obj_stream_trailer_items(
        self, offsets: dict[COSObjectKey, int], trailer: COSDictionary
    ) -> None:
        """Recover a /Root (and /Info) packed inside an object stream.

        Mirrors the upstream ``bfSearchForObjStreams`` + second
        ``searchForTrailerItems`` pass in ``BruteForceParser.rebuildTrailer``:
        the catalog of a PDF whose xref stream was lost (truncated /missing
        ``startxref``) lives compressed inside a ``/Type /ObjStm`` object, so
        the plain ``n g obj`` scan never sees it. We parse every recovered
        object stream, register its members as ``COMPRESSED`` xref entries
        (container number + inner index), pin each member into the document
        pool, and then classify the catalog / info candidates exactly as
        :meth:`COSParser.rebuild_trailer` does for plain objects."""
        assert self._cos_parser is not None and self._document is not None
        members = self._cos_parser.bf_search_for_obj_stream_members(offsets)
        if not members:
            return
        catalog_name = COSName.get_pdf_name("Catalog")
        type_name = COSName.get_pdf_name("Type")
        fdf_name = COSName.get_pdf_name("FDF")
        info_names = [COSName.get_pdf_name(k) for k in self._INFO_KEYS]
        root_set = trailer.get_item(COSName.ROOT) is not None
        info_set = trailer.get_item(COSName.get_pdf_name("Info")) is not None
        for key, (container, inner_index, parsed) in members.items():
            # Register the compressed member so its loader resolves later and
            # pin the already-parsed object into the pool.
            self._resolver.set_entry(
                key,
                XrefEntry(
                    type=XrefType.COMPRESSED,
                    offset=container,
                    compressed_index=inner_index,
                ),
            )
            holder = self._document.get_object_from_pool(key)
            holder.set_object(parsed)
            if not isinstance(parsed, COSDictionary):
                continue
            is_catalog = (
                parsed.get_item(type_name) is catalog_name
                or parsed.contains_key(fdf_name)
            )
            if not root_set and is_catalog:
                ref = self._document.get_object_from_pool(key)
                trailer.set_item(COSName.ROOT, ref)
                root_set = True
            elif (
                not info_set
                and not is_catalog
                and any(parsed.get_item(k) is not None for k in info_names)
            ):
                ref = self._document.get_object_from_pool(key)
                trailer.set_item(COSName.get_pdf_name("Info"), ref)
                info_set = True

    def _located_root_needs_relocation(self) -> bool:
        """``True`` when the located trailer's ``/Root`` is an indirect
        *reference* that does not resolve to a catalog dictionary.

        Used to decide whether the cleanly parsed classic table needs a
        brute-force object merge to relocate a catalog the xref dropped /
        mislabelled free. A non-reference ``/Root`` (an integer / name scalar)
        returns ``False`` — there is no object to relocate, so it is left to
        surface as a dangling root (matching upstream's resolve, which finds
        no catalog there either)."""
        trailer = self._resolver.get_trailer()
        if trailer is None:
            return False
        root_item = trailer.get_item(COSName.ROOT)
        if not isinstance(root_item, COSObject):
            return False
        # If the /Root object already has a usable xref entry (an in-use table
        # entry, an uncompressed xref-stream entry, or a compressed object that
        # lives inside an /ObjStm), it is present and WILL resolve once the
        # document is fully populated — most modern PDFs put the catalog in an
        # object stream, and that member is not yet loadable at this early
        # post-chain-walk check. Relocation is only warranted when the /Root
        # key is genuinely absent from the table or carries merely a *free*
        # stub (``compressed_index == -1``, the same predicate the merge uses
        # to decide a key is unusable). Without this guard the relocation merge
        # spuriously fired on every file whose catalog is compressed, pulling
        # the /XRef-stream object (and any other body objects) into the pool.
        root_key = COSObjectKey(
            root_item.get_object_number(), root_item.get_generation_number()
        )
        entry = self._resolver.get_xref_table().get(root_key)
        if entry is not None and entry.compressed_index != -1:
            return False
        try:
            resolved = trailer.get_dictionary_object(COSName.ROOT)
        except PDFParseError:
            return True
        return not isinstance(resolved, COSDictionary)

    def _merge_brute_force_objects(self) -> None:
        """Repair an incompletely parsed classic xref table by merging the
        brute-force object scan into the resolver.

        Fired when :meth:`_parse_traditional_xref_section` broke mid-parse (a
        malformed subsection header / entry row) or when the cleanly parsed
        table left ``/Root`` pointing at an unresolvable reference. Mirrors
        upstream COSParser, which after an "Unexpected XRefTable Entry" break —
        or an inconsistent table — recovers the missing / mislabelled objects
        via ``bfSearchForObjects`` so the body's real ``n g obj`` definitions
        (including a catalog the table dropped or mislabelled free) remain
        reachable. Brute-force offsets are registered in a synthetic resolver
        section for keys the partial table did not carry AND for keys it carried
        only as a *free* stub (those are overridden with the in-use offset so a
        catalog mislabelled ``f`` is relocated); cleanly parsed in-use entries
        keep their parsed offsets and ``/Prev``-chain precedence."""
        assert self._cos_parser is not None
        assert self._document is not None
        offsets = self._cos_parser.bf_search_for_objects()
        if not offsets:
            return
        existing = self._resolver.get_xref_table()
        new_entries: dict[COSObjectKey, int] = {}
        for key, offset in offsets.items():
            entry = existing.get(key)
            # Skip keys the table already carries as a usable in-use entry; a
            # free stub (compressed_index == -1) is overridden with the
            # brute-force in-use offset so a mislabelled-free object recovers.
            if entry is not None and entry.compressed_index != -1:
                continue
            new_entries[key] = offset
        if new_entries:
            # begin_section(-1) keeps the synthetic merge out of visited-offset
            # tracking; the regular populate_document step then attaches lazy
            # loaders for these recovered keys.
            self._resolver.begin_section(-1)
            for key, offset in new_entries.items():
                self._resolver.set_entry(
                    key, XrefEntry(type=XrefType.TABLE, offset=offset)
                )
        # If the trailer's /Root key now dangles (the broken table dropped the
        # catalog entry), repair it from the brute-force scan the same way the
        # missing-/Root path does.
        trailer = self._resolver.get_trailer()
        if trailer is not None:
            root = trailer.get_dictionary_object(COSName.ROOT)
            if not isinstance(root, COSDictionary):
                rebuilt = self._cos_parser.rebuild_trailer()
                rebuilt_root = rebuilt.get_item(COSName.ROOT)
                if rebuilt_root is not None:
                    trailer.set_item(COSName.ROOT, rebuilt_root)

    def _rebuild_trailer_for_missing_root(self) -> None:
        """Brute-force-rebuild the trailer when a cleanly parsed xref's
        trailer is missing its ``/Root`` key.

        Mirrors the upstream ``COSParser.retrieveTrailer`` branch that fires
        when ``trailer.getItem(ROOT) == null`` in lenient mode: the body is
        re-scanned for ``n g obj`` definitions, the first object advertising
        ``/Type /Catalog`` becomes the recovered ``/Root`` (plus ``/Info`` /
        ``/Encrypt`` / ``/ID`` candidates), and the recovered objects are
        merged into the resolver so the relocated catalog — which may not
        have appeared in the original (broken) xref — is reachable.

        Unlike :meth:`_rebuild_document_from_brute_force` this keeps the
        already-parsed xref section (the located xref's entries are valid;
        only the trailer's ``/Root`` was absent), registering brute-force
        offsets only for keys the xref didn't already carry."""
        assert self._cos_parser is not None
        offsets = self._cos_parser.bf_search_for_objects()
        if not offsets:
            # Nothing to recover from — leave the rootless trailer in place
            # so initial_parse surfaces "Missing root", matching upstream's
            # rebuild-then-still-no-root path.
            return
        trailer = self._cos_parser.rebuild_trailer()
        existing = self._resolver.get_xref_table()
        # Register a synthetic section holding any recovered object the
        # located xref did not already map (e.g. the catalog itself when the
        # broken xref omitted it). begin_section(-1) keeps it out of
        # visited-offset tracking.
        self._resolver.begin_section(-1)
        for key, offset in offsets.items():
            if key in existing:
                continue
            self._resolver.set_entry(
                key, XrefEntry(type=XrefType.TABLE, offset=offset)
            )
        self._resolver.set_trailer(trailer)
        self._cos_parser.set_trailer_was_rebuild(True)

    def _resolve_recovered_objects(self) -> None:
        """Dereference every brute-force-recovered object, tolerating
        per-object body defects exactly as upstream does.

        Mirrors the eager resolution upstream
        ``BruteForceParser.searchForTrailerItems`` performs while rebuilding
        the trailer: it loops over every recovered object and calls
        ``cosObject.getObject()`` to classify catalog / info candidates.
        Crucially, upstream ``COSObject.getObject`` *catches* the
        ``IOException`` a broken body throws (``COSObject.java`` line 120:
        ``catch (IOException e) { LOG.error(...); }``) and leaves that one
        object null — it does NOT abort the load. So a stream truncated mid
        body (no ``endstream``), a garbled ``obj`` keyword, or any other
        body-level defect on an object that isn't itself the catalog leaves
        the rest of the document fully loadable.

        Wave 1503 (mutation-fuzz parity): the previous implementation let the
        loader exception propagate, turning every such mutant into a load-time
        failure while PDFBox recovered. We now swallow the per-object
        ``PDFParseError`` / ``OSError`` here, matching upstream's
        ``getObject`` contract. The catalog itself is still validated by
        :meth:`_reject_full_rebuild_without_root` (an unresolvable /Root
        candidate stays absent, so the rootless rejection still fires)."""
        assert self._document is not None
        for cos_obj in self._document.get_objects():
            try:
                cos_obj.get_object()
            except (PDFParseError, OSError):
                # Upstream COSObject.getObject swallows the dereference
                # IOException and leaves this object null; the load continues.
                continue

    def _reject_full_rebuild_without_root(self) -> None:
        """Surface upstream's "Missing root" rejection on the full-rebuild path.

        Mirrors upstream ``PDFParser.initialParse`` (PDFParser.java) which
        ``Loader.loadPDF`` invokes via ``parse(boolean)``: after the trailer is
        retrieved it dereferences ``/Root`` and throws
        ``IOException("Missing root object specification in trailer.")`` when no
        catalog dictionary is reachable. A complete brute-force reconstruction
        that recovered objects but found no ``/Type /Catalog`` candidate has a
        trailer with no ``/Root`` (``COSParser.rebuildTrailer`` leaves the key
        absent), so the document would otherwise load as an empty 0-page shell.
        Only the full (no-locatable-xref) rebuild calls this — the located-xref
        path keeps pypdfbox's lazy /Root resolution contract."""
        trailer = self._resolver.get_trailer()
        root: COSBase | None = None
        if trailer is not None:
            root = trailer.get_dictionary_object(COSName.ROOT)  # type: ignore[attr-defined]
        if not isinstance(root, COSDictionary):
            raise PDFParseError("Missing root object specification in trailer.")

    def _check_pages_after_full_rebuild(self) -> None:
        """Run upstream ``initialParse``'s ``checkPages(root)`` on the rebuilt
        trailer's catalog so dangling / truncated /Kids are pruned and /Count
        is rewritten — matching the recovered page tally PDFBox produces.

        Only the full brute-force rebuild calls this (it mirrors
        ``initialParse`` end-to-end); the located-xref path defers
        ``initial_parse`` and keeps its valid kids untouched. The /Root was
        already validated by :meth:`_reject_full_rebuild_without_root`, so the
        catalog resolves here."""
        if self._cos_parser is None:
            return
        trailer = self._resolver.get_trailer()
        if trailer is None:
            return
        root = trailer.get_dictionary_object(COSName.ROOT)  # type: ignore[attr-defined]
        if not isinstance(root, COSDictionary):
            return
        if self._lenient and not root.contains_key(COSName.TYPE):
            root.set_item(COSName.TYPE, COSName.CATALOG)
        # Mirror upstream ``COSParser.checkPages``: when the trailer was
        # rebuilt it prunes the page tree's dangling / truncated /Kids and
        # rewrites /Count, then ALWAYS asserts ``root.getCOSDictionary(PAGES)
        # != null`` — raising IOException("Page tree root must be a dictionary")
        # otherwise. ``getCOSDictionary`` returns null both when /Pages is
        # absent AND when /Pages resolves to something that is not a
        # dictionary (a dangling reference to a missing object, or a
        # non-dictionary value).
        #
        # pypdfbox honours that rejection ONLY when the catalog actually
        # carries a /Pages key that fails to resolve to a dictionary — a
        # non-FDF catalog whose page tree dangles must fail at load time,
        # matching upstream. A catalog with NO /Pages key at all is left
        # lenient: those are the FDF root dictionaries pypdfbox loads through
        # this generic ``load_pdf`` path (upstream routes FDF through a
        # separate parser that never reaches checkPages). The /Root presence
        # was already validated by ``_reject_full_rebuild_without_root``.
        pages_name = COSName.get_pdf_name("Pages")
        pages = root.get_dictionary_object(pages_name)
        if isinstance(pages, COSDictionary):
            self._cos_parser.check_pages_dictionary(pages, set())
        elif root.contains_key(pages_name):
            # /Pages key present but it does not resolve to a page-tree
            # dictionary (missing target / non-dictionary value) — upstream
            # checkPages throws here.
            raise PDFParseError("Page tree root must be a dictionary")

    def _check_xref_offsets_lenient(self) -> None:
        """Verify every parsed xref offset points at its ``n g obj`` header
        and brute-force-correct the ones that don't.

        Mirrors upstream ``COSParser.checkXrefOffsets``: a single wrong
        subsection offset (corrupt xref entry) must not strand the object —
        the body still contains a valid ``n g obj`` definition that a
        linear scan can relocate. Only invoked in lenient mode. The scan is
        run lazily (only when at least one offset fails its header check) so
        well-formed documents pay nothing."""
        assert self._cos_parser is not None
        assert self._document is not None
        xref = self._resolver.get_xref_table()
        bf_offsets: dict[COSObjectKey, int] | None = None
        corrected: dict[COSObjectKey, int] = {}
        for key, entry in xref.items():
            if entry.type is XrefType.COMPRESSED or entry.compressed_index == -1:
                continue
            if self._object_header_matches(entry.offset, key):
                continue
            # Offset is wrong — locate the object by brute force.
            if bf_offsets is None:
                bf_offsets = self._cos_parser.bf_search_for_objects()
            real_offset = bf_offsets.get(key)
            if real_offset is None or real_offset == entry.offset:
                continue
            entry.offset = real_offset
            corrected[key] = real_offset
        if not corrected:
            return
        # Re-attach loaders for the corrected entries so lazy resolution
        # reads from the relocated offset, and refresh the document's
        # public xref-table view.
        for key, real_offset in corrected.items():
            cos_obj = self._document.get_object_from_pool(key)
            cos_obj.set_loader(
                self._make_loader(
                    XrefEntry(type=XrefType.TABLE, offset=real_offset)
                )
            )
        self._document.add_xref_table(corrected)

    def _object_header_matches(self, offset: int, key: COSObjectKey) -> bool:
        """Return ``True`` when ``offset`` seeks to an ``n g obj`` header
        whose object number matches ``key``. Cursor position is restored.

        Used by :meth:`_check_xref_offsets_lenient` to decide whether an
        xref entry's byte offset is trustworthy before resolving it."""
        if offset < 0 or offset >= self._src.length():
            return False
        saved = self._src.get_position()
        try:
            self._src.seek(offset)
            self._base.skip_whitespace()
            on = self._base.read_int()
            self._base.skip_whitespace()
            self._base.read_int()
            self._base.skip_whitespace()
            return (
                self._base.read_keyword() == b"obj"
                and on == key.object_number
            )
        except PDFParseError:
            return False
        finally:
            self._src.seek(saved)

    def _make_loader(self, entry: XrefEntry):  # type: ignore[no-untyped-def]
        """Build a lazy loader callback for a single xref entry."""
        if entry.type is XrefType.COMPRESSED:
            objstm_obj_num = entry.offset
            inner_index = entry.compressed_index

            def _compressed_loader(obj: COSObject) -> COSBase | None:
                try:
                    return self._load_compressed_object(
                        objstm_obj_num, inner_index, obj
                    )
                except PDFParseError as exc:
                    raise OSError(str(exc)) from exc

            return _compressed_loader

        offset = entry.offset

        def _loader(obj: COSObject) -> COSBase | None:
            try:
                return self._load_indirect_object_at(offset, obj)
            except PDFParseError as exc:
                raise OSError(str(exc)) from exc

        return _loader

    def _load_compressed_object(
        self, objstm_obj_num: int, inner_index: int, obj: COSObject
    ) -> COSBase | None:
        """Resolve an object stored inside an object stream (PDF 32000-1
        §7.5.7). The owning ``ObjStm`` is itself an indirect object whose
        body, after /Filter is applied, is a header of ``/N`` ``(obj_num
        byte_offset)`` pairs followed by ``/N`` packed direct objects
        starting at ``/First``.

        ``inner_index`` is the position of the requested object inside the
        ObjStm — *not* the requested object's own number. ``obj`` is the
        ``COSObject`` placeholder whose ``_resolved`` field the caller
        will populate from our return value."""
        assert self._document is not None
        objstm = self._document.get_object_from_pool(
            COSObjectKey(objstm_obj_num, 0)
        )
        objstm_body = objstm.get_object()
        if not isinstance(objstm_body, COSStream):
            raise PDFParseError(
                f"object stream {objstm_obj_num} is not a stream"
            )
        # Mirror upstream ``COSParser.parseObjectStreamObject`` (Apache PDFBox
        # 3.0.7, COSParser.java:812-833): the whole object-stream parse —
        # the ``PDFObjectStreamParser`` constructor's /N//First validation
        # plus the header-pair decode and member parse — runs inside a single
        # ``try { ... } catch (IOException ex)``. In lenient mode (the default
        # for ``Loader.loadPDF``) the exception is logged and the compressed
        # member resolves to ``null`` rather than failing the whole resolve;
        # only in strict (non-lenient) mode is it rethrown. pypdfbox formerly
        # always propagated, so malformed /N//First//header bytes raised where
        # PDFBox returns null (wave 1516 fuzz divergence — every malformed
        # case below now resolves to None at parity).
        try:
            decoded, pairs, first = _read_object_stream_offsets(
                objstm_body, objstm_obj_num
            )
            # Resolve the member by its STORED OBJECT NUMBER, not by the xref's
            # positional ``inner_index``. Upstream
            # ``PDFObjectStreamParser.parseAllObjects`` (Apache PDFBox 3.0.7)
            # keys every parsed member by ``COSObjectKey(storedObjNum, 0)`` and
            # ``COSParser.parseObjectStreamObject`` then does
            # ``objects.remove(requestedKey)`` — so an inflated /N, a missing
            # trailing pair, or header pairs whose order does not match the
            # xref's recorded stream-index all still resolve correctly (or to
            # null) by NUMBER. pypdfbox previously indexed ``pairs[inner_index]``
            # positionally, which diverged whenever the header order and the
            # xref index disagreed (wave 1516 fuzz: ``n_smaller_member_second``,
            # ``header_offset_unordered``). We mirror the by-number lookup and
            # use ``inner_index`` only to disambiguate genuine DUPLICATE object
            # numbers (the upstream ``getStreamIndex`` tiebreak).
            matches = [
                (pair_index, off)
                for pair_index, (stored_num, off) in enumerate(pairs)
                if stored_num == obj.object_number
            ]
            if not matches:
                # The requested object is not among the header pairs that were
                # actually read — upstream's ``objects.remove(key)`` returns
                # null for the same case.
                return None
            if len(matches) > 1 and 0 <= inner_index < len(pairs):
                # Duplicate object numbers: prefer the occurrence at the xref's
                # recorded stream index when it points at a matching pair.
                stored_at_index = pairs[inner_index][0]
                if stored_at_index == obj.object_number:
                    target_byte_offset = pairs[inner_index][1]
                else:
                    target_byte_offset = matches[0][1]
            else:
                target_byte_offset = matches[0][1]
            # Parse the requested direct object from the decoded payload.
            body_view = RandomAccessReadBuffer(decoded[first + target_byte_offset:])
            body_parser = COSParser(body_view, document=self._document)
            try:
                obj_body = body_parser.parse_direct_object()
                # A compressed object's body is the indirect object itself —
                # reset the direct flag (set by parse_direct_object on inline
                # dicts) so the writer keeps it as a keyed object. Mirrors
                # upstream PDFObjectStreamParser (Java line 102/160:
                # setDirect(false)). Restricted to dict/array — scalar bodies
                # are interned singletons.
                if isinstance(obj_body, (COSDictionary, COSArray)):
                    obj_body.set_direct(False)
                    obj_body.set_key(
                        COSObjectKey(obj.object_number, obj.generation_number)
                    )
                return obj_body
            finally:
                body_view.close()
        except PDFParseError:
            if self._lenient:
                _LOG.error(
                    "object stream %s could not be parsed due to an exception",
                    objstm_obj_num,
                    exc_info=True,
                )
                return None
            raise

    def _load_indirect_object_at(self, offset: int, obj: COSObject) -> COSBase | None:
        """Seek to ``offset`` and parse the indirect-object definition.
        For a stream object, also reads the body."""
        self._src.seek(offset)
        self._base.skip_whitespace()
        # n m obj
        on = self._base.read_int()
        self._base.skip_whitespace()
        gn = self._base.read_int()
        self._base.skip_whitespace()
        kw = self._base.read_keyword()
        if kw != b"obj":
            raise PDFParseError(
                f"expected 'obj' at offset {offset}, got {kw!r}",
                position=self._base.position,
            )
        if on != obj.object_number or gn != obj.generation_number:
            # Upstream COSParser.parseFileObject (COSParser.java line 729-734)
            # throws — unconditionally, in lenient mode too — when the object's
            # own ``n g obj`` header disagrees with the xref key it was reached
            # by ("XREF for N:G points to wrong object"). A definition whose
            # generation was bumped (e.g. ``1 5 obj`` where the xref / /Root
            # references ``1 0 R``) leaves that reference unresolvable; the
            # caller's lazy ``COSObject.get_object`` swallows the error and the
            # object stays null, so a bumped catalog surfaces as "Missing root".
            raise PDFParseError(
                f"XREF for {obj.object_number}:{obj.generation_number} points "
                f"to wrong object: {on}:{gn} at offset {offset}"
            )
        assert self._cos_parser is not None
        body = self._cos_parser.parse_direct_object(
            allow_indirect_reference=False
        )
        # The top-level body of an indirect object is itself the indirect
        # object — it must NOT be flagged direct, otherwise the writer would
        # try to inline it instead of emitting it as a keyed object. Upstream
        # COSParser.parseFileObject resets this (Java line 634:
        # parsedObject.setDirect(false)) after parseDirObject marks inline
        # dicts direct. Mirror that here, but only for COSDictionary / COSArray:
        # those are the only types whose direct flag the writer consults, and
        # scalar bodies (COSInteger / COSBoolean / COSNull / COSName) are
        # interned singletons in this port — touching their flag/key would leak
        # across documents.
        if isinstance(body, (COSDictionary, COSArray)):
            body.set_direct(False)
            body.set_key(COSObjectKey(obj.object_number, obj.generation_number))
        self._base.skip_whitespace()
        # Distinguish 'endobj' from 'stream'.
        peek = self._base.peek_byte()
        if peek == 0x73:  # 's' — possibly 'stream'
            kw2 = self._base.read_keyword()
            if kw2 == b"stream":
                if not isinstance(body, COSDictionary):
                    raise PDFParseError(
                        "stream object body is not a dictionary",
                        position=self._base.position,
                    )
                stream = self._convert_dict_to_stream(body)
                self._read_stream_body(stream)
                # After endstream comes endobj. A producer that omits the
                # closing ``endobj`` (or truncates the file right after the
                # stream body) leaves nothing to read — upstream
                # parseFileObject tolerates a missing trailing keyword in
                # lenient mode, so treat a no-keyword/EOF as an empty closing
                # keyword and let ``_check_endobj`` warn rather than raise.
                self._base.skip_whitespace()
                try:
                    end_kw = self._base.read_keyword()
                except PDFParseError:
                    if not self._lenient:
                        raise
                    end_kw = b""
                self._check_endobj(end_kw, on, gn, offset)
                return stream
            # An 's'-keyword that isn't 'stream' is just a wrong closing
            # keyword — upstream parseFileObject treats any non-'endobj'
            # trailing keyword the same (warn in lenient, raise in strict).
            self._check_endobj(kw2, on, gn, offset)
            return body
        end_kw = self._base.read_string().encode("latin-1")
        self._check_endobj(end_kw, on, gn, offset)
        return body

    def _check_endobj(
        self, end_kw: bytes, obj_nr: int, obj_gen: int, offset: int
    ) -> None:
        """Validate the keyword that closes an indirect object. Mirrors
        upstream ``COSParser.parseFileObject`` (Java lines 682-695): when the
        trailing keyword does not start with ``endobj`` the parser warns and
        carries on in lenient mode (recovered streams whose body contained an
        embedded ``endstream`` token leave the cursor mid-body, so the closing
        keyword is whatever followed the false terminator), and only raises in
        strict mode."""
        if end_kw.startswith(b"endobj"):
            return
        if self._lenient:
            _LOG.warning(
                "Object (%d:%d) at offset %d does not end with 'endobj' "
                "but with %r",
                obj_nr,
                obj_gen,
                offset,
                end_kw,
            )
            return
        raise PDFParseError(
            f"Object ({obj_nr}:{obj_gen}) at offset {offset} does not end "
            f"with 'endobj' but with {end_kw!r}",
            position=self._base.position,
        )

    def _convert_dict_to_stream(self, src: COSDictionary) -> COSStream:
        """Build a fresh ``COSStream`` from a parsed dictionary, copying
        every entry. The original dict is no longer referenced."""
        assert self._document is not None
        stream = COSStream(scratch_file=self._document.scratch_file)
        for k, v in src.entry_set():
            stream.set_item(k, v)
        return stream

    def _read_stream_body(self, stream: COSStream) -> None:
        """Per ISO 32000-1 §7.3.8.1: ``stream`` keyword is followed by EOL
        (CRLF or LF — bare CR is non-conformant). Then exactly /Length
        bytes. Then ``endstream`` (typically preceded by EOL).

        Mirrors upstream ``COSParser.parseCOSStream`` (Java line 904): the
        declared ``/Length`` is only trusted when ``validateStreamLength``
        confirms it actually lands on an ``endstream`` keyword. A present
        but *wrong* ``/Length`` (too short / too long / zero) — common in
        real-world files — is recovered by scanning to the next
        ``endstream`` and the recovered length is written back onto the
        stream dictionary, exactly as upstream does."""
        self._consume_eol_after_stream_keyword()
        # /Length may be an indirect reference whose resolution recurses
        # into ``_load_indirect_object_at`` and moves the shared cursor.
        # Snapshot here, resolve, then re-seek before reading the body.
        body_start = self._src.get_position()
        # Mirror upstream ``COSParser.getLength`` (COSParser.java line 854):
        # ``None`` means the ``/Length`` entry is missing or its indirect
        # target resolved to ``COSNull`` — fall through to the endstream scan.
        # A wrong-typed ``/Length`` (a name, a direct ``null``, an indirect
        # ref whose content was never read) raises ``PDFParseError``, which
        # propagates so the lazy ``COSObject.get_object`` leaves the object
        # null — exactly as upstream ``parseCOSStream`` lets ``getLength``'s
        # ``IOException`` bubble out.
        length = self._resolve_stream_length(stream)
        self._src.seek(body_start)
        if length is None:
            # No usable /Length. In lenient mode (Loader's default) recover by
            # scanning to ``endstream``; in strict mode a stream with no length
            # is a hard error — pypdfbox keeps the fail-fast strict contract.
            if not self._lenient:
                raise PDFParseError("stream missing or malformed /Length")
            self._recover_stream_body(stream, None)
            return
        # In lenient mode, a declared /Length is only trusted when it
        # actually points at an ``endstream`` keyword. A negative length, a
        # length that overruns the file, or one that simply doesn't land on
        # ``endstream`` all fail ``validate_stream_length`` and trigger the
        # endstream scan, rewriting /Length with the recovered value
        # (PDFBOX validateStreamLength workaround).
        if self._lenient and (
            length < 0 or not self._validate_stream_length(body_start, length)
        ):
            # A negative length is never directly read — even when the shared
            # COSParser isn't bound (so ``_validate_stream_length`` can't run)
            # the negative count would blow up ``bytearray(length)``; recover by
            # scanning to ``endstream`` instead.
            self._src.seek(body_start)
            self._recover_stream_body(stream, length)
            return
        body = bytearray(max(0, length))
        n = self._src.read_into(body)
        if n != length:
            raise PDFParseError(
                f"stream body truncated: expected {length} bytes, got {n}",
                position=self._src.get_position(),
            )
        stream.set_raw_data(bytes(body))
        # Trailing EOL is conventional but optional; skip it then verify
        # 'endstream' is next.
        self._base.skip_whitespace()
        kw = self._base.read_keyword()
        if kw != b"endstream":
            raise PDFParseError(
                f"expected 'endstream', got {kw!r}", position=self._base.position
            )

    def _validate_stream_length(self, body_start: int, length: int) -> bool:
        """Return ``True`` when ``length`` bytes from ``body_start`` lands on
        an ``endstream`` keyword. Mirrors upstream
        ``COSParser.validateStreamLength(long)`` — delegates to the shared
        :class:`COSParser` implementation (same underlying source), restoring
        the cursor to ``body_start`` afterwards."""
        if self._cos_parser is None:  # pragma: no cover - parser always bound here
            return True
        self._src.seek(body_start)
        try:
            return self._cos_parser.validate_stream_length(length)
        finally:
            self._src.seek(body_start)

    def _recover_stream_body(self, stream: COSStream, declared: int | None) -> None:
        """Recover a stream body by scanning to the next ``endstream`` and,
        when the recovered length differs from the ``declared`` value (or
        none was declared), write the recovered length back onto the stream
        dictionary. Mirrors the upstream readUntilEndStream fallback in
        ``parseCOSStream``. The source must be positioned at the body start."""
        body = self._read_until_endstream()
        stream.set_raw_data(body)
        if declared is None or declared != len(body):
            stream.set_item(COSName.LENGTH, COSInteger.get(len(body)))

    def _read_until_endstream(self) -> bytes:
        """Lenient stream recovery for a missing or malformed ``/Length``.

        Scans from the current source position for the next ``endstream`` —
        or, when a producer omitted ``endstream`` altogether, the next
        ``endobj`` — and treats the bytes before it as the body. The trailing
        stream line break is stripped via :class:`EndstreamFilterStream`.

        Mirrors upstream ``COSParser.readUntilEndStream`` (COSParser.java
        line 983), which matches either keyword. When the recovery stops on
        ``endstream`` the cursor is left just past it; when it stops on
        ``endobj`` the cursor is left *at* the keyword so the caller's
        end-of-object check consumes it. When neither keyword is present the
        whole remainder of the file is taken as the body (upstream scans to
        EOF).
        """
        start = self._src.get_position()
        remaining = max(0, self._src.length() - start)
        buf = bytearray(remaining)
        n = self._src.read_into(buf)
        data = bytes(buf[:n]) if n != RandomAccessRead.EOF and n > 0 else b""

        endstream_at = data.find(b"endstream")
        endobj_at = data.find(b"endobj")
        if endstream_at < 0 and endobj_at < 0:
            # Neither terminator present — take everything to EOF (upstream
            # readUntilEndStream returns when the source is exhausted).
            marker_at = len(data)
            cursor_after = start + marker_at
        elif endstream_at >= 0 and (endobj_at < 0 or endstream_at <= endobj_at):
            marker_at = endstream_at
            cursor_after = start + marker_at + len(b"endstream")
        else:
            # ``endobj`` reached first (no ``endstream``): stop at it and
            # leave the keyword for the caller's end-of-object check.
            marker_at = endobj_at
            cursor_after = start + marker_at

        body = data[:marker_at]
        filtered = EndstreamFilterStream()
        filtered.filter(body, 0, len(body))
        length = filtered.calculate_length()
        self._src.seek(cursor_after)
        return body[:length]

    def _consume_eol_after_stream_keyword(self) -> None:
        """Per spec: a single CRLF or LF after ``stream``. Tolerate a CR
        immediately followed by something other than LF (PDFBox quirk —
        some producers emit just CR)."""
        b = self._src.read()
        if b == 0x0D:  # CR
            if self._src.peek() == 0x0A:
                self._src.read()  # consume LF too
            return
        if b == 0x0A:  # LF
            return
        # No EOL after 'stream' — extremely non-conformant; rewind so the
        # body read sees the byte.
        if b != RandomAccessRead.EOF:
            self._src.rewind(1)

    def _resolve_stream_length(self, stream: COSStream) -> int | None:
        """Resolve ``/Length`` to an ``int``, or ``None`` when there is no
        usable length (entry missing, or an indirect ref whose target is
        ``COSNull``) and the caller must scan to ``endstream``. Mirrors
        upstream ``COSParser.getLength(COSBase, COSName)`` (COSParser.java
        line 854).

        A wrong-typed ``/Length`` — a direct value that is neither a number
        nor a missing entry (e.g. a name or a direct ``null``), or an
        indirect ref whose content could not be read — raises
        ``PDFParseError`` (upstream ``IOException``). The negative value is
        returned as-is so ``validate_stream_length`` can reject it and the
        caller falls back to the endstream scan, matching upstream where a
        negative ``longValue()`` simply fails ``validateStreamLength``."""
        length_base = stream.get_item(COSName.LENGTH)  # type: ignore[attr-defined]
        if length_base is None:
            return None
        # Indirect reference: resolve through the COSObject loader.
        if isinstance(length_base, COSObject):
            length = length_base.get_object()
            if length is None:
                raise PDFParseError("Length object content was not read.")
            if isinstance(length, COSNull):
                return None
            if isinstance(length, (COSInteger, COSFloat)):
                return int(length.value)
            raise PDFParseError(
                f"Wrong type of referenced length object: {type(length).__name__}"
            )
        # Direct value.
        if isinstance(length_base, (COSInteger, COSFloat)):
            return int(length_base.value)
        raise PDFParseError(
            f"Wrong type of length object: {type(length_base).__name__}"
        )
