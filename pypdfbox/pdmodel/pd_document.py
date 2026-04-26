from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, BinaryIO

from pypdfbox.cos import COSArray, COSDictionary, COSDocument, COSName
from pypdfbox.io import RandomAccessRead, RandomAccessWrite

from .pd_page import PDPage
from .pd_page_tree import PDPageTree

if TYPE_CHECKING:
    from .pd_document_catalog import PDDocumentCatalog


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
    def load(cls, source: PDDocumentSource) -> PDDocument:
        """Convenience classmethod — forwards to ``Loader.load_pdf`` and
        wraps the result in a ``PDDocument``. Matches PRD §7's example
        usage ``with PDDocument.load(path) as doc: …``."""
        # Local import to avoid a circular import at module load time.
        from pypdfbox.loader import Loader

        cos_doc = Loader.load_pdf(source)
        return cls(cos_doc)

    # ---------- COS surface ----------

    def get_document(self) -> COSDocument:
        return self._document

    def get_document_catalog(self) -> PDDocumentCatalog:
        from .pd_document_catalog import PDDocumentCatalog

        if self._catalog is None:
            self._catalog = PDDocumentCatalog(self)
        return self._catalog

    def get_document_information(self) -> COSDictionary | None:
        """Cluster #1 returns the raw ``/Info`` dictionary (or ``None``).
        ``PDDocumentInformation`` wrapper lands in cluster #2 — see
        ``CHANGES.md``."""
        trailer = self._document.get_trailer()
        if trailer is None:
            return None
        info = trailer.get_dictionary_object(_INFO)
        return info if isinstance(info, COSDictionary) else None

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

        opened: BinaryIO | None = None
        sink: BinaryIO | RandomAccessWrite
        if isinstance(target, (str, os.PathLike)):
            opened = open(target, "wb")  # noqa: SIM115 — closed in finally
            sink = opened
        else:
            sink = target
        try:
            with COSWriter(sink) as writer:
                writer.write(self._document)
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

    # ---------- stubs (later clusters) ----------

    def get_encryption(self) -> Any:
        raise NotImplementedError(
            "PDDocument.get_encryption requires PDEncryption — pdmodel cluster #10"
        )

    def set_encryption_dictionary(self, _encryption: Any) -> None:
        raise NotImplementedError(
            "PDDocument.set_encryption_dictionary — pdmodel cluster #10"
        )

    def protect(self, _policy: Any) -> None:
        raise NotImplementedError(
            "PDDocument.protect — pdmodel cluster #10 (security)"
        )

    def get_current_access_permission(self) -> Any:
        raise NotImplementedError(
            "PDDocument.get_current_access_permission — pdmodel cluster #10"
        )

    def add_signature(self, *_args: Any, **_kwargs: Any) -> None:
        raise NotImplementedError(
            "PDDocument.add_signature — pdmodel cluster #10 (signatures)"
        )

    def import_page(self, _page: PDPage) -> PDPage:
        raise NotImplementedError(
            "PDDocument.import_page requires content-stream rewriting — "
            "pdmodel cluster #3 + contentstream cluster"
        )

    def get_resource_cache(self) -> Any:
        raise NotImplementedError(
            "PDDocument.get_resource_cache requires ResourceCache — "
            "pdmodel cluster #3 (XObject)"
        )

    def set_resource_cache(self, _cache: Any) -> None:
        raise NotImplementedError(
            "PDDocument.set_resource_cache — pdmodel cluster #3"
        )

    def register_true_type_font_for_closing(self, _font: Any) -> None:
        raise NotImplementedError(
            "PDDocument.register_true_type_font_for_closing — "
            "pdmodel cluster #4 (fonts)"
        )

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
