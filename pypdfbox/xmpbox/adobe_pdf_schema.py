from __future__ import annotations

from typing import TYPE_CHECKING

from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class AdobePDFSchema(XMPSchema):
    """
    Representation of the Adobe PDF schema.

    Ported (subset, read+write path) from
    ``org.apache.xmpbox.schema.AdobePDFSchema`` (PDFBox 3.0). Per the
    ``@StructuredType`` annotation, the namespace is
    ``http://ns.adobe.com/pdf/1.3/`` with preferred prefix ``pdf``. Property
    local names match upstream ``public static final`` constants verbatim.

    Properties:

      * ``Keywords`` (Text) — keywords associated with the document.
      * ``PDFVersion`` (Text) — PDF spec version, e.g. ``"1.4"``.
      * ``Producer`` (Text) — name of the tool that produced the PDF.
    """

    NAMESPACE = "http://ns.adobe.com/pdf/1.3/"
    PREFERRED_PREFIX = "pdf"

    KEYWORDS = "Keywords"
    PDF_VERSION = "PDFVersion"
    PRODUCER = "Producer"

    def __init__(self, metadata: XMPMetadata, own_prefix: str | None = None) -> None:
        super().__init__(metadata, self.NAMESPACE, own_prefix or self.PREFERRED_PREFIX)

    # --- Keywords (Text) ---------------------------------------------

    def set_keywords(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.KEYWORDS)
            return
        self.set_text_property_value(self.KEYWORDS, value)

    def get_keywords(self) -> str | None:
        return self.get_unqualified_text_property_value(self.KEYWORDS)

    # --- PDFVersion (Text) -------------------------------------------

    def set_pdf_version(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.PDF_VERSION)
            return
        self.set_text_property_value(self.PDF_VERSION, value)

    def get_pdf_version(self) -> str | None:
        return self.get_unqualified_text_property_value(self.PDF_VERSION)

    # --- Producer (Text) ---------------------------------------------

    def set_producer(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.PRODUCER)
            return
        self.set_text_property_value(self.PRODUCER, value)

    def get_producer(self) -> str | None:
        return self.get_unqualified_text_property_value(self.PRODUCER)
