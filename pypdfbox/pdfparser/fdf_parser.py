from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos.cos_name import COSName
from pypdfbox.io.io_utils import close_quietly

from .cos_parser import COSParser
from .parse_error import PDFParseError

if TYPE_CHECKING:
    from pypdfbox.io.random_access_read import RandomAccessRead
    from pypdfbox.pdmodel.fdf.fdf_document import FDFDocument


class FDFParser(COSParser):
    """Parser for FDF (Forms Data Format) files.

    Mirrors upstream ``org.apache.pdfbox.pdfparser.FDFParser``. FDF is a
    PDF-derived format that carries only form field data without the
    full document structure; this parser shares all infrastructure with
    :class:`COSParser` and adds an FDF-specific header detection step.
    """

    def __init__(self, source: RandomAccessRead) -> None:
        super().__init__(source)

    # ------------------------------------------------------------------
    # Parsing entry points
    # ------------------------------------------------------------------

    def _initial_parse(self) -> None:
        """Initial parse — retrieve the trailer and confirm a ``/Root``.

        Mirrors upstream ``FDFParser.initialParse`` (Java line 48,
        private).
        """
        trailer = self.retrieve_trailer()
        root = trailer.get_cos_dictionary(COSName.ROOT)
        if root is None:
            raise PDFParseError("Missing root object specification in trailer.")
        self._initial_parse_done = True

    def initial_parse(self) -> None:
        """Public mirror for the upstream private ``initialParse`` (Java
        line 48). Kept callable so external ports compile."""
        self._initial_parse()

    def parse(self) -> FDFDocument:
        """Parse the FDF source and return an :class:`FDFDocument`.

        Mirrors upstream ``FDFParser.parse`` (Java line 66).
        """
        from pypdfbox.pdmodel.fdf.fdf_document import FDFDocument  # noqa: PLC0415

        exception_occurred = True
        try:
            # pypdfbox's ``parse_fdf_header`` returns the parsed version
            # number (float) — ``0`` or below would mean a failed parse,
            # matching upstream's boolean-returning shape.
            try:
                version = self.parse_fdf_header()
            except PDFParseError as exc:
                if "malformed %FDF- version" not in exc.message:
                    raise PDFParseError(
                        "Error: Header doesn't contain versioninfo"
                    ) from exc
                version = 1.7
            if not version:
                raise PDFParseError("Error: Header doesn't contain versioninfo")
            if self._document is None:
                from .pdf_parser import PDFParser  # noqa: PLC0415

                self._src.seek(0)
                parser = PDFParser(self._src)
                parser.parse_header = lambda: version  # type: ignore[method-assign]
                self._document = parser.parse()
            else:
                self._document.set_version(version)
            self._initial_parse()
            exception_occurred = False
            return FDFDocument(self._document, self._src)
        finally:
            if exception_occurred and self.document is not None:
                close_quietly(self.document)
                self._document = None  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Header detection — delegates to COSParser's PDF-header method when
    # the FDF-specific one isn't available.
    # ------------------------------------------------------------------

    def parse_fdf_header(self) -> bool:
        """Read and validate the FDF version header.

        Mirrors upstream ``COSParser.parseFDFHeader``. If the underlying
        parser only exposes ``parse_pdf_header`` we fall back to that —
        an FDF header has the same shape as a PDF header.
        """
        parse_fdf = getattr(super(), "parse_fdf_header", None)
        if callable(parse_fdf):
            return parse_fdf()
        return self.parse_pdf_header()
