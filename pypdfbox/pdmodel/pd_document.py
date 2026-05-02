from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, BinaryIO

from pypdfbox.cos import COSArray, COSDictionary, COSDocument, COSName
from pypdfbox.io import RandomAccessRead, RandomAccessWrite

from .pd_page import PDPage
from .pd_page_tree import PDPageTree

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

    Cluster #1 surface:

    - construction (empty in-memory or wrapping an existing
      ``COSDocument``);
    - ``PDDocument.load(source)`` classmethod (forwards to ``Loader``);
    - page accessors (``get_pages``, ``get_number_of_pages``,
      ``add_page``, ``remove_page``);
    - ``save`` / ``save_incremental`` thin wrappers over ``COSWriter``;
    - version / encryption / security flags;
    - ``close`` + context manager.

    Methods touching encryption, signing, FDF, overlay, font subsetting,
    or printing raise ``NotImplementedError`` with a cluster pointer (see
    ``CHANGES.md`` for the consolidated list).
    """

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
        elif isinstance(source_or_doc, COSDocument):
            self._document = source_or_doc
            # Loader-built documents pass ownership of the source via
            # ``COSDocument._source``; we don't double-own it here.
            self._owns_document = True
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
        # reference-stable. Cleared when ``set_document_information`` is
        # called.
        self._document_information: PDDocumentInformation | None = None

        # Mirror the upstream ``allSecurityToBeRemoved`` flag.
        self._all_security_to_be_removed: bool = False

        # Lazy ``PDEncryption`` wrapper around the trailer's /Encrypt dict;
        # populated on first ``get_encryption()`` call or by ``decrypt()``.
        self._encryption: Any = None
        # Lazy :class:`DefaultResourceCache` — built on first access via
        # ``get_resource_cache``. Shared across every ``PDResources`` lookup
        # in the document so identical indirect refs round-trip the same
        # typed wrapper. ``None`` means "not yet allocated"; callers can
        # inject a custom cache (or ``None`` to disable) via
        # ``set_resource_cache``.
        self._resource_cache: Any = None
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
        # Pages root.
        pages = COSDictionary()
        pages.set_item(_TYPE, _PAGES)
        pages.set_item(_KIDS, COSArray())
        pages.set_int(_COUNT, 0)
        catalog.set_item(_PAGES, pages)
        # Mirror upstream's no-arg PDDocument: stamp /Version "1.4" on the
        # catalog so it matches the default header version.
        catalog.set_item(COSName.get_pdf_name("Version"), COSName.get_pdf_name("1.4"))
        trailer.set_item(_ROOT, catalog)
        self._document.set_trailer(trailer)

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
        ``documentInformation`` field. ``set_document_information`` clears
        the cache."""
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
            trailer.set_item(_INFO, info)
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

    # ---------- pages ----------

    def get_pages(self) -> PDPageTree:
        if self._pages is None:
            self._pages = self.get_document_catalog().get_pages()
        return self._pages

    def get_number_of_pages(self) -> int:
        return len(self.get_pages())

    def get_page(self, index: int) -> PDPage:
        """Return the page at the given 0-based index. Mirrors upstream
        ``PDDocument.getPage(int)``."""
        return self.get_pages()[index]

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

        ``compress_parameters`` is accepted for API parity but currently
        ignored: pypdfbox always writes uncompressed object streams (the
        compression toggle lands with the pdfwriter cluster). Callers may
        pass ``CompressParameters.NO_COMPRESSION`` to be explicit; any
        truthy compression request is silently downgraded to no-compression
        and recorded in CHANGES.md."""
        if self._closed:
            raise ValueError("operation on closed PDDocument")
        # Local import — pdfwriter depends on cos and we want the loader-style
        # late binding to keep import-time cycles impossible.
        from pypdfbox.pdfwriter import COSWriter

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
                trailer.remove_item(COSName.ENCRYPT)  # type: ignore[attr-defined]

        opened: BinaryIO | None = None
        sink: BinaryIO | RandomAccessWrite
        if isinstance(target, (str, os.PathLike)):
            opened = open(target, "wb")  # noqa: SIM115 — closed in finally
            sink = opened
        else:
            sink = target
        try:
            with COSWriter(sink) as writer:
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
            raise ValueError("operation on closed PDDocument")
        source = self._document.get_source()
        if source is None:
            raise ValueError(
                "save_incremental requires a loaded document with a source "
                "(use Loader.load_pdf or PDDocument.load)"
            )

        # Mirror upstream's second saveIncremental overload: stamp every
        # dict in ``objects_to_write`` as dirty so the writer emits it.
        if objects_to_write is not None:
            for entry in objects_to_write:
                if not isinstance(entry, COSDictionary):
                    raise TypeError(
                        f"save_incremental: objects_to_write must contain only "
                        f"COSDictionary instances, got {type(entry).__name__}"
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

    # Hex-character width reserved for the ``/Contents <…>`` placeholder.
    # 16384 hex chars = 8192 raw bytes, enough headroom for typical RSA-2048
    # PKCS#7 detached SignedData blobs (≈ 2-3 KiB) plus full chains and
    # OCSP / CRL evidence when present. Mirrors PDFBox's default reservation.
    _CONTENTS_PLACEHOLDER_HEX_LEN: int = 16384
    # Width (decimal digits) reserved for each ByteRange placeholder slot.
    # Wide enough to cover any PDF up to ~10 GiB without re-flowing offsets.
    _BYTERANGE_SLOT_WIDTH: int = 10

    def _render_incremental_with_placeholder(
        self,
    ) -> tuple[bytearray, tuple[int, int], list[int]]:
        """Run the incremental writer with the pending signature carrying a
        ``/Contents <0…0>`` placeholder of ``_CONTENTS_PLACEHOLDER_HEX_LEN``
        hex chars and a ``/ByteRange [0 ☐ ☐ ☐]`` placeholder. After the
        bytes are produced, locate the placeholders, compute the real
        ``/ByteRange``, and patch it in place. The ``/Contents`` slot is
        left as zeros for the caller (or :meth:`save_incremental`) to
        splice into."""
        from pypdfbox.cos import COSArray, COSInteger
        from pypdfbox.pdfwriter import COSWriter

        sig = self._pending_signature
        assert sig is not None
        sig_dict = sig.get_cos_object()

        # Install the /Contents placeholder: a COSString of all-zero bytes
        # whose hex form occupies exactly _CONTENTS_PLACEHOLDER_HEX_LEN chars.
        placeholder_bytes = b"\x00" * (self._CONTENTS_PLACEHOLDER_HEX_LEN // 2)
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
        zero_run = b"<" + b"0" * self._CONTENTS_PLACEHOLDER_HEX_LEN + b">"
        idx = rendered.rfind(zero_run)
        if idx < 0:
            raise RuntimeError(
                "signature splice failed: /Contents placeholder not found "
                "in writer output (writer may have collapsed the COSString)"
            )
        # contents_span is the slice [start, end) covering the hex zeros
        # BETWEEN the angle brackets — what we'll overwrite with PKCS#7 hex.
        contents_start = idx + 1  # skip the '<'
        contents_end = contents_start + self._CONTENTS_PLACEHOLDER_HEX_LEN

        # ByteRange = [start1, len1, start2, len2] where the two slices
        # bracket the /Contents bytes (INCLUDING the angle brackets, per
        # ISO 32000-1 §12.8.1: "the byte range shall span the entire file
        # except the bytes between < and >, exclusive of those delimiters").
        # Strictly: bytes 0..idx (just before `<`), then idx+1+N+1..end.
        contents_open = idx                        # position of `<`
        contents_close = idx + len(zero_run) - 1   # position of `>`
        start1 = 0
        len1 = contents_open + 1                   # include `<`
        start2 = contents_close                    # include `>`
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
        (PDF 1.4+ allows the catalog to override the header)."""
        header_version = self._document.get_version()
        try:
            catalog_str = self.get_document_catalog().get_version()
        except Exception:  # noqa: BLE001 — catalog may be absent on raw docs
            catalog_str = None
        if catalog_str is not None:
            try:
                catalog_version = float(catalog_str)
                return max(header_version, catalog_version)
            except ValueError:
                pass
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
                trailer.remove_item(COSName.ENCRYPT)  # type: ignore[attr-defined]
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
        trailer.set_item(COSName.ENCRYPT, enc_dict)  # type: ignore[attr-defined]

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

        Raises :class:`PDInvalidPasswordException` when the password is
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

        if isinstance(password, str):
            password_bytes: bytes = password.encode("utf-8")
        else:
            password_bytes = bytes(password)

        handler = StandardSecurityHandler(encryption)
        handler.prepare_for_decryption(
            encryption,
            document_id,
            StandardDecryptionMaterial(password_bytes),
        )

        # Walk every loaded indirect — attach the handler to each COSStream
        # so that ``create_input_stream`` decrypts before the filter chain.
        # This also covers xref-stream objects (PDF 1.5+ encrypted xref
        # streams, /Type /XRef): they live in the same pool and inherit
        # from COSStream, so the same hook deciphers their body when the
        # parser cluster reads it back.
        for cos_obj in self._document.get_objects():
            # Avoid forcing a parse on objects that aren't yet loaded —
            # the lazy loader will see the security handler attached at
            # the COSStream level once it materialises. ``get_object()``
            # only triggers parsing for stream-bearing entries because the
            # stream body itself is encrypted, so we still call through.
            actual = cos_obj.get_object()
            if isinstance(actual, _COSStream):
                actual.set_security_handler(
                    handler,
                    cos_obj.get_object_number(),
                    cos_obj.get_generation_number(),
                )

        self._security_handler = handler
        self._encryption = encryption

    def protect(self, protection_policy: Any) -> None:
        """Stage an encryption policy on the document — actual key
        derivation and ``/Encrypt`` synthesis happen at save time via the
        writer. Mirrors upstream ``PDDocument.protect``."""
        from pypdfbox.pdmodel.encryption.standard_protection_policy import (
            StandardProtectionPolicy,
        )

        if not isinstance(protection_policy, StandardProtectionPolicy):
            # Public-key handlers land later — fail loudly until then.
            raise NotImplementedError(
                "PDDocument.protect: only StandardProtectionPolicy is supported "
                "(public-key handler dispatch is deferred)"
            )
        self._protection_policy = protection_policy

    def get_current_access_permission(self) -> Any:
        """Return the :class:`AccessPermission` derived from the most
        recent successful :meth:`decrypt` call (owner-level when no
        decryption occurred but the document is unencrypted). When the
        document is encrypted but not yet decrypted, returns a
        no-permission default."""
        from pypdfbox.pdmodel.encryption.access_permission import AccessPermission

        if self._security_handler is not None:
            current = getattr(
                self._security_handler, "get_current_access_permission", None
            )
            if callable(current):
                return current()
        if not self.is_encrypted():
            return AccessPermission.get_owner_access_permission()
        return AccessPermission(0)

    def add_signature(
        self,
        sig: PDSignature,
        signature_interface: SignatureInterface | None = None,
        options: Any = None,
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
        """
        from .interactive.digitalsignature.pd_signature import PDSignature

        if not isinstance(sig, PDSignature):
            raise TypeError(
                f"add_signature expected a PDSignature, got {type(sig).__name__}"
            )
        if self._signature_added:
            # Mirrors upstream ``IllegalStateException`` — Java's nearest
            # equivalent is ``RuntimeError`` here, but we surface it as
            # ``ValueError`` for symmetry with the rest of the PDDocument
            # surface (closed-doc / no-source guards both raise ValueError).
            raise ValueError("Only one signature may be added in a document")

        sig_dict = sig.get_cos_object()

        # Default /Filter + /SubFilter when caller didn't set them — matches
        # PDFBox's default ``Adobe.PPKLite`` + ``adbe.pkcs7.detached`` choice.
        if sig.get_filter() is None:
            sig.set_filter("Adobe.PPKLite")
        if sig.get_sub_filter() is None:
            sig.set_sub_filter("adbe.pkcs7.detached")

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
        if isinstance(fields_arr, COSArray):
            fields_arr.set_needs_to_be_updated(True)

        # Register so the next save_incremental knows to splice.
        self._pending_signature = sig
        self._pending_signature_interface = signature_interface
        self._pending_signature_options = options
        self._signature_added = True

    def import_page(self, page: PDPage) -> PDPage:
        """Deep-copy ``page`` into this document and return the new
        :class:`PDPage`.

        The page's dictionary, ``/Resources``, ``/Contents`` stream(s), and
        inheritable attributes are copied. Annotations are copied as-is
        (their ``/Subtype``-specific references are NOT remapped;
        cross-document ``/Names`` tree merging, ``/Dest`` resolution, font
        / image resource deduplication, and annotation ``/Parent`` /
        ``/AcroForm`` field fix-ups are deferred — see ``CHANGES.md``)."""
        src_dict = page.get_cos_object()
        new_dict = self._deep_copy_cos(src_dict, set())
        # Drop /Parent — re-set when added to our page tree.
        new_dict.remove_item(COSName.get_pdf_name("Parent"))
        new_page = PDPage(new_dict)
        self.get_pages().add(new_page)
        return new_page

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
        if self._resource_cache is None:
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
            raise ValueError("operation on closed PDDocument")
        if self._pending_signature is None:
            raise ValueError(
                "save_incremental_for_external_signing requires a prior "
                "add_signature(...) call"
            )
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
            raise ValueError("operation on closed PDDocument")
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
            raise ValueError("operation on closed PDDocument")
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
