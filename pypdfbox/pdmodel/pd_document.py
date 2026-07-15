from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, BinaryIO

from pypdfbox.cos import COSArray, COSDictionary, COSDocument, COSName
from pypdfbox.io import RandomAccessRead, RandomAccessWrite

from .pd_page import PDPage
from .pd_page_tree import PDPageTree

_LOG = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .interactive.digitalsignature.pd_signature import PDSignature
    from .interactive.digitalsignature.signature_interface import SignatureInterface
    from .pd_document_catalog import PDDocumentCatalog
    from .pd_document_information import PDDocumentInformation


_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_CATALOG: COSName = COSName.CATALOG  # type: ignore[attr-defined]
_PAGES: COSName = COSName.PAGES  # type: ignore[attr-defined]
_KIDS: COSName = COSName.KIDS  # type: ignore[attr-defined]
_COUNT: COSName = COSName.COUNT  # type: ignore[attr-defined]
_INFO: COSName = COSName.INFO  # type: ignore[attr-defined]
_ROOT: COSName = COSName.ROOT  # type: ignore[attr-defined]
_ENCRYPT: COSName = COSName.ENCRYPT  # type: ignore[attr-defined]
_RESOURCE_CACHE_UNSET = object()
# PDF 32000-1 §7.6.3 — the /Filter value naming the Standard security handler
# (mirrors ``StandardSecurityHandler.FILTER``; kept as a literal here to avoid a
# module-load circular import and to stay stable under decrypt-path test doubles).
_STANDARD_SECURITY_FILTER = "Standard"


# Source-type alias for ``PDDocument.load`` — same shape as ``Loader.load_pdf``.
PDDocumentSource = (
    str
    | os.PathLike[str]
    | bytes
    | bytearray
    | memoryview
    | BinaryIO
    | RandomAccessRead
)


