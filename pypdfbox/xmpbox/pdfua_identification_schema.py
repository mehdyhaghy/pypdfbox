from __future__ import annotations

from typing import TYPE_CHECKING

from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class PDFUAIdentificationSchema(XMPSchema):
    """
    Representation of the PDF/UA Identification XMP schema.

    Mirrors the shape of :class:`PDFAIdentificationSchema` for ISO 14289 (PDF/UA).
    Apache PDFBox 3.0 does not ship a dedicated ``PDFUAIdentificationSchema``
    class — the closest upstream artefact is ad-hoc XMP packet authoring in
    Preflight (which 4.0 dropped). This pypdfbox class fills that gap so callers
    can read/write the ``pdfuaid`` block without hand-rolling XMP.

    PDF/UA-1 (ISO 14289-1) requires::

        pdfuaid:part = 1

    Optional companion properties:

      * ``pdfuaid:conformance`` — single-letter conformance ("Acc" is the
        conventional value emitted by some toolchains; the spec is silent on
        the exact set of letters).
      * ``pdfuaid:rev`` — revision year string (e.g. ``"2014"``).
      * ``pdfuaid:amd`` — amendment identifier string.

    This is a passive schema: it stores the metadata claim only. PDF/UA
    *validation* is explicitly out of scope (see CLAUDE.md — defer to external
    veraPDF / PAC for any conformance checking).
    """

    NAMESPACE = "http://www.aiim.org/pdfua/ns/id/"
    PREFERRED_PREFIX = "pdfuaid"

    # Local-name constants — kept as lower-case to match the casing used in
    # real-world PDF/UA XMP packets and parallel the ``PDFAIdentificationSchema``
    # constant style.
    PART = "part"
    CONFORMANCE = "conformance"
    REV = "rev"
    AMD = "amd"

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
        # Store as int so round-trips preserve numeric type. The parser path
        # (string from XML attribute) is normalised in ``get_part``.
        self._properties[self.PART] = int(value)

    # --- conformance (text) -------------------------------------------

    def get_conformance(self) -> str | None:
        return self.get_unqualified_text_property_value(self.CONFORMANCE)

    def set_conformance(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.CONFORMANCE)
            return
        self.set_text_property_value(self.CONFORMANCE, value)

    # --- revision -----------------------------------------------------

    def get_revision(self) -> str | None:
        return self.get_unqualified_text_property_value(self.REV)

    def set_revision(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.REV)
            return
        self.set_text_property_value(self.REV, value)

    # --- amendment ----------------------------------------------------

    def get_amendment(self) -> str | None:
        return self.get_unqualified_text_property_value(self.AMD)

    def set_amendment(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.AMD)
            return
        self.set_text_property_value(self.AMD, value)
