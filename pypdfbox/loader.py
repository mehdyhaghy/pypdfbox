from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, BinaryIO, TypeGuard

from pypdfbox.cos import COSDocument
from pypdfbox.io import (
    RandomAccessRead,
    RandomAccessReadBuffer,
    RandomAccessReadBufferedFile,
)
from pypdfbox.pdfparser import PDFParseError, PDFParser

if TYPE_CHECKING:
    from pypdfbox.pdmodel.fdf import FDFDocument

# Type alias for everything Loader.load_pdf accepts. Mirrors the overloads
# of org.apache.pdfbox.Loader.loadPDF (file, byte[], RandomAccessRead,
# InputStream).
PDFSource = (
    str
    | os.PathLike[str]
    | bytes
    | bytearray
    | memoryview
    | BinaryIO
    | RandomAccessRead
)


def _is_binary_stream_like(source: object) -> TypeGuard[BinaryIO]:
    """Return True for stream-shaped inputs accepted by ``load_pdf``."""
    return callable(getattr(source, "read", None))


class Loader:
    """
    Top-level entry point for parsing a PDF — mirrors
    ``org.apache.pdfbox.Loader``.

    The PDFBox class exposes many overloads (paths, bytes, streams,
    ``RandomAccessRead``, plus password / ``MemoryUsageSetting`` knobs).
    This port covers the source forms and password-based auto-decryption;
    memory-usage tuning and key-store overloads are deferred until their
    corresponding subsystems land.

    Lifecycle: when ``load_pdf`` is given a path, byte buffer, or stream,
    the Loader constructs the underlying ``RandomAccessRead`` itself and
    hands it to the resulting ``COSDocument`` as an owned resource —
    ``doc.close()`` then closes it. Stream inputs are copied into memory
    and closed immediately after buffering, matching the local
    ``RandomAccessReadBuffer.create_buffer_from_stream`` contract. When
    the caller passes a ``RandomAccessRead`` directly, ownership stays
    with the caller.
    """

    @staticmethod
    def load_pdf(
        source: PDFSource,
        password: str | bytes | None = None,
        /,
    ) -> COSDocument:
        """Parse a PDF from one of the supported sources and return the
        populated ``COSDocument``.

        When ``password`` is supplied (or the empty string for blank-password
        documents) and the parsed trailer carries an ``/Encrypt`` entry, the
        document is auto-decrypted: a ``StandardSecurityHandler`` is wired
        into every ``COSStream`` so subsequent reads decipher transparently.
        Encrypted documents loaded without a password are returned encrypted —
        the caller can wrap them in a ``PDDocument`` and call ``decrypt`` later.

        Mirrors PDFBox ``Loader.loadPDF(..., String password)``."""
        access, owned = Loader._coerce_source(source)
        parser = PDFParser(access)
        # Stage the password BEFORE ``parse()`` so the parser can stand up
        # a security handler the instant the trailer's ``/Encrypt`` becomes
        # available — required for PDF 1.5+ documents whose xref *itself*
        # is an encrypted stream (the body must be deciphered before its
        # ``/FlateDecode`` filter can run; otherwise zlib sees ciphertext
        # and fails with "incorrect header check"). The post-parse
        # ``PDDocument.decrypt`` path is too late for that case.
        if password is not None:
            parser.set_password(password)
        try:
            document = parser.parse()
        except PDFParseError as e:
            partial_document = parser.get_document()
            if partial_document is not None:
                partial_document.close()
            if owned:
                access.close()
            # Mirror upstream Loader.loadPDF: malformed input surfaces as
            # an IOException-equivalent (OSError) at the Loader boundary.
            raise OSError(str(e)) from e
        except BaseException:
            partial_document = parser.get_document()
            if partial_document is not None:
                partial_document.close()
            if owned:
                access.close()
            raise
        if owned:
            # Hand ownership to the document so doc.close() releases it.
            document._source = access  # noqa: SLF001 — sibling-package handoff

        # Auto-decrypt path: only kick in when the document is actually
        # encrypted AND the caller passed a password (empty string counts —
        # plenty of documents are protected with a blank user password).
        if password is not None and document.is_encrypted():
            try:
                from pypdfbox.pdmodel import PDDocument  # noqa: PLC0415
            except ImportError:
                # pdmodel layer not installed yet — return the encrypted
                # COSDocument and let the caller drive decryption manually.
                return document
            pd = PDDocument(document)
            # The COSDocument is the loader's return value — the transient
            # wrapper must not assume ownership (a stray gc cycle could
            # close the document out from under the caller).
            pd._owns_document = False  # noqa: SLF001
            try:
                pd.decrypt(password)
            except BaseException:
                if owned:
                    access.close()
                raise
            # Stash the prepared security handler / encryption on the
            # COSDocument so a *fresh* PDDocument wrapper (e.g. via
            # ``PDDocument.load`` which re-wraps the result) can pick them
            # up without re-running the (expensive) PBKDF2-based key
            # derivation. This is the only path where ``_security_handler``
            # would otherwise be lost between the transient decrypt-time
            # wrapper and the caller-visible wrapper.
            document_any: Any = document
            document_any._loader_security_handler = pd._security_handler  # noqa: SLF001
            document_any._loader_encryption = pd._encryption  # noqa: SLF001
        return document

    @staticmethod
    def load(
        source: PDFSource,
        password: str | bytes | None = None,
        /,
    ) -> COSDocument:
        """Upstream-name alias for :meth:`load_pdf`.

        Mirrors ``org.apache.pdfbox.Loader.loadPDF`` — many call sites in
        upstream samples and third-party code use the bare ``Loader.load``
        spelling, so we expose both names with identical semantics.
        """
        return Loader.load_pdf(source, password)

    @staticmethod
    def load_pdf_from_bytes(
        data: bytes | bytearray | memoryview,
        password: str | bytes | None = None,
        /,
    ) -> COSDocument:
        """Explicit bytes entry point — mirrors PDFBox
        ``Loader.loadPDF(byte[])``.

        Equivalent to ``Loader.load_pdf(data, password)`` but rejects
        non-bytes-like inputs eagerly so callers get a clear error message
        at the boundary instead of a generic ``TypeError`` deeper in
        ``_coerce_source``.
        """
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError(
                "Loader.load_pdf_from_bytes expected bytes, bytearray, or "
                f"memoryview; got {type(data).__name__}"
            )
        return Loader.load_pdf(data, password)

    @staticmethod
    def load_pdf_from_file(
        path: str | os.PathLike[str],
        password: str | bytes | None = None,
        /,
    ) -> COSDocument:
        """Explicit path entry point — mirrors PDFBox
        ``Loader.loadPDF(File)``.

        Equivalent to ``Loader.load_pdf(path, password)`` but rejects
        non-path inputs eagerly. Accepts ``str``, ``pathlib.Path``, and
        any ``os.PathLike``.
        """
        if not isinstance(path, (str, os.PathLike)):
            raise TypeError(
                "Loader.load_pdf_from_file expected str or PathLike; got "
                f"{type(path).__name__}"
            )
        return Loader.load_pdf(path, password)

    @staticmethod
    def load_xfdf(source: PDFSource) -> FDFDocument:
        """Parse an XFDF (XML Forms Data Format) document — mirrors
        ``org.apache.pdfbox.Loader.loadXFDF``.

        Accepts the same source shapes as :meth:`load_pdf`: a path,
        bytes-like buffer, binary stream, or :class:`RandomAccessRead`.
        Returns a populated :class:`pypdfbox.pdmodel.fdf.FDFDocument`.

        Mirrors ``Loader.loadXFDF(File)`` / ``Loader.loadXFDF(InputStream)``
        upstream (``Loader.java`` lines 120-155), which both eventually
        delegate to ``new FDFDocument(XMLUtil.parse(input))``.
        """
        from pypdfbox.pdmodel.fdf import FDFDocument  # noqa: PLC0415
        from pypdfbox.util.xml_util import XMLUtil  # noqa: PLC0415

        # Read the source as bytes for XMLUtil.parse (which itself reads
        # via defusedxml). We use the same _coerce_source helper to
        # accept paths, bytes, streams and RandomAccessRead uniformly,
        # then drain the resulting RandomAccessRead into memory.
        access, owned = Loader._coerce_source(source)
        try:
            access.seek(0)
            data = access.read_fully(access.length())
        finally:
            if owned:
                access.close()

        xml_doc = XMLUtil.parse(data)
        fdf = FDFDocument()
        try:
            fdf.set_xfdf(xml_doc)
        except BaseException:
            fdf.close()
            raise
        return fdf

    @staticmethod
    def load_fdf(source: PDFSource) -> FDFDocument:
        """Parse an FDF (Forms Data Format) document — mirrors
        ``org.apache.pdfbox.Loader.loadFDF``.

        FDF shares PDF's object/xref/trailer wire structure, so this
        delegates to :class:`pypdfbox.pdmodel.fdf.FDFDocument`'s loader and
        returns the high-level FDF wrapper.
        """
        from pypdfbox.pdmodel.fdf import FDFDocument  # noqa: PLC0415

        return FDFDocument.load(source)

    @staticmethod
    def _coerce_source(source: PDFSource) -> tuple[RandomAccessRead, bool]:
        """Return ``(random_access_read, loader_owns_it)``."""
        # Order matters: RandomAccessRead is checked first so a custom
        # subclass that also happens to expose ``.read`` doesn't get
        # routed through the BinaryIO branch.
        if isinstance(source, RandomAccessRead):
            return source, False
        if isinstance(source, (str, os.PathLike)):
            return RandomAccessReadBufferedFile(source), True
        if isinstance(source, (bytes, bytearray, memoryview)):
            return RandomAccessReadBuffer(source), True
        if _is_binary_stream_like(source):
            return RandomAccessReadBuffer.create_buffer_from_stream(source), True
        raise TypeError(
            "Loader.load_pdf expected a path, bytes-like object, binary "
            f"stream, or RandomAccessRead; got {type(source).__name__}"
        )

    # Upstream Java aliases (camelCase mirrors of the snake_case API).
    loadPDF = load_pdf  # noqa: N815
    loadFDF = load_fdf  # noqa: N815
    loadXFDF = load_xfdf  # noqa: N815