class PDDocument:
    """
    High-level PDF document handle. Mirrors
    ``org.apache.pdfbox.pdmodel.PDDocument``.

    Provides construction and loading, catalog and information access,
    page-tree mutation, save and incremental-save plumbing, version and
    encryption state, signing staging, resource cache wiring, and document
    lifecycle helpers. Feature-specific work that belongs to sibling
    modules (for example page content, catalog sub-dictionaries, security
    handlers, or writer serialization details) remains delegated to those
    modules.
    """

    #: Default PDF version stamped on the catalog of an empty
    #: :class:`PDDocument`. Mirrors upstream's hard-coded ``"1.4"`` literal in
    #: the no-arg constructor — exposed as a class-level constant so callers
    #: (and tests) can branch on it without re-stating the value.
    DEFAULT_VERSION: float = 1.4

    #: Sentinel ``/ByteRange`` reserved by :meth:`add_signature` until the
    #: real byte offsets are known. Mirrors upstream's package-private
    #: ``RESERVE_BYTE_RANGE = {0, 1000000000, 1000000000, 1000000000}`` —
    #: exposed here so external-signing callers writing their own placeholder
    #: pipelines can re-use the same shape.
    RESERVE_BYTE_RANGE: tuple[int, int, int, int] = (
        0,
        1_000_000_000,
        1_000_000_000,
        1_000_000_000,
    )

    def __init__(
        self,
        source_or_doc: COSDocument | None = None,
        *,
        source: RandomAccessRead | None = None,
    ) -> None:
        if source_or_doc is None:
            self._document = COSDocument()
            self._owns_document = True
            self._build_minimal_skeleton()
            self._prepare_document_for_updates()
        elif isinstance(source_or_doc, COSDocument):
            self._document = source_or_doc
            # Loader-built documents pass ownership of the source via
            # ``COSDocument._source``; we don't double-own it here.
            self._owns_document = True
            self._prepare_document_for_updates()
        else:
            raise TypeError(
                f"PDDocument expected COSDocument or None; got "
                f"{type(source_or_doc).__name__}"
            )
        if source is not None:
            # Late-bound source override (rare — primarily test plumbing).
            self._document._source = source  # noqa: SLF001 — sibling-package handoff

        # Cached high-level wrappers, lazily built.
        self._catalog: PDDocumentCatalog | None = None
        self._pages: PDPageTree | None = None
        # Cached PDDocumentInformation wrapper. Mirrors upstream's
        # ``documentInformation`` field — the same wrapper instance is
        # returned across calls so ``getDocumentInformation()`` stays
        # reference-stable. Replaced when ``set_document_information`` is
        # called and cleared when ``clear_document_information`` is called.
        self._document_information: PDDocumentInformation | None = None

        # Mirror the upstream ``allSecurityToBeRemoved`` flag.
        self._all_security_to_be_removed: bool = False

        # Lazy ``PDEncryption`` wrapper around the trailer's /Encrypt dict;
        # populated on first ``get_encryption()`` call or by ``decrypt()``.
        self._encryption: Any = None
        # Lazy :class:`DefaultResourceCache` — built on first access via
        # ``get_resource_cache``. Shared across every ``PDResources`` lookup
        # in the document so identical indirect refs round-trip the same
        # typed wrapper. A private sentinel represents "not yet allocated"
        # so callers can pass ``None`` to disable caching.
        self._resource_cache: Any = _RESOURCE_CACHE_UNSET
        # Stash for TTF fonts that asked to be closed at document close.
        # We don't manage TTF lifetimes at runtime (Python GC handles it),
        # so this list is effectively a registration log — see
        # ``register_true_type_font_for_closing``.
        self._fonts_to_close: list[Any] = []
        # Set of fonts queued for subsetting prior to the next full save.
        # Mirrors upstream's package-private ``fontsToSubset`` field —
        # populated by ``PDFont`` subclasses when a glyph is referenced and
        # drained by the writer's subset pass. Pypdfbox keeps the surface so
        # callers (and the writer) can inspect / extend the set even before
        # subsetting itself ships. See ``get_fonts_to_subset``.
        self._fonts_to_subset: set[Any] = set()
        # Active security handler after ``decrypt()`` succeeds — used by
        # ``get_current_access_permission`` and by the writer for encrypt
        # passes.
        self._security_handler: Any = None
        # Policy staged by ``protect()`` and consumed by the writer at save.
        self._protection_policy: Any = None

        # Pick up handler / encryption stashed by ``Loader.load_pdf`` when
        # the COSDocument has already been auto-decrypted. This lets a
        # caller-visible PDDocument wrapper (created after the transient
        # decrypt-time wrapper has been discarded) report the correct
        # ``get_current_access_permission`` without re-running the
        # password-derivation pipeline.
        loader_handler = getattr(self._document, "_loader_security_handler", None)
        loader_encryption = getattr(self._document, "_loader_encryption", None)
        if loader_handler is not None:
            self._security_handler = loader_handler
        if loader_encryption is not None:
            self._encryption = loader_encryption

        # Optional ``Long`` seed consumed by COSWriter when deriving the
        # trailer's ``/ID`` array on a full save. ``None`` (the default) lets
        # the writer pick a random / time-based seed; a caller-supplied value
        # makes the resulting /ID deterministic — useful for reproducible
        # builds and round-trip tests. Mirrors upstream's
        # ``PDDocument.setDocumentId(Long)`` transient field.
        self._document_id_seed: int | None = None

        # Cached :class:`AccessPermission` result for
        # :meth:`get_current_access_permission`. Mirrors upstream's
        # ``accessPermission`` field — first call snapshots the permission
        # so subsequent calls return the same instance (some upstream tests
        # rely on reference identity, e.g. when downstream callers stash the
        # permission in a side channel and expect it to keep matching).
        self._access_permission: Any = None

        # Pending signature staged by ``add_signature(...)`` and consumed by
        # the next ``save_incremental`` call. ``_pending_signature_dict`` is
        # the COSDictionary backing the PDSignature (so the writer emits its
        # bytes), ``_pending_signature_interface`` is the SignatureInterface
        # callback that produces the PKCS#7 blob over the bracketed bytes.
        # Cleared after a successful sign cycle.
        self._pending_signature: PDSignature | None = None
        self._pending_signature_interface: SignatureInterface | None = None
        self._pending_signature_options: Any = None
        # Mirrors upstream's ``signatureAdded`` field — set to True the first
        # time ``add_signature`` is called and never reset for the lifetime
        # of the document. A second ``add_signature`` raises so callers
        # follow the "load → add → save → close → reload" cycle prescribed
        # by ISO 32000 §12.8 for sequential signing.
        self._signature_added: bool = False

        self._closed: bool = False

    # ---------- construction helpers ----------

    def _build_minimal_skeleton(self) -> None:
        """Wire up an empty trailer + catalog + pages tree so the document
        is immediately saveable. Mirrors upstream's ``new PDDocument()``
        no-arg constructor."""
        # Trailer with /Root pointing at a Catalog dict.
        trailer = COSDictionary()
        catalog = COSDictionary()
        catalog.set_item(_TYPE, _CATALOG)
        # Mirror upstream's no-arg PDDocument constructor (PDDocument.java
        # lines 180-185) key-for-key AND in upstream's exact insertion order:
        # /Type, then /Version, then /Pages. Stamping /Version BEFORE /Pages
        # (rather than appending it after the pages tree) is what keeps a
        # freshly-built destination catalog byte-identical to PDFBox's when
        # serialized — most visibly in PDFMergerUtility output, whose merged
        # /Catalog otherwise diverged only in this key order. The literal
        # value lives in :attr:`DEFAULT_VERSION` so subclasses / callers can
        # override.
        catalog.set_item(
            COSName.get_pdf_name("Version"),
            COSName.get_pdf_name(f"{self.DEFAULT_VERSION:.1f}"),
        )
        # Pages root.
        pages = COSDictionary()
        pages.set_item(_TYPE, _PAGES)
        pages.set_item(_KIDS, COSArray())
        pages.set_int(_COUNT, 0)
        catalog.set_item(_PAGES, pages)
        trailer.set_item(_ROOT, catalog)
        self._document.set_trailer(trailer)

    def _prepare_document_for_updates(self) -> None:
        """Link existing COS update-info objects to this document lifecycle.

        Parser-created documents already do this while parsing. This pass
        also covers manually assembled ``COSDocument`` instances and the
        no-arg constructor's skeleton without marking the graph dirty.
        """
        state = self._document.get_document_state()
        trailer = self._document.get_trailer()
        if trailer is not None:
            trailer.get_update_state().set_origin_document_state(
                state,
                dereferencing=True,
            )
        for cos_object in self._document.get_objects():
            cos_object.get_update_state().set_origin_document_state(
                state,
                dereferencing=True,
            )
        state.set_parsing(False)

    # ---------- alternate construction ----------

    @classmethod
    def load(
        cls,
        source: PDDocumentSource,
        password: str | bytes | None = None,
    ) -> PDDocument:
        """Convenience classmethod — forwards to ``Loader.load_pdf`` and
        wraps the result in a ``PDDocument``. Matches PRD §7's example
        usage ``with PDDocument.load(path) as doc: …``.

        When ``password`` is supplied the document is auto-decrypted on
        load (mirrors ``PDDocument.load(File, String)`` upstream)."""
        # Local import to avoid a circular import at module load time.
        from pypdfbox.loader import Loader

        cos_doc = (
            Loader.load_pdf(source)
            if password is None
            else Loader.load_pdf(source, password)
        )
        return cls(cos_doc)

    # ---------- COS surface ----------

    def get_document(self) -> COSDocument:
        return self._document

    def get_pdf_source(self) -> RandomAccessRead | None:
        """Return the underlying :class:`RandomAccessRead` the document was
        loaded from, or ``None`` when the document was synthesised in
        memory.

        Mirrors upstream's package-private ``pdfSource`` field — pypdfbox
        promotes it to a public accessor so callers needing to verify
        whether :meth:`save_incremental` will succeed without raising can
        check the source presence directly (cheaper than catching the
        ``ValueError`` raised by the incremental save itself). Equivalent
        to ``self.get_document().get_source()`` but kept on the PDDocument
        surface so callers don't have to drop down to the COS layer."""
        return self._document.get_source()

    def get_document_catalog(self) -> PDDocumentCatalog:
        from .pd_document_catalog import PDDocumentCatalog

        if self._catalog is None:
            self._catalog = PDDocumentCatalog(self)
        return self._catalog

    def set_document_catalog(self, catalog: PDDocumentCatalog) -> None:
        """Replace the document's catalog with ``catalog``. Rewires the
        trailer's ``/Root`` entry to ``catalog.get_cos_object()`` so any
        subsequent save reaches the new catalog. Mirrors upstream
        ``PDDocument.setDocumentCatalog``.

        Note: the previous catalog (and anything reachable only through it)
        becomes orphaned; callers are responsible for not stranding dirty
        objects across a swap during incremental save."""
        if catalog is None:
            raise TypeError("set_document_catalog: catalog must not be None")
        cos = catalog.get_cos_object()
        if not isinstance(cos, COSDictionary):
            raise TypeError(
                f"set_document_catalog: expected a PDDocumentCatalog backed by "
                f"a COSDictionary; got {type(cos).__name__}"
            )
        trailer = self._document.get_trailer()
        if trailer is None:
            trailer = COSDictionary()
            self._document.set_trailer(trailer)
        trailer.set_item(_ROOT, cos)
        self._catalog = catalog
        # Catalog-derived caches (notably the page tree) must rebuild.
        self._pages = None

    def get_document_information(self) -> PDDocumentInformation:
        """Return the trailer's ``/Info`` dictionary wrapped as
        ``PDDocumentInformation``. If absent, an empty wrapper is created
        and wired into the trailer so subsequent setters round-trip
        (matches upstream ``PDDocument.getDocumentInformation``).

        The wrapper is cached after the first call — repeated invocations
        return the same instance, mirroring upstream's
        ``documentInformation`` field. ``set_document_information`` swaps
        the cache to the supplied wrapper."""
        from .pd_document_information import PDDocumentInformation

        if self._document_information is not None:
            return self._document_information
        trailer = self._document.get_trailer()
        if trailer is None:
            trailer = COSDictionary()
            self._document.set_trailer(trailer)
        info = trailer.get_dictionary_object(_INFO)
        if not isinstance(info, COSDictionary):
            info = COSDictionary()
            trailer._set_item_quiet(_INFO, info)
        self._document_information = PDDocumentInformation(info)
        return self._document_information

    def set_document_information(self, info: PDDocumentInformation) -> None:
        """Replace the trailer's ``/Info`` entry. The cached
        :class:`PDDocumentInformation` wrapper is updated so subsequent
        :meth:`get_document_information` calls return ``info`` (mirrors
        upstream's assignment to ``this.documentInformation``)."""
        trailer = self._document.get_trailer()
        if trailer is None:
            trailer = COSDictionary()
            self._document.set_trailer(trailer)
        trailer.set_item(_INFO, info.get_cos_object())
        self._document_information = info

    # ---------- trailer presence / clear helpers ----------

    def has_document_catalog(self) -> bool:
        """Return ``True`` when the trailer has a well-formed ``/Root``
        catalog dictionary.

        This is a read-only probe: unlike :meth:`get_document_catalog`, it
        does not materialise a replacement catalog when the trailer is
        missing or ``/Root`` has a malformed COS value.
        """
        trailer = self._document.get_trailer()
        return trailer is not None and isinstance(
            trailer.get_dictionary_object(_ROOT), COSDictionary
        )

    def has_document_information(self) -> bool:
        """Return ``True`` when the trailer has a well-formed ``/Info``
        dictionary.

        Malformed values read as absent, matching
        :meth:`get_document_information`'s type-check posture without
        replacing the value as that accessor does.
        """
        trailer = self._document.get_trailer()
        return trailer is not None and isinstance(
            trailer.get_dictionary_object(_INFO), COSDictionary
        )

    def has_encryption_dictionary(self) -> bool:
        """Return ``True`` when the trailer has a well-formed ``/Encrypt``
        dictionary.

        This intentionally differs from :meth:`is_encrypted`, which mirrors
        the COS-layer key-presence check. A malformed ``/Encrypt`` entry can
        therefore make ``is_encrypted()`` true while this stricter predicate
        returns false.
        """
        trailer = self._document.get_trailer()
        return trailer is not None and isinstance(
            trailer.get_dictionary_object(_ENCRYPT), COSDictionary
        )

    def clear_document_catalog(self) -> None:
        """Remove trailer ``/Root`` and invalidate catalog-derived caches."""
        trailer = self._document.get_trailer()
        if trailer is not None:
            trailer.remove_item(_ROOT)
        self._catalog = None
        self._pages = None

    def clear_document_information(self) -> None:
        """Remove trailer ``/Info`` and invalidate the cached wrapper."""
        trailer = self._document.get_trailer()
        if trailer is not None:
            trailer.remove_item(_INFO)
        self._document_information = None

    def clear_encryption_dictionary(self) -> None:
        """Remove trailer ``/Encrypt`` and clear the cached wrapper."""
        self.set_encryption_dictionary(None)

    # ---------- pages ----------

    def get_pages(self) -> PDPageTree:
        if self._pages is None:
            self._pages = self.get_document_catalog().get_pages()
        return self._pages

    def get_number_of_pages(self) -> int:
        """Return the total page count. Mirrors upstream
        ``PDDocument.getNumberOfPages()`` literally — delegates to
        :meth:`PDPageTree.get_count` (the cached ``/Pages /Count`` field)
        so the result is O(1) regardless of tree shape, matching the
        upstream's ``getDocumentCatalog().getPages().getCount()`` chain.

        Mirrors upstream by building the page tree *fresh* through the
        catalog rather than reusing the cached :attr:`_pages` wrapper — see
        :meth:`get_page` for why the fresh tree matters."""
        return self.get_document_catalog().get_pages().get_count()

    def get_page(self, index: int) -> PDPage:
        """Return the page at the given 0-based index. Mirrors upstream
        ``PDDocument.getPage(int)`` literally:
        ``getDocumentCatalog().getPages().get(index)``.

        Upstream's ``getPages()`` constructs a NEW ``PDPageTree`` (with a
        fresh recursion-guard ``pageSet``) on every call, so each
        ``getPage`` lookup starts from an empty set. pypdfbox caches the
        page-tree wrapper in :attr:`_pages` for iteration / mutation reuse,
        but that cache also persists the tree's ``_page_set``, which
        ``PDPageTree.__getitem__`` never clears on the out-of-bounds path.
        Reusing the cached tree here therefore leaked node identities
        between successive ``get_page`` calls — a second out-of-range lookup
        spuriously tripped the recursion guard (``RuntimeError``) where
        upstream raises ``IndexError``. Routing through the catalog's fresh
        tree restores upstream-faithful per-lookup isolation while leaving
        the cached wrapper (and its within-a-single-lookup recursion
        semantics) untouched for every other caller."""
        return self.get_document_catalog().get_pages()[index]

    def add_page(self, page: PDPage) -> None:
        self.get_pages().add(page)

    def remove_page(self, page: PDPage | int) -> None:
        """Remove a page either by reference or 0-based index. Mirrors
        upstream's two ``removePage`` overloads."""
        tree = self.get_pages()
        if isinstance(page, int):
            target = tree[page]
            tree.remove(target)
            return
        tree.remove(page)

    # ---------- save ----------

    def save(
        self,
        target: str | os.PathLike[str] | BinaryIO | RandomAccessWrite,
        compress_parameters: Any = None,
    ) -> None:
        """Full save via ``COSWriter``. Accepts a path, a writable binary
        stream, or a ``RandomAccessWrite``. Mirrors the multiple ``save``
        overloads upstream — including the trailing ``CompressParameters``
        argument introduced in PDFBox 3.0.

        ``compress_parameters`` defaults to
        ``CompressParameters.DEFAULT_COMPRESSION`` (upstream parity): the
        output packs non-stream indirect objects into ``/Type /ObjStm``
        object streams addressed by a compressed cross-reference stream.
        Pass ``CompressParameters.NO_COMPRESSION`` for a traditional
        uncompressed xref-table save."""
        if self._closed:
            raise OSError("Cannot save a document which has been closed")
        # Local import — pdfwriter depends on cos and we want the loader-style
        # late binding to keep import-time cycles impossible.
        from pypdfbox.pdfwriter import COSWriter
        from pypdfbox.pdfwriter.compress import CompressParameters

        if compress_parameters is None:
            compress_parameters = CompressParameters.DEFAULT_COMPRESSION
        elif not isinstance(compress_parameters, CompressParameters):
            raise TypeError(
                "compress_parameters must be a CompressParameters instance "
                f"or None, got {type(compress_parameters).__name__}"
            )
        compress = compress_parameters.is_compress()

        # Honour ``set_all_security_to_be_removed``: drop /Encrypt from the
        # trailer (and force any decrypted streams to be re-emitted as
        # plaintext) before handing off to the writer. Mirrors PDFBox's
        # ``saveUnencrypted`` semantics — once decrypted, raw bytes on
        # COSStream already carry the plaintext payload thanks to the
        # in-place rewrite inside ``COSStream.create_input_stream``.
        if self._all_security_to_be_removed and self.is_encrypted():
            trailer = self._document.get_trailer()
            if trailer is not None:
                import contextlib

                # Force a decode pass on every stream so its raw bytes are
                # plaintext before the writer snapshots them.
                from pypdfbox.cos import COSStream as _COSStream

                for cos_obj in self._document.get_objects():
                    actual = cos_obj.get_object()
                    if isinstance(actual, _COSStream) and actual.has_data():
                        with contextlib.suppress(Exception):
                            # If decryption hasn't been wired yet the raw
                            # bytes stay as-is; matches upstream's "best
                            # effort" stripping behaviour.
                            actual.create_input_stream().close()
                trailer.remove_item(_ENCRYPT)

        opened: BinaryIO | None = None
        sink: BinaryIO | RandomAccessWrite
        if isinstance(target, (str, os.PathLike)):
            opened = open(target, "wb")  # noqa: SIM115 — closed in finally
            sink = opened
        else:
            sink = target
        try:
            with COSWriter(
                sink,
                xref_stream=compress,
                object_stream=compress,
                object_stream_size=(
                    compress_parameters.get_object_stream_size()
                    if compress
                    else None
                ),
            ) as writer:
                # Pass the PDDocument so the writer can drive the
                # encryption pipeline — ``_protection_policy`` and
                # ``_security_handler`` live on this wrapper, not on the
                # raw COSDocument. Mirrors upstream
                # ``COSWriter.write(PDDocument)``.
                writer.write(self)
        finally:
            if opened is not None:
                opened.close()

    def save_incremental(
        self,
        target: str | os.PathLike[str] | BinaryIO | RandomAccessWrite,
        objects_to_write: set[COSDictionary] | None = None,
    ) -> None:
        """Append-only save via ``COSWriter(incremental=True)``.

        Requires the document to have been loaded from a parsable source
        — incremental mode preserves the original bytes and appends only
        objects flagged ``needs_to_be_updated``. Synthesised documents
        with no source raise ``ValueError`` (matches upstream).

        ``objects_to_write`` mirrors the upstream
        ``saveIncremental(OutputStream, Set<COSDictionary>)`` overload —
        every dictionary in the set is force-flagged
        ``needs_to_be_updated`` so it appears in the appended xref even
        when no path of dirty objects reaches it. Useful when an editor
        knows it touched a dict whose containing array / parent didn't
        get re-flagged. Only ``COSDictionary`` instances are supported (the
        upstream signature constraint).

        When :meth:`add_signature` has staged a pending signature, the save
        runs the full signing pipeline: writes a placeholder ``/Contents``
        and a ``/ByteRange`` covering everything outside it, calls the
        registered :class:`SignatureInterface` over the bracketed bytes,
        and splices the resulting PKCS#7 DER blob back into ``/Contents``."""
        if self._closed:
            raise OSError("Cannot save a document which has been closed")
        source = self._document.get_source()
        if source is None:
            # Mirrors upstream ``IllegalStateException`` (PDDocument.java
            # line 1089) → ``RuntimeError`` per the project's
            # IllegalStateException→RuntimeError convention. Oracle-confirmed
            # message against PDFBox 3.0.7 (PDDocumentSignStateProbe).
            raise RuntimeError("document was not loaded from a file or a stream")

        # Mirror upstream's second saveIncremental overload: stamp every
        # dict in ``objects_to_write`` as dirty so the writer emits it.
        if objects_to_write is not None:
            for entry in objects_to_write:
                if not isinstance(entry, COSDictionary):
                    raise TypeError(
                        f"save_incremental: objects_to_write must contain only "
                        f"COSDictionary instances, got {type(entry).__name__}"
                    )
                entry.get_update_state().set_origin_document_state(
                    self._document.get_document_state()
                )
                entry.set_needs_to_be_updated(True)

        # Pending-signature path → full sign pipeline.
        if self._pending_signature is not None:
            if self._pending_signature_interface is None:
                raise ValueError(
                    "save_incremental on a signed document requires a "
                    "SignatureInterface — pass one to add_signature() or use "
                    "save_incremental_for_external_signing"
                )
            signed_bytes, contents_span, byte_range = (
                self._render_incremental_with_placeholder()
            )
            interface = self._pending_signature_interface
            # Hash + sign the bracketed bytes via the SignatureInterface.
            import io as _io

            bracketed = self._extract_bracketed(signed_bytes, byte_range)
            pkcs7_der = interface.sign(_io.BytesIO(bracketed))
            final_bytes = self._splice_signature(
                signed_bytes, contents_span, pkcs7_der
            )
            self._write_bytes_to_target(final_bytes, target)
            # Clear staging so a follow-up save_incremental doesn't double-sign.
            self._pending_signature = None
            self._pending_signature_interface = None
            self._pending_signature_options = None
            return

        from pypdfbox.pdfwriter import COSWriter

        opened: BinaryIO | None = None
        sink: BinaryIO | RandomAccessWrite
        if isinstance(target, (str, os.PathLike)):
            opened = open(target, "wb")  # noqa: SIM115
            sink = opened
        else:
            sink = target
        try:
            with COSWriter(sink, incremental=True, incremental_input=source) as writer:
                writer.write(self._document)
        finally:
            if opened is not None:
                opened.close()

    # ---------- signing internals ----------

    # Default hex-character width reserved for the ``/Contents <…>`` slot when
    # the caller passes no ``SignatureOptions`` (or a non-positive preferred
    # size). 18944 hex chars = 0x2500 = 9472 raw bytes, matching upstream
    # ``SignatureOptions.DEFAULT_SIGNATURE_SIZE`` (the COSWriter reserves twice
    # the byte count as hex chars between ``<`` and ``>``). Confirmed against
    # the live oracle (SignByteRangeFuzzProbe): default gap == 0x2500*2+2.
    # Kept as a class constant so existing tests can monkeypatch a narrow slot.
    _CONTENTS_PLACEHOLDER_HEX_LEN: int = 0x2500 * 2
    # Width (decimal digits) reserved for each ByteRange placeholder slot.
    # Wide enough to cover any PDF up to ~10 GiB without re-flowing offsets.
    _BYTERANGE_SLOT_WIDTH: int = 10

    def _contents_placeholder_hex_len(self) -> int:
        """Hex-character width to reserve for the ``/Contents <…>`` slot.

        Honours the pending ``SignatureOptions.get_preferred_signature_size``
        (a *byte* count → twice as many hex chars), falling back to
        ``_CONTENTS_PLACEHOLDER_HEX_LEN`` when no positive preference was set.
        Mirrors upstream PDFBox's COSWriter, which sizes the placeholder from
        ``SignatureOptions`` and otherwise from the default constant —
        confirmed by the live oracle (SignByteRangeFuzzProbe): the gap
        between the two /ByteRange segments equals ``preferred_size*2 + 2``."""
        options = self._pending_signature_options
        if options is not None:
            getter = getattr(options, "get_preferred_signature_size", None)
            if callable(getter):
                preferred = getter()
                if isinstance(preferred, int) and preferred > 0:
                    return preferred * 2
        return self._CONTENTS_PLACEHOLDER_HEX_LEN

    def _render_incremental_with_placeholder(
        self,
    ) -> tuple[bytearray, tuple[int, int], list[int]]:
        """Run the incremental writer with the pending signature carrying a
        ``/Contents <0…0>`` placeholder sized from the pending
        ``SignatureOptions`` preferred size (see
        :meth:`_contents_placeholder_hex_len`) and a ``/ByteRange [0 ☐ ☐ ☐]``
        placeholder. After the bytes are produced, locate the placeholders,
        compute the real ``/ByteRange``, and patch it in place. The
        ``/Contents`` slot is left as zeros for the caller (or
        :meth:`save_incremental`) to splice into."""
        from pypdfbox.cos import COSArray, COSInteger
        from pypdfbox.pdfwriter import COSWriter

        sig = self._pending_signature
        assert sig is not None
        sig_dict = sig.get_cos_object()

        contents_hex_len = self._contents_placeholder_hex_len()

        # Install the /Contents placeholder: a COSString of all-zero bytes
        # whose hex form occupies exactly ``contents_hex_len`` chars.
        placeholder_bytes = b"\x00" * (contents_hex_len // 2)
        sig.set_contents(placeholder_bytes)

        # Install a /ByteRange placeholder using a sentinel made of digits
        # wide enough that the real ByteRange will fit when we splice.
        # ``[0 9999999999 9999999999 9999999999]`` — 4 ints, three of which
        # are ``_BYTERANGE_SLOT_WIDTH`` digits wide.
        sentinel = int("9" * self._BYTERANGE_SLOT_WIDTH)
        br_placeholder = COSArray()
        br_placeholder.add(COSInteger.get(0))
        br_placeholder.add(COSInteger.get(sentinel))
        br_placeholder.add(COSInteger.get(sentinel))
        br_placeholder.add(COSInteger.get(sentinel))
        # Force inline emit so the placeholder lives literally inside the
        # signature dict (we can't splice through an indirect ref).
        br_placeholder.set_direct(True)
        sig_dict.set_item(COSName.get_pdf_name("ByteRange"), br_placeholder)
        sig_dict.set_needs_to_be_updated(True)

        # Drive the writer into a buffer.
        import io as _io

        buf = _io.BytesIO()
        source = self._document.get_source()
        with COSWriter(
            buf,
            incremental=True,
            incremental_input=source,
            allow_signing_placeholders=True,
        ) as writer:
            writer.write(self._document)
        rendered = bytearray(buf.getvalue())

        # Locate the /Contents placeholder. The signature dict is the only
        # one carrying a contiguous run of N hex zeros enclosed in `<…>`,
        # so we can scan for that exact pattern. Search from the END so a
        # source document that already contains a similar literal (e.g. an
        # XMP packet padding) doesn't mislead us — the dirty signature dict
        # is appended after the source bytes, so it's the last hit.
        zero_run = b"<" + b"0" * contents_hex_len + b">"
        idx = rendered.rfind(zero_run)
        if idx < 0:
            raise RuntimeError(
                "signature splice failed: /Contents placeholder not found "
                "in writer output (writer may have collapsed the COSString)"
            )
        # contents_span is the slice [start, end) covering the hex zeros
        # BETWEEN the angle brackets — what we'll overwrite with PKCS#7 hex.
        contents_start = idx + 1  # skip the '<'
        contents_end = contents_start + contents_hex_len

        # ByteRange = [start1, len1, start2, len2] where the two slices
        # bracket the /Contents hex string. Mirror Apache PDFBox's COSWriter
        # (COSWriter.java doWriteSignature): the digest covers the entire file
        # EXCEPT the `<…>` /Contents token *including* its `<` and `>` angle
        # delimiters. Upstream sets
        #   beforeLength = signatureOffset            (= position of `<`)
        #   afterOffset  = signatureOffset + signatureLength (= just past `>`)
        # so range1 ends just BEFORE `<` (the `<` is the first excluded byte)
        # and range2 starts just AFTER `>` (the `>` is the last excluded byte).
        # Confirmed against the live oracle (SignByteRangeConventionProbe):
        # fileBytes[start1+len1] == '<' and fileBytes[start2-1] == '>'.
        contents_open = idx                        # position of `<`
        contents_close = idx + len(zero_run) - 1   # position of `>`
        start1 = 0
        len1 = contents_open                       # exclude `<` (ends before it)
        start2 = contents_close + 1                # exclude `>` (starts after it)
        len2 = len(rendered) - start2
        byte_range = [start1, len1, start2, len2]

        # Splice the real ByteRange into the placeholder. Find the first
        # `/ByteRange` token after the source's original /ByteRange (if any
        # — the source might also have a signed dict with its own range).
        # Strategy: find the literal bytes corresponding to the placeholder
        # array and replace them with a same-width formatted array (we pad
        # with trailing spaces so total width matches).
        sentinel_text = (
            b"[0 "
            + str(sentinel).encode("ascii")
            + b" "
            + str(sentinel).encode("ascii")
            + b" "
            + str(sentinel).encode("ascii")
            + b"]"
        )
        sentinel_idx = rendered.rfind(sentinel_text)
        if sentinel_idx < 0:
            br_pos = rendered.rfind(b"/ByteRange")
            preview = (
                bytes(rendered[br_pos : br_pos + 200]) if br_pos >= 0 else b"<none>"
            )
            raise RuntimeError(
                "signature splice failed: /ByteRange placeholder not found "
                f"in writer output. /ByteRange context: {preview!r}"
            )
        new_br = (
            b"[0 "
            + str(len1).encode("ascii")
            + b" "
            + str(start2).encode("ascii")
            + b" "
            + str(len2).encode("ascii")
            + b"]"
        )
        if len(new_br) > len(sentinel_text):
            raise RuntimeError(
                f"signature splice failed: real /ByteRange ({len(new_br)} bytes) "
                f"exceeds placeholder width ({len(sentinel_text)} bytes)"
            )
        # Pad with trailing spaces inside the brackets so widths match exactly.
        # Insert spaces just before the closing bracket.
        padding_needed = len(sentinel_text) - len(new_br)
        padded_br = new_br[:-1] + b" " * padding_needed + b"]"
        rendered[sentinel_idx : sentinel_idx + len(sentinel_text)] = padded_br

        return rendered, (contents_start, contents_end), byte_range

    @staticmethod
    def _extract_bracketed(buffer: bytes | bytearray, byte_range: list[int]) -> bytes:
        """Return ``buffer[start1:start1+len1] + buffer[start2:start2+len2]``."""
        start1, len1, start2, len2 = byte_range
        return bytes(buffer[start1 : start1 + len1]) + bytes(
            buffer[start2 : start2 + len2]
        )

    @staticmethod
    def _splice_signature(
        buffer: bytearray, contents_span: tuple[int, int], pkcs7_der: bytes
    ) -> bytes:
        """Hex-encode ``pkcs7_der`` and patch it into ``buffer`` at
        ``contents_span``. Pads with trailing zeros to fill the placeholder.

        Raises ``ValueError`` when the PKCS#7 blob is too large for the
        reserved /Contents slot — caller may bump
        :attr:`_CONTENTS_PLACEHOLDER_HEX_LEN`."""
        contents_start, contents_end = contents_span
        slot_len = contents_end - contents_start
        hex_blob = pkcs7_der.hex().upper().encode("ascii")
        if len(hex_blob) > slot_len:
            raise ValueError(
                f"PKCS#7 signature ({len(hex_blob)} hex chars) larger than "
                f"reserved /Contents placeholder ({slot_len} hex chars). "
                f"Increase PDDocument._CONTENTS_PLACEHOLDER_HEX_LEN."
            )
        padded = hex_blob + b"0" * (slot_len - len(hex_blob))
        out = bytearray(buffer)
        out[contents_start:contents_end] = padded
        return bytes(out)

    @staticmethod
    def _write_bytes_to_target(
        data: bytes,
        target: str | os.PathLike[str] | BinaryIO | RandomAccessWrite,
    ) -> None:
        """Drain ``data`` into ``target`` honouring the same target-shape
        contract as :meth:`save_incremental`."""
        if isinstance(target, (str, os.PathLike)):
            with open(target, "wb") as fh:
                fh.write(data)
            return
        if isinstance(target, RandomAccessWrite):
            target.write_bytes(data)
            return
        target.write(data)

    # ---------- version ----------

    def get_version(self) -> float:
        """Highest version reported by either the header or the catalog
        (PDF 1.4+ allows the catalog to override the header).

        Mirrors upstream literally: catalog ``/Version`` is consulted *only*
        when the header is already at 1.4 or above (PDF < 1.4 does not
        permit a catalog version override per ISO 32000-1 §7.5.2). A
        malformed catalog version string is logged and skipped, matching
        upstream's ``NumberFormatException`` swallow."""
        header_version = self._document.get_version()
        if header_version < 1.4:
            return header_version
        try:
            catalog_str = self.get_document_catalog().get_version()
        except Exception:  # noqa: BLE001 — catalog may be absent on raw docs
            catalog_str = None
        if catalog_str is not None:
            try:
                catalog_version = float(catalog_str)
                return max(header_version, catalog_version)
            except ValueError:
                _LOG.error(
                    "Can't extract the version number of the document catalog."
                )
        return header_version

    def set_version(self, version: float) -> None:
        """Set the PDF version. Upstream forbids downgrades; we mirror.

        For PDF >= 1.4 documents the bump lives in the catalog only —
        the header stays at the original version (matches upstream
        ``PDDocument.setVersion``).

        Equal-version calls are a no-op (matches upstream's ``Float.compare``
        early exit) so we don't gratuitously stamp a catalog version on a
        pre-1.4 document that already reports the requested float."""
        current = self.get_version()
        if version == current:
            return
        if version < current:
            return
        if self._document.get_version() >= 1.4:
            self.get_document_catalog().set_version(f"{version:.1f}")
        else:
            self._document.set_version(version)

    # ---------- encryption ----------

    def is_encrypted(self) -> bool:
        return self._document.is_encrypted()

    def is_all_security_to_be_removed(self) -> bool:
        return self._all_security_to_be_removed

    def set_all_security_to_be_removed(self, value: bool) -> None:
        self._all_security_to_be_removed = bool(value)

    def get_encryption(self) -> Any:
        """Return the document's :class:`PDEncryption` wrapper around the
        trailer's ``/Encrypt`` dictionary, or ``None`` when the document
        is not encrypted. Cached after first call. Mirrors upstream
        ``PDDocument.getEncryption``."""
        from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption

        if self._encryption is not None:
            return self._encryption
        enc_dict = self._document.get_encryption_dictionary()
        if enc_dict is None:
            return None
        self._encryption = PDEncryption(enc_dict)
        return self._encryption

    def set_encryption_dictionary(self, encryption: Any) -> None:
        """Replace the trailer's ``/Encrypt`` entry. Accepts a
        :class:`PDEncryption` (preferred) or a raw ``COSDictionary``.

        Passing ``None`` clears the cached :class:`PDEncryption` wrapper
        and removes ``/Encrypt`` from the trailer so the next save emits
        an unencrypted document — mirrors upstream
        ``PDDocument.setEncryptionDictionary(null)`` (which simply nulls
        the cached field; pypdfbox additionally drops the trailer entry
        because we keep the trailer authoritative)."""
        from pypdfbox.cos import COSDictionary as _COSDictionary

        if encryption is None:
            self._encryption = None
            trailer = self._document.get_trailer()
            if trailer is not None:
                trailer.remove_item(_ENCRYPT)
            return

        if isinstance(encryption, _COSDictionary):
            enc_dict = encryption
            self._encryption = None
        else:
            # Duck-type: PDEncryption.get_cos_object()
            enc_dict = encryption.get_cos_object()
            self._encryption = encryption
        trailer = self._document.get_trailer()
        if trailer is None:
            trailer = _COSDictionary()
            self._document.set_trailer(trailer)
        trailer.set_item(_ENCRYPT, enc_dict)

    def set_encryption(self, encryption: Any) -> None:
        """Alias for :meth:`set_encryption_dictionary`. Mirrors upstream
        ``PDDocument.setEncryptionDictionary`` (PDFBox 3.0 retains both
        spellings as overloads on ``PDEncryption`` and ``COSDictionary``)."""
        self.set_encryption_dictionary(encryption)

    # ---------- document id seed ----------

    def get_document_id(self) -> int | None:
        """Return the caller-supplied seed for the trailer's ``/ID`` array,
        or ``None`` when no seed has been staged. Mirrors upstream
        ``PDDocument.getDocumentId(): Long``.

        This is *not* the trailer's actual ``/ID`` value — read that via
        ``get_document().get_document_id()`` (returns the
        ``COSArray`` of two byte strings). The seed is consumed by
        :class:`COSWriter` at full-save time to produce a deterministic
        ``/ID`` when set."""
        return self._document_id_seed

    def set_document_id(self, doc_id: int | None) -> None:
        """Stage a deterministic seed for the trailer's ``/ID`` derivation.
        Pass ``None`` to clear and let the writer fall back to a random
        seed. Mirrors upstream ``PDDocument.setDocumentId(Long)``."""
        if doc_id is not None and not isinstance(doc_id, int):
            raise TypeError(
                f"set_document_id: expected int or None, got {type(doc_id).__name__}"
            )
        self._document_id_seed = doc_id

    def decrypt(self, password: str | bytes = "") -> None:
        """Validate ``password`` against the document's ``/Encrypt``
        dictionary and attach the resulting security handler to every
        ``COSStream`` in the object pool so subsequent reads decrypt
        on-the-fly. Mirrors upstream's load-time decryption pipeline.

        Raises :class:`InvalidPasswordException` when the password is
        rejected (or when no password was supplied for an owner/user
        password-protected document). Quietly returns when the document
        is not encrypted."""
        from pypdfbox.cos import COSStream as _COSStream
        from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
        from pypdfbox.pdmodel.encryption.standard_security_handler import (
            StandardDecryptionMaterial,
            StandardSecurityHandler,
        )

        if not self.is_encrypted():
            return

        enc_dict = self._document.get_encryption_dictionary()
        if enc_dict is None:
            return
        encryption = PDEncryption(enc_dict)

        # /Filter dispatch (PDF 32000-1 §7.6.1): the encryption dictionary's
        # /Filter names the security handler. This password-based decrypt path
        # only satisfies the Standard security handler — a missing, unknown, or
        # public-key (/Adobe.PubSec) /Filter selects no password handler, so we
        # raise the same ``IOException`` PDFBox does ("No security handler for
        # filter <name>", matched verbatim by Apache Tika TIKA-4082) rather than
        # silently treating a non-Standard /Filter as Standard and mis-decrypting.
        # The standard /Filter value is the PDF-spec constant "Standard"
        # (``StandardSecurityHandler.FILTER``); compare on the name so the check
        # is independent of the handler-class binding instantiated below.
        filter_name = encryption.get_filter()
        if filter_name != _STANDARD_SECURITY_FILTER:
            raise OSError(f"No security handler for filter {filter_name}")

        # Pull the file ID's first element — the standard handler keys off
        # of it during file-encryption-key derivation. May be absent on
        # ancient documents; the handler tolerates ``b""``.
        document_id: bytes = b""
        ids = self._document.get_document_id()
        if ids is not None and ids.size() >= 1:
            from pypdfbox.cos import COSString as _COSString

            first = ids.get(0)
            if isinstance(first, _COSString):
                document_id = first.get_bytes()

        # Hand the raw str straight to the decryption material so its
        # revision-aware ``get_password_bytes`` can apply the correct charset
        # *and* the SaslPrep canonicalisation r6 mandates (PDF 32000-2
        # §7.6.4.3.4). Eagerly UTF-8-encoding here would bypass SaslPrep and
        # the r2-r4 Latin-1 path, so a password with a compatibility character
        # (e.g. the ``ﬀ`` ligature) hashed differently from PDFBox. ``bytes``
        # callers pass already-encoded material through untouched.
        password_material: str | bytes = (
            password if isinstance(password, str) else bytes(password)
        )

        handler = StandardSecurityHandler(encryption)
        handler.prepare_for_decryption(
            encryption,
            document_id,
            StandardDecryptionMaterial(password_material),
        )

        # Walk every loaded indirect in two passes.
        #
        # Pass 1: attach the handler to each ``COSStream`` so that
        # ``create_input_stream`` decrypts before the filter chain. This
        # also covers xref-stream objects (PDF 1.5+ encrypted xref
        # streams, /Type /XRef): they live in the same pool and inherit
        # from ``COSStream``, so the same hook deciphers their body when
        # the parser cluster reads it back. We *also* pre-seed the
        # handler's ``_objects_seen`` set with every stream's identity so
        # pass 2's dictionary walk doesn't re-enter the stream body via
        # the ``COSDictionary`` recursion (a stream IS a dictionary, but
        # we want to keep its raw bytes deferred to the lazy hook).
        from pypdfbox.cos import COSArray as _COSArray  # noqa: PLC0415
        from pypdfbox.cos import COSDictionary as _COSDictionary  # noqa: PLC0415
        from pypdfbox.cos import COSObjectKey as _COSObjectKey  # noqa: PLC0415
        from pypdfbox.cos import COSString as _COSString  # noqa: PLC0415

        # Object-stream membership guard (PDF 32000-1 §7.6.2): strings and
        # streams stored *inside* a /Type /ObjStm container are never
        # individually encrypted — only the ObjStm container itself is, and
        # decrypting the container yields the contained objects already in
        # cleartext. The parser records membership in the COSDocument's xref
        # table as a NEGATIVE offset (``-objstm_object_number`` per the
        # PDFBox convention). We collect those member keys up front so both
        # decryption passes can skip them; applying a per-object cipher to a
        # member would double-decrypt it into garbage (observed as
        # ``FlateDecode: invalid block type`` when its container's body was
        # subsequently read). Mirrors upstream
        # ``COSParser#parseObjectDynamically`` (Java line 677), which only
        # decrypts objects loaded from a direct file offset and leaves
        # ObjStm-resident objects untouched.
        objstm_member_keys: set[_COSObjectKey] = {
            key
            for key, offset in self._document.get_xref_table().items()
            if offset is not None and offset < 0
        }

        # Pre-seed the handler's already-decrypted set with every stream
        # identity so pass 2's dict walk doesn't re-enter the stream body
        # via the ``COSDictionary`` recursion (a stream IS a dictionary,
        # but its body decrypt is owned by the lazy ``set_security_handler``
        # hook attached below). When the handler is a stub that doesn't
        # expose ``_objects_seen`` (test doubles in
        # ``test_pd_document_wave576``), the dict walk is skipped — those
        # tests assert only on ``prepare_for_decryption`` invocation, so
        # no functional surface is lost.
        seen_ids = None
        objects_seen = getattr(handler, "_objects_seen", None)
        if callable(objects_seen):
            seen_ids = objects_seen()

        def _object_key(cos_obj: Any) -> _COSObjectKey:
            return _COSObjectKey(
                cos_obj.get_object_number(), cos_obj.get_generation_number()
            )

        # Pass 1 must attach handlers to every ObjStm *container* before any
        # ObjStm *member* is materialised. Forcing a member's parse
        # (``get_object()``) lazily reads its container's body through
        # ``create_input_stream`` — if the container has no handler yet, that
        # read decodes ciphertext as plaintext and the filter chain blows up.
        # Members carry a negative xref offset, so iterate them last (and
        # never attach a handler to them — they're plaintext after the
        # container decrypts). Non-member streams (containers, xref streams,
        # content streams written at a direct offset) are handled first.
        for cos_obj in self._document.get_objects():
            if _object_key(cos_obj) in objstm_member_keys:
                continue
            # ``get_object()`` only triggers a parse for stream-bearing
            # entries; their body is encrypted so we materialise to attach
            # the lazy decrypt hook.
            actual = cos_obj.get_object()
            if isinstance(actual, _COSStream):
                actual.set_security_handler(
                    handler,
                    cos_obj.get_object_number(),
                    cos_obj.get_generation_number(),
                )
                if seen_ids is not None:
                    seen_ids.add(id(actual))

        # Now safe to materialise members — every container has a handler —
        # but members are NOT individually encrypted, so we only mark them as
        # already-seen (so pass 2 skips their body) without attaching a
        # per-object cipher.
        for cos_obj in self._document.get_objects():
            if _object_key(cos_obj) not in objstm_member_keys:
                continue
            actual = cos_obj.get_object()
            if isinstance(actual, _COSStream) and seen_ids is not None:
                seen_ids.add(id(actual))

        # Pass 2: PDFBOX-4453 — decrypt every COSString/COSArray slot
        # reachable from each indirect dictionary, using the indirect's
        # ``(obj_num, gen_num)`` as the per-object key seed. Upstream's
        # ``COSParser#parseObjectDynamically`` does this inline (line 677
        # of ``COSParser.java``) by calling ``securityHandler.decrypt``
        # on every non-stream parsed object. pypdfbox parses without an
        # active handler and recovers it here once the trailer's
        # ``/Encrypt`` entry has yielded the file-encryption key.
        decrypt_dict = getattr(handler, "_decrypt_dictionary", None)
        decrypt_dispatch = getattr(handler, "decrypt", None)
        if callable(decrypt_dict) and callable(decrypt_dispatch):
            encrypt_dict = self._document.get_encryption_dictionary()
            for cos_obj in self._document.get_objects():
                # ObjStm members are plaintext once their container has been
                # decrypted (see the membership guard above) — never run a
                # per-object string/array decrypt over them.
                if _object_key(cos_obj) in objstm_member_keys:
                    continue
                actual = cos_obj.get_object()
                # The /Encrypt dictionary itself was never encrypted —
                # its contents (e.g. /U, /O, /OE, /UE byte strings) are
                # key material, not ciphertext. Skip it.
                if actual is encrypt_dict:
                    continue
                if isinstance(actual, _COSStream):
                    # Body is lazy; the stream's *dictionary* entries
                    # may still contain encrypted strings (rare but
                    # legal, e.g. an Outline-level /Title pulled into a
                    # stream dict). ``_decrypt_dictionary`` iterates
                    # entries and recurses; the pre-seeded ``seen_ids``
                    # guards against re-entering nested streams.
                    decrypt_dict(
                        actual,
                        cos_obj.get_object_number(),
                        cos_obj.get_generation_number(),
                    )
                elif isinstance(actual, (_COSDictionary, _COSArray, _COSString)):
                    decrypt_dispatch(
                        actual,
                        cos_obj.get_object_number(),
                        cos_obj.get_generation_number(),
                    )

        self._security_handler = handler
        self._encryption = encryption
        # A successful decrypt may upgrade the document's permission set —
        # invalidate the cached AccessPermission so the next call re-derives.
        self._access_permission = None

    def protect(self, protection_policy: Any) -> None:
        """Stage an encryption policy on the document — actual key
        derivation and ``/Encrypt`` synthesis happen at save time via the
        writer. Mirrors upstream ``PDDocument.protect``.

        If :meth:`set_all_security_to_be_removed` was previously called with
        ``True``, that flag is force-cleared with a warning — ``protect``
        implies ``setAllSecurityToBeRemoved(false)`` (matches upstream's
        guard, which warns and resets the flag rather than failing the
        call)."""
        from pypdfbox.pdmodel.encryption.public_key_protection_policy import (
            PublicKeyProtectionPolicy,
        )
        from pypdfbox.pdmodel.encryption.standard_protection_policy import (
            StandardProtectionPolicy,
        )

        if not isinstance(
            protection_policy, (StandardProtectionPolicy, PublicKeyProtectionPolicy)
        ):
            # Only the two PDFBox-native policy shapes are supported here —
            # anything else is a caller bug rather than a deferred surface.
            raise TypeError(
                "PDDocument.protect requires a StandardProtectionPolicy or "
                f"PublicKeyProtectionPolicy, got {type(protection_policy).__name__}"
            )

        if self._all_security_to_be_removed:
            _LOG.warning(
                "do not call set_all_security_to_be_removed(True) before "
                "calling protect(), as protect() implies "
                "set_all_security_to_be_removed(False)"
            )
            self._all_security_to_be_removed = False

        self._protection_policy = protection_policy

    def get_current_access_permission(self) -> Any:
        """Return the :class:`AccessPermission` derived from the most
        recent successful :meth:`decrypt` call (owner-level when no
        decryption occurred but the document is unencrypted). When the
        document is encrypted but not yet decrypted, returns a
        no-permission default.

        The result is cached after the first call and reused on subsequent
        calls — mirrors upstream's ``accessPermission`` field, so callers
        can rely on reference identity across reads."""
        from pypdfbox.pdmodel.encryption.access_permission import AccessPermission

        if self._access_permission is not None:
            return self._access_permission

        if self._security_handler is not None:
            current = getattr(
                self._security_handler, "get_current_access_permission", None
            )
            if callable(current):
                self._access_permission = current()
                return self._access_permission
        if not self.is_encrypted():
            self._access_permission = AccessPermission.get_owner_access_permission()
            return self._access_permission
        # Encrypted but not yet decrypted — return a no-permission default.
        # Don't cache: a follow-up decrypt() should be able to upgrade.
        return AccessPermission(0)

    def add_signature(
        self,
        sig: PDSignature,
        signature_interface: SignatureInterface | None = None,
        options: Any = None,
        *,
        seed_value: Any = None,
        enforce_seed_value: bool = False,
    ) -> None:
        """Stage ``sig`` for inclusion in the next :meth:`save_incremental`
        and bind ``signature_interface`` as the PKCS#7 producer. Mirrors
        upstream ``PDDocument.addSignature(PDSignature, SignatureInterface,
        SignatureOptions)``.

        The signature dictionary is wired into the document's /AcroForm
        (creating one if necessary) inside an invisible signature field
        named ``Signature1`` (or the next free ``SignatureN``) so it has a
        stable indirect reference. /SigFlags |= 3 (SignaturesExist +
        AppendOnly) per ISO 32000-1 §12.7.3.

        ``signature_interface`` may be ``None`` only when the caller intends
        to drive the signing externally via
        :meth:`save_incremental_for_external_signing`.

        ``seed_value`` (optional) is a :class:`PDSeedValue` describing the
        ``/SV`` constraints the producer must respect. When
        ``enforce_seed_value`` is also ``True`` the candidate ``sig`` is
        validated against the seed value's flagged ``/Ff`` constraints
        before staging — a violation raises :class:`ValueError`. Upstream
        Apache PDFBox keeps this enforcement on the front-end / UI; the
        ``enforce_seed_value=True`` opt-in lets pypdfbox callers offload
        the check to the engine. (Wave 1380.)
        """
        from .interactive.digitalsignature.pd_seed_value import PDSeedValue
        from .interactive.digitalsignature.pd_signature import PDSignature

        if not isinstance(sig, PDSignature):
            raise TypeError(
                f"add_signature expected a PDSignature, got {type(sig).__name__}"
            )

        # /SV enforcement (opt-in). Validate BEFORE we mutate any AcroForm
        # state so a violation leaves the document unchanged.
        if enforce_seed_value:
            if seed_value is None:
                raise ValueError(
                    "enforce_seed_value=True requires a seed_value= PDSeedValue"
                )
            if not isinstance(seed_value, PDSeedValue):
                raise TypeError(
                    f"seed_value must be a PDSeedValue, got "
                    f"{type(seed_value).__name__}"
                )
            # Defaults from the engine — /Filter + /SubFilter get filled
            # later in this method, but validation must see them now.
            if sig.get_filter() is None:
                sig.set_filter("Adobe.PPKLite")
            if sig.get_sub_filter() is None:
                sig.set_sub_filter("adbe.pkcs7.detached")
            seed_value.validate_signature(sig)

        if self._signature_added:
            # Mirrors upstream ``IllegalStateException`` (PDDocument.java
            # line 316) → ``RuntimeError`` per the project's
            # IllegalStateException→RuntimeError convention.
            raise RuntimeError("Only one signature may be added in a document")

        sig_dict = sig.get_cos_object()

        # Default /Filter + /SubFilter when caller didn't set them — matches
        # PDFBox's default ``Adobe.PPKLite`` + ``adbe.pkcs7.detached`` choice.
        if sig.get_filter() is None:
            sig.set_filter("Adobe.PPKLite")
        if sig.get_sub_filter() is None:
            sig.set_sub_filter("adbe.pkcs7.detached")

        # Refuse to sign a page-less document. Mirrors upstream
        # ``IllegalStateException`` (PDDocument.java line 345) → ``RuntimeError``
        # per the project's IllegalStateException→RuntimeError convention.
        # Oracle-confirmed message against PDFBox 3.0.7
        # (PDDocumentSignStateProbe).
        if self.get_pages().get_count() == 0:
            raise RuntimeError("Cannot sign an empty document")

        # Wire the signature dict into /AcroForm /Fields so the writer reaches
        # it from the catalog. We attach via an invisible signature field
        # widget containing the sig dict in /V.
        catalog = self.get_document_catalog()
        from .interactive.form import PDAcroForm

        acro_form = catalog.get_acro_form()
        if acro_form is None:
            acro_form = PDAcroForm(self)
            catalog.set_acro_form(acro_form)
        acro_form_dict = acro_form.get_cos_object()

        # Build an invisible signature field. /T = "Signature{N}" where N is
        # the smallest unused number among existing /Sig fields. The widget
        # carries an empty /Rect (invisible) and the sig dict in /V.
        existing_field_names: set[str] = set()
        fields_arr = acro_form_dict.get_dictionary_object(COSName.get_pdf_name("Fields"))
        if isinstance(fields_arr, COSArray):
            for entry in fields_arr:
                resolved = entry.get_object() if hasattr(entry, "get_object") else entry
                if isinstance(resolved, COSDictionary):
                    nm = resolved.get_string(COSName.get_pdf_name("T"))
                    if nm:
                        existing_field_names.add(nm)
        else:
            fields_arr = COSArray()
            acro_form_dict.set_item(COSName.get_pdf_name("Fields"), fields_arr)

        n = 1
        while f"Signature{n}" in existing_field_names:
            n += 1
        field_name = f"Signature{n}"

        sig_field = COSDictionary()
        sig_field.set_item(COSName.get_pdf_name("FT"), COSName.get_pdf_name("Sig"))
        sig_field.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
        sig_field.set_item(
            COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget")
        )
        sig_field.set_string(COSName.get_pdf_name("T"), field_name)
        sig_field.set_int(COSName.get_pdf_name("F"), 132)  # Print + Locked
        # Invisible widget — zero-area rectangle.
        rect = COSArray()
        for v in (0, 0, 0, 0):
            from pypdfbox.cos import COSInteger as _COSInteger

            rect.add(_COSInteger.get(v))
        sig_field.set_item(COSName.get_pdf_name("Rect"), rect)
        # /V points at the signature value dict. Direct embed keeps the
        # writer pipeline simple: walking the field reaches the sig dict.
        sig_field.set_item(COSName.get_pdf_name("V"), sig_dict)
        # Anchor the widget to the first page so the field is reachable from
        # the page tree as well (mirrors what PDFBox does internally).
        try:
            first_page = self.get_pages()[0].get_cos_object()
        except (IndexError, KeyError):
            first_page = None
        if first_page is not None:
            sig_field.set_item(COSName.get_pdf_name("P"), first_page)
            page_annots = first_page.get_dictionary_object(
                COSName.get_pdf_name("Annots")
            )
            if not isinstance(page_annots, COSArray):
                page_annots = COSArray()
                first_page.set_item(COSName.get_pdf_name("Annots"), page_annots)
            page_annots.add(sig_field)
            # First page now needs a fresh xref entry in incremental mode.
            first_page.set_needs_to_be_updated(True)

        fields_arr.add(sig_field)

        # /SigFlags = SignaturesExist (1) | AppendOnly (2) per §12.7.3.
        acro_form.set_signatures_exist(True)
        acro_form.set_appendonly(True)

        # Mark the touched dicts dirty so incremental save emits them.
        sig_dict.set_needs_to_be_updated(True)
        sig_field.set_needs_to_be_updated(True)
        acro_form_dict.set_needs_to_be_updated(True)
        catalog.get_cos_object().set_needs_to_be_updated(True)
        if isinstance(fields_arr, COSArray):  # pragma: no branch — see lines 1228/1236
            fields_arr.set_needs_to_be_updated(True)

        # Register so the next save_incremental knows to splice.
        self._pending_signature = sig
        self._pending_signature_interface = signature_interface
        self._pending_signature_options = options
        self._signature_added = True

    # ---------- private signing helpers (1:1 with upstream PDDocument) ----------

    @staticmethod
    def find_signature_field(
        field_iterator: Any, sig_object: PDSignature
    ) -> Any | None:
        """Search ``field_iterator`` (an iterable of :class:`PDField`) for the
        :class:`PDSignatureField` whose ``/V`` is the COS object backing
        ``sig_object``. Returns the matching field, or ``None`` if none is
        present. Mirrors upstream private
        ``PDDocument.findSignatureField`` (PDDocument.java:476-493)."""
        from .interactive.form.pd_signature_field import PDSignatureField

        target = sig_object.get_cos_object()
        for pd_field in field_iterator:
            if isinstance(pd_field, PDSignatureField):
                signature = pd_field.get_signature()
                if signature is not None and signature.get_cos_object() == target:
                    return pd_field
        return None

    @staticmethod
    def check_signature_field(field_iterator: Any, signature_field: Any) -> bool:
        """Return ``True`` when ``signature_field`` already appears in
        ``field_iterator`` (membership keyed off the underlying COS dict).
        Mirrors upstream private
        ``PDDocument.checkSignatureField`` (PDDocument.java:502-514)."""
        from .interactive.form.pd_signature_field import PDSignatureField

        target = signature_field.get_cos_object()
        for field in field_iterator:
            if isinstance(field, PDSignatureField) and field.get_cos_object() == target:
                return True
        return False

    @staticmethod
    def check_signature_annotation(annotations: Any, widget: Any) -> bool:
        """Return ``True`` when ``widget`` (a ``PDAnnotationWidget``) is
        already present in ``annotations`` (membership keyed off the
        underlying COS dict). Mirrors upstream private
        ``PDDocument.checkSignatureAnnotation`` (PDDocument.java:523-533)."""
        target = widget.get_cos_object()
        for annotation in annotations:
            cos = (
                annotation.get_cos_object()
                if hasattr(annotation, "get_cos_object")
                else annotation
            )
            if cos == target:
                return True
        return False

    def prepare_non_visible_signature(self, first_widget: Any) -> None:
        """Wire an invisible signature widget — zero-area /Rect plus an
        empty appearance stream — so the signature dictionary is
        well-formed even when the field is not meant to be rendered.
        Mirrors upstream private
        ``PDDocument.prepareNonVisibleSignature`` (PDDocument.java:535-548)."""
        from pypdfbox.cos import COSInteger, COSStream
        from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
            PDAppearanceDictionary,
        )
        from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
            PDAppearanceStream,
        )

        # Zero-area /Rect [0 0 0 0] — invisible per ISO 32000-1 §12.7.4.5.
        rect = COSArray()
        for v in (0, 0, 0, 0):
            rect.add(COSInteger.get(v))
        first_widget.get_cos_object().set_item(COSName.get_pdf_name("Rect"), rect)

        # Empty but well-formed /AP /N appearance. Pypdfbox's
        # PDAppearanceStream wraps a COSStream directly (upstream takes a
        # PDDocument and synthesises one) — we build a minimal empty stream.
        empty_stream = COSStream()
        empty_bbox = COSArray()
        for v in (0, 0, 0, 0):
            empty_bbox.add(COSInteger.get(v))
        empty_stream.set_item(COSName.get_pdf_name("BBox"), empty_bbox)
        empty_stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
        empty_stream.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form"))
        appearance_dict = PDAppearanceDictionary()
        appearance_dict.set_normal_appearance(PDAppearanceStream(empty_stream))
        first_widget.set_appearance(appearance_dict)

    def prepare_visible_signature(
        self, first_widget: Any, acro_form: Any, visual_signature: COSDocument
    ) -> None:
        """Lift the visual-signature template out of ``visual_signature``
        and wire the widget's /Rect, /AP, and the AcroForm /DR resources
        from it. Mirrors upstream private
        ``PDDocument.prepareVisibleSignature`` (PDDocument.java:550-591).

        Raises :class:`ValueError` (≈ Java ``IllegalArgumentException``)
        when the template lacks either a signature annotation or a
        signature field."""
        annot_found = False
        sig_field_found = False

        _ANNOT = COSName.get_pdf_name("Annot")
        _SIG = COSName.get_pdf_name("Sig")
        _AP = COSName.get_pdf_name("AP")
        _FT = COSName.get_pdf_name("FT")

        for cos_object in visual_signature.get_objects():
            base = cos_object.get_object()
            if not isinstance(base, COSDictionary):
                continue
            # Search for signature annotation.
            if not annot_found and base.get_cos_name(_TYPE) == _ANNOT:
                self.assign_signature_rectangle(first_widget, base)
                annot_found = True
            # Search for signature field.
            ap_dict = base.get_dictionary_object(_AP)
            if (
                isinstance(ap_dict, COSDictionary)
                and not sig_field_found
                and base.get_cos_name(_FT) == _SIG
            ):
                self.assign_appearance_dictionary(first_widget, ap_dict)
                self.assign_acro_form_default_resource(acro_form, base)
                sig_field_found = True
            if annot_found and sig_field_found:
                break
        if not annot_found or not sig_field_found:
            raise ValueError("Template is missing required objects")

    @staticmethod
    def assign_signature_rectangle(first_widget: Any, annot_dict: COSDictionary) -> None:
        """Copy ``annot_dict``'s ``/Rect`` onto ``first_widget`` unless the
        widget already carries a 4-element rectangle (preserves caller-
        supplied geometry on existing fields). Mirrors upstream private
        ``PDDocument.assignSignatureRectangle`` (PDDocument.java:593-605)."""
        from pypdfbox.pdmodel.pd_rectangle import PDRectangle

        existing = first_widget.get_rectangle()
        if existing is None or existing.get_cos_array().size() != 4:
            rect_array = annot_dict.get_dictionary_object(COSName.get_pdf_name("Rect"))
            if isinstance(rect_array, COSArray):
                first_widget.set_rectangle(PDRectangle.from_cos_array(rect_array))

    @staticmethod
    def assign_appearance_dictionary(first_widget: Any, ap_dict: COSDictionary) -> None:
        """Wrap ``ap_dict`` as a :class:`PDAppearanceDictionary`, force it
        direct so it round-trips inside the widget, and attach it to
        ``first_widget``. Mirrors upstream private
        ``PDDocument.assignAppearanceDictionary`` (PDDocument.java:607-613)."""
        from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
            PDAppearanceDictionary,
        )

        ap = PDAppearanceDictionary(ap_dict)
        ap_dict.set_direct(True)
        first_widget.set_appearance(ap)

    @staticmethod
    def assign_acro_form_default_resource(
        acro_form: Any, new_dict: COSDictionary
    ) -> None:
        """Merge the template's ``/DR`` (default resources) into the
        AcroForm's, preferring an outright install when the AcroForm has no
        existing default-resources dict. Mirrors upstream private
        ``PDDocument.assignAcroFormDefaultResource`` (PDDocument.java:615-640)."""
        _DR = COSName.get_pdf_name("DR")
        _XOBJECT = COSName.get_pdf_name("XObject")

        new_dr = new_dict.get_dictionary_object(_DR)
        if not isinstance(new_dr, COSDictionary):
            return
        default_resources = acro_form.get_default_resources()
        if default_resources is None:
            acro_form.get_cos_object().set_item(_DR, new_dr)
            new_dr.set_direct(True)
            new_dr.set_needs_to_be_updated(True)
            return
        old_dr = default_resources.get_cos_object()
        new_xobject = new_dr.get_dictionary_object(_XOBJECT)
        old_xobject = old_dr.get_dictionary_object(_XOBJECT)
        if isinstance(new_xobject, COSDictionary) and isinstance(
            old_xobject, COSDictionary
        ):
            old_xobject.add_all(new_xobject)
            old_dr.set_needs_to_be_updated(True)

    def subset_designated_fonts(self) -> None:
        """Drain the document's ``fontsToSubset`` set, calling ``subset()``
        on each registered font, and clear the set. Mirrors upstream private
        ``PDDocument.subsetDesignatedFonts`` (PDDocument.java:1040-1048).

        Pypdfbox keeps the API public for symmetry with the rest of the
        port; the writer cluster invokes it from :meth:`save` /
        :meth:`save_incremental` once font subsetting lands."""
        for font in list(self._fonts_to_subset):
            subset = getattr(font, "subset", None)
            if callable(subset):
                subset()
        self._fonts_to_subset.clear()

    def get_pending_signature(self) -> PDSignature | None:
        """Return the :class:`PDSignature` staged by the most recent
        :meth:`add_signature` call, or ``None`` when no signature is
        pending. Cleared by :meth:`save_incremental` (or
        :meth:`ExternalSigningSupport.set_signature`) once signing
        completes.

        Pypdfbox-specific accessor — upstream stores the staged signature
        on the field's ``/V`` and re-discovers it via
        :meth:`save_incremental_for_external_signing`'s field-tree walk.
        Exposing it as a typed read-only accessor lets callers introspect
        the staged dict (e.g. to log signing-time choices, or to confirm
        the right :class:`SignatureInterface` was wired) without having
        to walk the ``/AcroForm`` themselves."""
        return self._pending_signature

    def has_pending_signature(self) -> bool:
        """Predicate — ``True`` when :meth:`add_signature` has staged a
        signature that has not yet been finalised by
        :meth:`save_incremental` or
        :meth:`ExternalSigningSupport.set_signature`. Convenience wrapper
        around :meth:`get_pending_signature` that spares callers the
        ``is None`` comparison."""
        return self._pending_signature is not None

    def get_signature_interface(self) -> SignatureInterface | None:
        """Return the :class:`SignatureInterface` callback registered by
        the most recent :meth:`add_signature` call, or ``None`` when none
        was supplied (external-signing path) or no signature is pending.
        Mirrors upstream's package-private ``signInterface`` field."""
        return self._pending_signature_interface

    def get_signature_options(self) -> Any:
        """Return the signature-options object staged by the most recent
        :meth:`add_signature` call, or ``None`` when none was supplied or
        no signature is pending. Mirrors upstream's per-call
        ``SignatureOptions`` parameter — pypdfbox stores it for callers
        that want to introspect the staged state before a save runs."""
        return self._pending_signature_options

    def is_signature_added(self) -> bool:
        """Predicate — ``True`` when :meth:`add_signature` has been called
        on this document at least once. Mirrors upstream's package-private
        ``signatureAdded`` field, which guards the "only one signature per
        document" rule (a second :meth:`add_signature` call raises).

        Stays ``True`` for the lifetime of the document even after
        :meth:`save_incremental` consumes the staging — callers must
        follow the ISO 32000 §12.8 "load → add → save → close → reload"
        cycle to add another signature. Pypdfbox-specific accessor
        (upstream keeps the flag private and only exposes its effect via
        the ``IllegalStateException`` raised on the second call); helps
        callers branch on whether re-loading is required without forcing a
        sacrificial :meth:`add_signature` call."""
        return self._signature_added

    def import_page(self, page: PDPage) -> PDPage:
        """Deep-copy ``page`` into this document and return the new
        :class:`PDPage`.

        The page's dictionary, ``/Resources``, ``/Contents`` stream(s), and
        inheritable attributes are copied. Widget-annotation ``/Parent``
        chains are walked to their top-most field root and that root is
        promoted into this document's ``/AcroForm /Fields`` (name
        collisions are resolved with a per-document ``dummyFieldName``
        counter mirroring :class:`PDFMergerUtility` legacy mode), so
        AcroForm widgets imported from another document remain navigable
        from the destination's form. Cross-document ``/Names`` tree
        merging, ``/Dest`` resolution, and font / image resource
        deduplication are deferred — see ``CHANGES.md``."""
        src_dict = page.get_cos_object()
        # Copy key-by-key, skipping /Parent BEFORE the deep copy — the
        # parent chain reaches the source page tree and therefore every
        # page in the source document, so copy-then-strip deep-copied the
        # whole document per imported page (O(n^2) across a full
        # ``Splitter.split``). Seeding ``seen`` with the page dict itself
        # preserves the old cycle behaviour: a subtree reference back to
        # the page resolves to the shared original, exactly as it did when
        # ``_deep_copy_cos`` visited ``src_dict`` first.
        parent_key = COSName.get_pdf_name("Parent")
        seen: set[int] = {id(src_dict)}
        new_dict = COSDictionary()
        for key in list(src_dict.key_set()):
            if key == parent_key:
                continue
            new_dict.set_item(
                key, self._deep_copy_cos(src_dict.get_item(key), seen)
            )
        new_page = PDPage(new_dict)
        self._import_page_acroform_fixup(new_dict)
        self.get_pages().add(new_page)
        return new_page

    def _import_page_acroform_fixup(self, page_dict: Any) -> None:
        """For an imported page, walk its ``/Annots`` and promote any
        widget-annot ``/Parent`` chain to a top-level field root under
        this document's ``/AcroForm /Fields``.

        Collision handling mirrors :class:`PDFMergerUtility`'s legacy
        mode: if a field with the same ``/T`` is already present in the
        destination's top-level field set, the imported field's ``/T``
        is rewritten with a per-document monotonic suffix
        (``dummyFieldName`` + counter) so callers can still resolve
        every field by name without losing the import.
        """
        from pypdfbox.cos import COSArray, COSDictionary

        annots_name = COSName.get_pdf_name("Annots")
        annots = page_dict.get_dictionary_object(annots_name)
        if not isinstance(annots, COSArray):
            return
        # Collect top-level field roots reached via /Parent walking.
        roots: list[COSDictionary] = []
        seen: set[int] = set()
        for i in range(annots.size()):
            annot = annots.get_object(i)
            if not isinstance(annot, COSDictionary):
                continue
            subtype = annot.get_name(COSName.get_pdf_name("Subtype"))
            # Only widget annots participate in /AcroForm. Other
            # annot kinds use /Parent for structure-tree linking — those
            # references are inside the cloned subgraph and stay valid.
            if subtype != "Widget":
                continue
            parent = annot.get_dictionary_object(
                COSName.get_pdf_name("Parent")
            )
            root = parent if isinstance(parent, COSDictionary) else annot
            # Climb to the topmost /Parent.
            while True:
                up = root.get_dictionary_object(
                    COSName.get_pdf_name("Parent")
                )
                if not isinstance(up, COSDictionary):
                    break
                root = up
            if id(root) in seen:
                continue
            seen.add(id(root))
            roots.append(root)
        if not roots:
            return

        from .interactive.form import PDAcroForm

        catalog = self.get_document_catalog()
        # Read the AcroForm *without* applying the default fixup
        # (``get_acro_form(None)`` mirrors upstream's ``getAcroForm(null)``).
        # This widget-field re-attachment helper is a pypdfbox-only
        # convenience during ``import_page``; seeding Adobe /DA + /DR
        # defaults here would mutate a form the caller never asked to fix
        # up (upstream's ``importPage`` does not touch /AcroForm at all).
        acro_form = catalog.get_acro_form(None)
        if acro_form is None:
            acro_form = PDAcroForm(self)
            catalog.set_acro_form(acro_form)
        form_dict = acro_form.get_cos_object()
        fields_array = form_dict.get_dictionary_object(
            COSName.get_pdf_name("Fields")
        )
        if not isinstance(fields_array, COSArray):
            fields_array = COSArray()
            form_dict.set_item(COSName.get_pdf_name("Fields"), fields_array)
        if not hasattr(self, "_import_field_counter"):
            self._import_field_counter = 1
        # Incremental state persisted on the destination document so a long
        # import_page loop doesn't rescan the whole /Fields array on every
        # page (the naive rebuild-per-page was O(n^2) — 6.6s for 3200 pages).
        #   _import_field_names     — set[str] of known /T field names
        #   _import_field_root_ids  — set[int] of id() of appended field roots
        #   _import_fields_array_id — id() of the tracked /Fields COSArray
        #   _import_fields_count    — entries tracked in that array
        # The cache is rebuilt from scratch only when the /Fields array
        # identity changed (a swap) or its size no longer matches the tracked
        # count (an external mutation) — otherwise it is trusted verbatim.
        needs_rebuild = (
            not hasattr(self, "_import_fields_array_id")
            or self._import_fields_array_id != id(fields_array)
            or self._import_fields_count != fields_array.size()
        )
        if needs_rebuild:
            existing_names: set[str] = set()
            root_ids: set[int] = set()
            for i in range(fields_array.size()):
                entry = fields_array.get_object(i)
                root_ids.add(id(entry))
                if isinstance(entry, COSDictionary):
                    t = entry.get_string(COSName.get_pdf_name("T"))
                    if t is not None:
                        existing_names.add(t)
            self._import_field_names = existing_names
            self._import_field_root_ids = root_ids
            self._import_fields_array_id = id(fields_array)
            self._import_fields_count = fields_array.size()
        existing_names = self._import_field_names
        root_ids = self._import_field_root_ids
        prefix = "dummyFieldName"
        for root in roots:
            if id(root) in root_ids:
                continue
            t = root.get_string(COSName.get_pdf_name("T"))
            if t is not None and t in existing_names:
                root.set_string(
                    COSName.get_pdf_name("T"),
                    f"{prefix}{self._import_field_counter}",
                )
                self._import_field_counter += 1
            elif t is not None:
                existing_names.add(t)
            fields_array.add(root)
            root_ids.add(id(root))
            self._import_fields_count += 1

    def _deep_copy_cos(self, value: Any, seen: set[int]) -> Any:
        """Recursive deep copy of a ``COSBase`` tree. Cycles are broken via
        an ``id()``-keyed seen set — when revisited, the original instance
        is shared (rare in well-formed PDFs but possible via /Parent loops
        or self-referential resource trees)."""
        from pypdfbox.cos import COSArray, COSDictionary, COSObject, COSStream

        if id(value) in seen:
            return value
        if isinstance(value, COSObject):
            # Resolve indirect ref, then deep-copy the resolved value.
            return self._deep_copy_cos(value.get_object(), seen)
        if isinstance(value, COSStream):
            seen.add(id(value))
            new_stream = COSStream()
            for key in list(value.key_set()):
                new_stream.set_item(
                    key, self._deep_copy_cos(value.get_item(key), seen)
                )
            # Copy raw (still-encoded) stream bytes verbatim — /Filter chain
            # and /Length come along via the dict copy above.
            if value.has_data():
                new_stream.set_raw_data(value.get_raw_data())
            return new_stream
        if isinstance(value, COSDictionary):
            seen.add(id(value))
            new_dict = COSDictionary()
            for key in list(value.key_set()):
                new_dict.set_item(
                    key, self._deep_copy_cos(value.get_item(key), seen)
                )
            return new_dict
        if isinstance(value, COSArray):
            seen.add(id(value))
            new_arr = COSArray()
            for item in value:
                new_arr.add(self._deep_copy_cos(item, seen))
            return new_arr
        # Scalars (COSInteger, COSFloat, COSName, COSString, COSBoolean,
        # COSNull) are immutable in practice — share the original instance.
        return value

    def get_resource_cache(self) -> Any:
        """Return the document's :class:`PDResourceCache`, lazily allocating
        a :class:`DefaultResourceCache` on first access. Mirrors upstream
        ``PDDocument.getResourceCache``."""
        if self._resource_cache is _RESOURCE_CACHE_UNSET:
            from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache

            self._resource_cache = DefaultResourceCache()
        return self._resource_cache

    def set_resource_cache(self, cache: Any) -> None:
        """Install a custom :class:`PDResourceCache` (or ``None`` to disable
        caching). Subsequent ``get_resource_cache`` calls return whatever
        was passed in — no lazy re-allocation when ``None``."""
        self._resource_cache = cache

    def get_signature_fields(self) -> list[Any]:
        """Return every ``/FT /Sig`` field reachable from the catalog's
        ``/AcroForm`` (depth-first across the field tree). Empty list when
        there is no AcroForm or no signature fields. Mirrors upstream
        ``PDDocument.getSignatureFields``."""
        from .interactive.form.pd_signature_field import PDSignatureField

        catalog = self.get_document_catalog()
        acro_form = catalog.get_acro_form()
        if acro_form is None:
            return []
        return [
            field
            for field in acro_form.get_field_tree()
            if isinstance(field, PDSignatureField)
        ]

    def get_signature_dictionaries(self) -> list[PDSignature]:
        """Return the :class:`PDSignature` value of every signature field in
        the document (skipping fields whose ``/V`` is unset). Mirrors
        upstream ``PDDocument.getSignatureDictionaries``."""
        out: list[PDSignature] = []
        for sig_field in self.get_signature_fields():
            sig = sig_field.get_signature()
            if sig is not None:
                out.append(sig)
        return out

    def has_signatures(self) -> bool:
        """Return ``True`` when at least one signed signature dictionary is
        present in the document's ``/AcroForm`` field tree.

        Convenience predicate — equivalent to
        ``bool(doc.get_signature_dictionaries())`` but spares callers from
        building the intermediate list when they only need the boolean.
        Pypdfbox-specific addition (no upstream equivalent on
        ``PDDocument`` itself; upstream callers reach for
        ``getSignatureDictionaries().size() > 0``)."""
        for sig_field in self.get_signature_fields():
            if sig_field.get_signature() is not None:
                return True
        return False

    def get_last_signature_dictionary(self) -> PDSignature | None:
        """Return the most recently added signature in the document's
        ``/AcroForm`` field tree, or ``None`` when no signed signature
        field is present. Mirrors upstream
        ``PDDocument.getLastSignatureDictionary``."""
        sigs = self.get_signature_dictionaries()
        if sigs:
            return sigs[-1]
        return None

    def requires_full_save(self) -> bool:
        """Return ``True`` when the document has unsaved changes that cannot
        be appended via :meth:`save_incremental` and instead require a full
        :meth:`save`. Convenience predicate — at present we report ``True``
        only when there is no parsable source to append to (synthesised
        documents) or when there are no objects flagged
        ``needs_to_be_updated`` to drive an incremental pass."""
        if self._document.get_source() is None:
            return True
        for cos_obj in self._document.get_objects():
            if cos_obj.is_needs_to_be_updated():
                return False
            inner = cos_obj.get_object()
            if inner is not None and inner.is_needs_to_be_updated():
                return False
        return True

    def is_locked_by_outline_destinations(self) -> bool:
        """Return ``True`` when the document's outline tree pins the
        document into append-only mode (e.g. signed-and-locked outline
        destinations). Placeholder — returns ``False`` until outline-lock
        detection lands."""
        return False

    def register_true_type_font_for_closing(self, font: Any) -> None:
        """Register ``font`` to be closed when the document closes. Lite
        stub — Python GC handles TTF lifetimes for us, so this method just
        appends to an internal list without driving any teardown. Provided
        to keep the upstream API surface complete; full lifecycle
        management lands when font subsetting does (see ``CHANGES.md``)."""
        self._fonts_to_close.append(font)

    def get_fonts_to_close(self) -> list[Any]:
        """Return the live list of fonts registered for close-on-document-
        close via :meth:`register_true_type_font_for_closing`. Mirrors
        upstream's package-private ``fontsToClose`` field — exposed here as
        a public typed accessor for symmetry with :meth:`get_fonts_to_subset`,
        so callers (notably tests verifying registration semantics) can
        introspect the staged set without dropping into private state.

        The returned list is the document's own backing store; mutate it in
        place to deregister a font before close. Pypdfbox uses a list rather
        than a set because Python ``TrueTypeFont`` wrappers aren't
        guaranteed hashable across implementations."""
        return self._fonts_to_close

    def get_fonts_to_subset(self) -> set[Any]:
        """Return the live set of fonts queued for subsetting on the next
        full save. Mirrors upstream's package-private
        ``PDDocument.getFontsToSubset()`` — the returned set is the
        document's own backing store, so callers may add / remove fonts in
        place. Empty by default; subset-aware ``PDFont`` subclasses
        populate it as glyphs are referenced. The writer drains and clears
        it during a full save (subset pass)."""
        return self._fonts_to_subset

    def save_incremental_for_external_signing(
        self, output: BinaryIO
    ) -> ExternalSigningSupport:
        """Drive an externally-supplied signer (HSM, smartcard, remote PKCS#11
        broker, ...) by emitting the signed-but-uncovered bytes and handing
        the caller an :class:`ExternalSigningSupport` shim.

        Workflow::

            with open("out.pdf", "wb") as fh:
                handle = doc.save_incremental_for_external_signing(fh)
                pkcs7_blob = my_external_signer(handle.get_content())
                handle.set_signature(pkcs7_blob)

        Internally identical to :meth:`save_incremental` minus the actual
        ``signature_interface.sign`` call — the caller signs the bracketed
        bytes and then triggers the splice via
        :meth:`ExternalSigningSupport.set_signature`.
        """
        if self._closed:
            raise OSError("Cannot save a document which has been closed")
        # Upstream order (PDDocument.java line 1174 then 1190): the source
        # check fires before the signature-field check. Both are
        # ``IllegalStateException`` → ``RuntimeError`` per the project's
        # convention. Oracle-confirmed messages against PDFBox 3.0.7
        # (PDDocumentSignStateProbe): a created (no-source) document raises the
        # source message even when it carries no signature.
        if self._document.get_source() is None:
            raise RuntimeError("document was not loaded from a file or a stream")
        if self._pending_signature is None:
            raise RuntimeError("document does not contain signature fields")
        signed_bytes, contents_span, byte_range = (
            self._render_incremental_with_placeholder()
        )
        return ExternalSigningSupport(
            document=self,
            output=output,
            buffer=signed_bytes,
            contents_span=contents_span,
            byte_range=byte_range,
        )

    # ---------- top-level convenience helpers (pypdfbox additions) ----------
    #
    # These three helpers are NOT in upstream PDFBox. They are Python-friendly
    # shortcuts that delegate to the multipdf cluster (Splitter / PageExtractor
    # / PDFMergerUtility) so users can stay on the PDDocument surface for
    # common page-level operations:
    #
    #     parts = doc.split(every=1)
    #     section = doc.extract_pages(2, 4)
    #     merged = PDDocument.merge(doc_a, doc_b, doc_c)
    #
    # The delegates are imported lazily — Splitter / PDFMergerUtility may not
    # be available in every wave; an ImportError is surfaced with a pointer to
    # the canonical class so callers can fall back to the upstream-shaped API.
    # Recorded in CHANGES.md as a pypdfbox-specific addition.

    def split(self, every: int = 1) -> list[PDDocument]:
        """Split the document into a list of new :class:`PDDocument` instances.
        Delegates to :class:`pypdfbox.multipdf.splitter.Splitter`.

        ``every`` is the number of pages per output document (mirrors
        upstream ``Splitter.setSplitAtPage``); the default of 1 emits one
        document per page.

        Pypdfbox-only convenience — no upstream equivalent on
        ``PDDocument`` itself."""
        if self._closed:
            raise OSError("PDDocument has been closed")
        try:
            from pypdfbox.multipdf.splitter import Splitter
        except ImportError as exc:  # pragma: no cover — wave-ordering guard
            raise ImportError(
                "PDDocument.split requires pypdfbox.multipdf.splitter.Splitter, "
                "which is not yet available in this build. Use the upstream-"
                "shaped API (Splitter().split(doc)) once the splitter cluster "
                "lands."
            ) from exc

        splitter = Splitter()
        splitter.set_split_at_page(every)
        return splitter.split(self)

    def extract_pages(self, start: int, end: int) -> PDDocument:
        """Return a new :class:`PDDocument` containing pages ``[start..end]``
        (1-based, inclusive). Delegates to
        :class:`pypdfbox.multipdf.page_extractor.PageExtractor`.

        Pypdfbox-only convenience — no upstream equivalent on
        ``PDDocument`` itself."""
        if self._closed:
            raise OSError("PDDocument has been closed")
        from pypdfbox.multipdf.page_extractor import PageExtractor

        return PageExtractor(self, start, end).extract()

    @classmethod
    def merge(cls, *docs: PDDocument) -> PDDocument:
        """Merge ``docs`` left-to-right into a single new :class:`PDDocument`.
        Delegates to
        :class:`pypdfbox.multipdf.pdf_merger_utility.PDFMergerUtility`.

        Pypdfbox-only convenience — no upstream equivalent on
        ``PDDocument`` itself. Returns an empty document when called with no
        arguments."""
        if not docs:
            return cls()
        try:
            from pypdfbox.multipdf.pdf_merger_utility import PDFMergerUtility
        except ImportError as exc:  # pragma: no cover — wave-ordering guard
            raise ImportError(
                "PDDocument.merge requires "
                "pypdfbox.multipdf.pdf_merger_utility.PDFMergerUtility, "
                "which is not yet available in this build. Use the upstream-"
                "shaped API (PDFMergerUtility().merge_documents(...)) once "
                "the merger cluster lands."
            ) from exc

        merger = PDFMergerUtility()
        result = cls()
        for d in docs:
            merger.append_document(result, d)
        return result

    # ---------- lifecycle ----------

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_document:
            self._document.close()

    def is_closed(self) -> bool:
        return self._closed

    def __enter__(self) -> PDDocument:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def __repr__(self) -> str:
        try:
            n = self.get_number_of_pages() if not self._closed else "?"
        except Exception:  # noqa: BLE001
            n = "?"
        return (
            f"PDDocument(pages={n}, version={self._document.get_version()}, "
            f"encrypted={self.is_encrypted()})"
        )


