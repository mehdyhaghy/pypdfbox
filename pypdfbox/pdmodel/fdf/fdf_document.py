from __future__ import annotations

import contextlib
import os
from typing import IO, BinaryIO
from xml.dom.minidom import Document as XmlDocument
from xml.dom.minidom import Element

from pypdfbox.cos import COSDictionary, COSDocument, COSName
from pypdfbox.io import RandomAccessRead, RandomAccessWrite

from .fdf_catalog import FDFCatalog

_ROOT: COSName = COSName.get_pdf_name("Root")
_FDF: COSName = COSName.get_pdf_name("FDF")
_VERSION: float = 1.2  # FDF default version, mirrors upstream FDFDocument.

# Source-type alias mirrors :data:`PDDocumentSource`.
FDFSource = (
    str
    | os.PathLike[str]
    | bytes
    | bytearray
    | memoryview
    | BinaryIO
    | RandomAccessRead
)


class FDFDocument:
    """In-memory FDF (Forms Data Format) document. Mirrors
    ``org.apache.pdfbox.pdmodel.fdf.FDFDocument``.

    An FDF file is structured exactly like a PDF — header, object pool,
    xref, trailer — but its catalog points at a single ``/FDF``
    sub-dictionary that carries form-field values, annotations, and the
    name of the source PDF.

    This wave covers:

    - construction (empty in-memory or wrapping an existing
      :class:`COSDocument`);
    - :meth:`load` classmethod (forwards to ``Loader.load_pdf`` because
      FDF and PDF share the parser);
    - :meth:`get_catalog` returning a :class:`FDFCatalog`;
    - :meth:`get_document` exposing the underlying :class:`COSDocument`;
    - :meth:`save` writing to a path / stream / :class:`RandomAccessWrite`;
    - :meth:`close` + context manager.

    XFDF (the XML-encoded variant) is **not** supported in this cluster —
    it requires its own SAX-based parser/serializer and will land in a
    later wave (see ``CHANGES.md`` once that wave ships).
    """

    def __init__(
        self,
        source_or_doc: COSDocument | None = None,
        fdf_source: RandomAccessRead | None = None,
    ) -> None:
        if source_or_doc is None:
            self._document = COSDocument()
            self._owns_document = True
            self._build_minimal_skeleton()
        elif isinstance(source_or_doc, COSDocument):
            self._document = source_or_doc
            self._owns_document = True
        else:
            raise TypeError(
                f"FDFDocument expected COSDocument or None; got "
                f"{type(source_or_doc).__name__}"
            )
        # Optional backing source — mirrors upstream's ``RandomAccessRead
        # source`` constructor parameter (lines 93-98). Closed alongside
        # the COSDocument in :meth:`close`.
        self._fdf_source: RandomAccessRead | None = fdf_source
        # Cached catalog wrapper.
        self._catalog: FDFCatalog | None = None
        self._closed: bool = False

    # ---------- construction helpers ----------

    def _build_minimal_skeleton(self) -> None:
        """Build the minimum trailer + catalog + /FDF dict so a freshly
        constructed ``FDFDocument`` is immediately saveable. Mirrors
        upstream's no-arg ``new FDFDocument()``.
        """
        trailer = COSDictionary()
        catalog = COSDictionary()
        # /FDF sub-dictionary (intentionally empty — populated by callers
        # via ``get_catalog().get_fdf().set_fields(...)`` etc.).
        catalog.set_item(_FDF, COSDictionary())
        trailer.set_item(_ROOT, catalog)
        self._document.set_trailer(trailer)
        # FDF default header version — upstream stamps "1.2" on new docs.
        self._document.set_version(_VERSION)

    # ---------- alternate construction ----------

    @classmethod
    def load(cls, source: FDFSource) -> FDFDocument:
        """Parse an FDF file from a path, bytes, stream, or
        :class:`RandomAccessRead`.

        FDF shares PDF's object/xref/trailer wire structure but begins with
        an ``%FDF-x.y`` header, not ``%PDF-``. ``Loader.load_pdf`` drives the
        full xref-walking parser, whose header check accepts either marker
        (see ``PDFParser.parse_header``), so a real FDF file — including one
        pypdfbox itself just saved with its ``%FDF-`` header — parses
        correctly. (Routing through the bare ``%PDF-``-only header check
        previously rejected every genuine FDF.)

        Mirrors ``Loader.loadFDF(...)`` upstream.
        """
        from pypdfbox.loader import Loader

        cos_doc = Loader.load_pdf(source)
        return cls(cos_doc)

    # ---------- COS surface ----------

    def get_document(self) -> COSDocument:
        """Return the underlying :class:`COSDocument` (mirrors upstream
        ``FDFDocument.getDocument()``)."""
        return self._document

    def get_catalog(self) -> FDFCatalog:
        """Return the FDF catalog wrapper. Lazily allocated; if the
        trailer's ``/Root`` is missing, an empty catalog is wired in
        (mirrors upstream which never returns ``null``).
        """
        if self._catalog is not None:
            trailer = self._document.get_trailer()
            if trailer is not None:
                root = trailer.get_dictionary_object(_ROOT)
                if isinstance(root, COSDictionary) and root is self._catalog.get_cos_object():
                    return self._catalog
        trailer = self._document.get_trailer()
        if trailer is None:
            trailer = COSDictionary()
            self._document.set_trailer(trailer)
        root = trailer.get_dictionary_object(_ROOT)
        if not isinstance(root, COSDictionary):
            root = COSDictionary()
            trailer.set_item(_ROOT, root)
        self._catalog = FDFCatalog(root)
        return self._catalog

    def set_catalog(self, catalog: FDFCatalog) -> None:
        """Wire ``catalog`` into the trailer's ``/Root``. Mirrors upstream
        ``FDFDocument.setCatalog(FDFCatalog)`` (lines 173-177).
        """
        trailer = self._document.get_trailer()
        if trailer is None:
            trailer = COSDictionary()
            self._document.set_trailer(trailer)
        trailer.set_item(_ROOT, catalog.get_cos_object())
        # Invalidate the cached wrapper so :meth:`get_catalog` re-reads
        # from the trailer on next access.
        self._catalog = catalog

    # ---------- XFDF (XML Forms Data Format) ----------

    def write_xml(self, output: IO[str]) -> None:
        """Serialise this FDF document as XFDF XML to ``output``. Mirrors
        upstream ``FDFDocument.writeXML(Writer)`` (lines 126-134).
        """
        output.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        output.write('<xfdf xmlns="http://ns.adobe.com/xfdf/" xml:space="preserve">\n')
        self.get_catalog().write_xml(output)
        output.write("</xfdf>\n")

    # ---------- save ----------

    def save(
        self,
        target: str | os.PathLike[str] | BinaryIO | RandomAccessWrite,
    ) -> None:
        """Serialize this FDF to a path, writable binary stream, or
        :class:`RandomAccessWrite`. Uses the shared :class:`COSWriter`
        (FDF and PDF share the wire format).
        """
        if self._closed:
            raise OSError("Cannot save a document which has been closed")
        from pypdfbox.pdfwriter import COSWriter

        opened: BinaryIO | None = None
        sink: BinaryIO | RandomAccessWrite
        if isinstance(target, (str, os.PathLike)):
            opened = open(target, "wb")  # noqa: SIM115 — closed in finally
            sink = opened
        else:
            sink = target
        try:
            # ``fdf=True`` makes the writer emit an ``%FDF-x.y`` header
            # instead of ``%PDF-``. PDFBox's FDFParser requires the FDF
            # marker; a PDF-marked FDF fails to reload ("Header doesn't
            # contain versioninfo"). Mirrors upstream COSWriter.write(FDFDocument).
            with COSWriter(sink, fdf=True) as writer:
                # FDF's wire format is identical to PDF — feed the raw
                # COSDocument so the writer doesn't try to walk a
                # PDDocument-shaped structure that doesn't exist here.
                writer.write(self._document)
        finally:
            if opened is not None:
                opened.close()

    # ---------- /FDF convenience accessors (parity with upstream) ----------

    def set_xfdf(self, xfdf: XmlDocument | Element | bytes | bytearray | IO[bytes]) -> None:
        """Replace this document's catalog with the contents of an XFDF
        XML document. Mirrors the ``FDFDocument(org.w3c.dom.Document)``
        constructor upstream (``FDFDocument.java`` lines 106-117).

        Accepts any of:

        - a parsed :class:`xml.dom.minidom.Document` (the upstream form);
        - a parsed :class:`xml.dom.minidom.Element` pointing at the
          ``<xfdf>`` root;
        - raw ``bytes`` / ``bytearray`` holding XFDF XML;
        - a binary stream (anything with a ``.read()`` method).

        Raises ``OSError`` when the input is not rooted at an ``<xfdf>``
        element — matches the upstream ``IOException`` contract.
        """
        from pypdfbox.util.xml_util import XMLUtil

        from .xfdf_parser import populate_fdf_dictionary_from_xfdf

        if isinstance(xfdf, XmlDocument):
            root = xfdf.documentElement
        elif isinstance(xfdf, Element):
            root = xfdf
        elif isinstance(xfdf, (bytes, bytearray)):
            root = XMLUtil.parse(xfdf).documentElement
        elif hasattr(xfdf, "read"):
            root = XMLUtil.parse(xfdf).documentElement  # type: ignore[arg-type]
        else:
            raise TypeError(
                "FDFDocument.set_xfdf expected an XML document, element, "
                f"bytes, or readable stream; got {type(xfdf).__name__}"
            )

        if root is None or root.tagName != "xfdf":
            actual = root.tagName if root is not None else None
            raise OSError(
                "Error while importing xfdf document, root should be "
                f"'xfdf' and not {actual!r}"
            )

        # Rebuild the catalog: fresh FDFCatalog, fresh FDFDictionary,
        # populated from the parsed XML. Matches upstream
        # ``FDFDocument(Document)`` which constructs a new ``FDFCatalog``
        # via the ``Element`` overload then assigns it via setCatalog.
        from .fdf_dictionary import FDFDictionary

        catalog = FDFCatalog()
        fdf_dict = FDFDictionary()
        populate_fdf_dictionary_from_xfdf(fdf_dict, root)
        catalog.set_fdf(fdf_dict)
        self.set_catalog(catalog)

    def save_xfdf(
        self,
        target: str | os.PathLike[str] | IO[str],
    ) -> None:
        """Serialise this document as XFDF XML to ``target`` (path or
        text stream). Mirrors the trio of upstream ``saveXFDF(...)``
        overloads (lines 226-267): file path string, ``File``, and
        ``Writer``.

        For path-like targets, the file is opened in UTF-8 text mode (the
        upstream wraps the ``FileOutputStream`` with an
        ``OutputStreamWriter`` over ``StandardCharsets.UTF_8``).
        """
        if self._closed:
            raise OSError("Cannot save a document which has been closed")
        if isinstance(target, (str, os.PathLike)):
            with open(target, "w", encoding="utf-8", newline="") as writer:
                self.write_xml(writer)
            return
        # Treat as a text-mode writer. Upstream closes the writer at the
        # tail of saveXFDF(Writer) (lines 254-267) — we mirror that.
        try:
            self.write_xml(target)
        finally:
            close = getattr(target, "close", None)
            if callable(close):
                close()

    # ---------- lifecycle ----------

    def is_closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_document:
            self._document.close()
        # Mirror upstream: also drain the backing RandomAccessRead, if
        # any, swallowing-and-logging follow-on errors (lines 282-294).
        src = self._fdf_source
        if src is not None:
            self._fdf_source = None
            close = getattr(src, "close", None)
            if callable(close):
                # Mirror IOUtils.closeAndLogException — swallow follow-on
                # I/O errors so close() stays best-effort.
                with contextlib.suppress(Exception):
                    close()

    def __enter__(self) -> FDFDocument:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()
