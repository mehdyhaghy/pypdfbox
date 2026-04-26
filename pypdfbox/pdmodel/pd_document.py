from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, BinaryIO

from pypdfbox.cos import COSArray, COSDictionary, COSDocument, COSName
from pypdfbox.io import RandomAccessRead, RandomAccessWrite

from .pd_page import PDPage
from .pd_page_tree import PDPageTree

if TYPE_CHECKING:
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
        # Active security handler after ``decrypt()`` succeeds — used by
        # ``get_current_access_permission`` and by the writer for encrypt
        # passes.
        self._security_handler: Any = None
        # Policy staged by ``protect()`` and consumed by the writer at save.
        self._protection_policy: Any = None

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

    def get_document_information(self) -> PDDocumentInformation:
        """Return the trailer's ``/Info`` dictionary wrapped as
        ``PDDocumentInformation``. If absent, an empty wrapper is created
        and wired into the trailer so subsequent setters round-trip
        (matches upstream ``PDDocument.getDocumentInformation``)."""
        from .pd_document_information import PDDocumentInformation

        trailer = self._document.get_trailer()
        if trailer is None:
            trailer = COSDictionary()
            self._document.set_trailer(trailer)
        info = trailer.get_dictionary_object(_INFO)
        if not isinstance(info, COSDictionary):
            info = COSDictionary()
            trailer.set_item(_INFO, info)
        return PDDocumentInformation(info)

    def set_document_information(self, info: PDDocumentInformation) -> None:
        """Replace the trailer's ``/Info`` entry."""
        trailer = self._document.get_trailer()
        if trailer is None:
            trailer = COSDictionary()
            self._document.set_trailer(trailer)
        trailer.set_item(_INFO, info.get_cos_object())

    # ---------- pages ----------

    def get_pages(self) -> PDPageTree:
        if self._pages is None:
            self._pages = self.get_document_catalog().get_pages()
        return self._pages

    def get_number_of_pages(self) -> int:
        return len(self.get_pages())

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
    ) -> None:
        """Full save via ``COSWriter``. Accepts a path, a writable binary
        stream, or a ``RandomAccessWrite``. Mirrors the multiple ``save``
        overloads upstream."""
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
    ) -> None:
        """Append-only save via ``COSWriter(incremental=True)``.

        Requires the document to have been loaded from a parsable source
        — incremental mode preserves the original bytes and appends only
        objects flagged ``needs_to_be_updated``. Synthesised documents
        with no source raise ``ValueError`` (matches upstream)."""
        if self._closed:
            raise ValueError("operation on closed PDDocument")
        source = self._document.get_source()
        if source is None:
            raise ValueError(
                "save_incremental requires a loaded document with a source "
                "(use Loader.load_pdf or PDDocument.load)"
            )

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
        ``PDDocument.setVersion``)."""
        if version < self.get_version():
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
        :class:`PDEncryption` (preferred) or a raw ``COSDictionary``."""
        from pypdfbox.cos import COSDictionary as _COSDictionary

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

    def add_signature(self, *_args: Any, **_kwargs: Any) -> None:
        raise NotImplementedError(
            "Signature creation deferred — PDSignature.verify works for "
            "read-side. See PRD §6.10 for the signing pipeline."
        )

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

    def register_true_type_font_for_closing(self, font: Any) -> None:
        """Register ``font`` to be closed when the document closes. Lite
        stub — Python GC handles TTF lifetimes for us, so this method just
        appends to an internal list without driving any teardown. Provided
        to keep the upstream API surface complete; full lifecycle
        management lands when font subsetting does (see ``CHANGES.md``)."""
        self._fonts_to_close.append(font)

    def save_incremental_for_external_signing(self, _output: Any) -> Any:
        raise NotImplementedError(
            "PDDocument.save_incremental_for_external_signing — "
            "pdmodel cluster #10 (signatures)"
        )

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
