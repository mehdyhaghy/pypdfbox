from __future__ import annotations

from typing import TYPE_CHECKING

from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class PDFAIdentificationSchema(XMPSchema):
    """
    Representation of the PDF/A Identification XMP schema.

    Ported (subset, read+write path) from
    ``org.apache.xmpbox.schema.PDFAIdentificationSchema`` (PDFBox 3.0). The
    schema declares which revision of the PDF/A standard a document conforms
    to. Property local names match upstream constants verbatim.

    PDF/A versions:

      * Parts 1, 2, 3 use ``pdfaid:part`` (1/2/3) plus ``pdfaid:conformance``
        (``A``/``B``/``U``).
      * Part 4 uses ``pdfaid:part = 4`` and omits ``pdfaid:conformance``;
        ``pdfaid:amd`` / ``pdfaid:rev`` / ``pdfaid:corr`` carry amendment,
        revision, and correction year strings.
    """

    NAMESPACE = "http://www.aiim.org/pdfa/ns/id/"
    PREFERRED_PREFIX = "pdfaid"

    # Local-name constants — names match upstream ``public static final`` fields.
    PART = "part"
    AMD = "amd"
    CONFORMANCE = "conformance"
    REV = "rev"
    CORR = "corr"

    def __init__(self, metadata: XMPMetadata, own_prefix: str | None = None) -> None:
        super().__init__(metadata, self.NAMESPACE, own_prefix or self.PREFERRED_PREFIX)

    # --- part (Integer) ----------------------------------------------

    def get_part(self) -> int | None:
        raw = self._properties.get(self.PART)
        if raw is None:
            return None
        if isinstance(raw, int) and not isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            try:
                return int(raw)
            except ValueError:
                return None
        # Fall back through the standard text accessor for parsed-from-XML
        # values that may have landed in list/dict shape.
        text = self.get_unqualified_text_property_value(self.PART)
        if text is None:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    def set_part(self, value: int) -> None:
        # Upstream stores an IntegerType; we keep the int directly so that
        # round-trips preserve numeric type. The parser path (string from XML)
        # is normalised in ``get_part``.
        self._properties[self.PART] = int(value)

    # --- conformance (single character) ------------------------------

    def get_conformance(self) -> str | None:
        return self.get_unqualified_text_property_value(self.CONFORMANCE)

    def set_conformance(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.CONFORMANCE)
            return
        self.set_text_property_value(self.CONFORMANCE, value)

    # --- amendment / revision / correction (PDF/A 4 only) -----------

    def get_amendment(self) -> str | None:
        return self.get_unqualified_text_property_value(self.AMD)

    def set_amendment(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.AMD)
            return
        self.set_text_property_value(self.AMD, value)

    def get_revision(self) -> str | None:
        return self.get_unqualified_text_property_value(self.REV)

    def set_revision(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.REV)
            return
        self.set_text_property_value(self.REV, value)

    def get_correction(self) -> str | None:
        return self.get_unqualified_text_property_value(self.CORR)

    def set_correction(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.CORR)
            return
        self.set_text_property_value(self.CORR, value)