class ExternalSigningSupport:
    """Handle returned by :meth:`PDDocument.save_incremental_for_external_signing`.

    Mirrors PDFBox's ``ExternalSigningSupport`` interface: hands the caller
    the bytes to hash + sign, then patches the resulting PKCS#7 blob into
    ``/Contents`` and drains the final document to the user-supplied
    ``output``.

    Typical usage::

        with open("out.pdf", "wb") as fh:
            handle = doc.save_incremental_for_external_signing(fh)
            blob = remote_hsm.sign(handle.get_content())
            handle.set_signature(blob)
    """

    def __init__(
        self,
        *,
        document: PDDocument,
        output: BinaryIO,
        buffer: bytearray,
        contents_span: tuple[int, int],
        byte_range: list[int],
    ) -> None:
        self._document = document
        self._output = output
        self._buffer = buffer
        self._contents_span = contents_span
        self._byte_range = byte_range
        self._signature_set: bool = False

    def get_content(self) -> bytes:
        """Return the bracketed bytes the caller must sign — the
        concatenation of the two slices identified by ``/ByteRange``."""
        return PDDocument._extract_bracketed(self._buffer, self._byte_range)

    def get_byte_range(self) -> list[int]:
        """Return the computed ``/ByteRange`` (post-placeholder-patch)."""
        return list(self._byte_range)

    def set_signature(self, pkcs7_der: bytes) -> None:
        """Splice ``pkcs7_der`` into the ``/Contents`` placeholder, drain the
        final document bytes to the configured output sink, and clear any
        pending-signature staging on the parent document."""
        if self._signature_set:
            raise RuntimeError("set_signature called twice on the same handle")
        final = PDDocument._splice_signature(
            self._buffer, self._contents_span, pkcs7_der
        )
        PDDocument._write_bytes_to_target(final, self._output)
        self._signature_set = True
        # Clear pending-signature staging on the document so a subsequent
        # save_incremental doesn't try to re-sign with no interface.
        self._document._pending_signature = None  # noqa: SLF001
        self._document._pending_signature_interface = None  # noqa: SLF001
        self._document._pending_signature_options = None  # noqa: SLF001


__all__ = ["PDDocument", "PDDocumentSource", "ExternalSigningSupport"]
