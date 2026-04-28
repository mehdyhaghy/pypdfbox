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

    PDF/UA-2 (ISO 14289-2) requires::

        pdfuaid:part = 2
        pdfuaid:rev  = "2024"   # year of the standard

    Optional companion properties:

      * ``pdfuaid:conformance`` — single-letter conformance ("Acc" is the
        conventional value emitted by some toolchains; the spec is silent on
        the exact set of letters).
      * ``pdfuaid:rev`` — revision year string (e.g. ``"2014"`` for UA-1,
        ``"2024"`` for UA-2). Stored verbatim for round-trip parity.
      * ``pdfuaid:amd`` — amendment identifier string.
      * ``pdfuaid:corr`` — correction identifier string (PDF/UA-2 introduces
        formal corrigenda alongside amendments).

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
    CORR = "corr"

    # Part-number constants — pypdfbox enrichments. Upstream PDFBox 3.0 has no
    # PDFUAIdentificationSchema class, but ISO 14289 defines exactly two parts
    # at present (UA-1 and UA-2); surfacing them as named constants makes the
    # call sites self-documenting.
    PART_1 = 1
    PART_2 = 2

    def __init__(self, metadata: XMPMetadata, own_prefix: str | None = None) -> None:
        super().__init__(metadata, self.NAMESPACE, own_prefix or self.PREFERRED_PREFIX)

    # --- part (Integer) ----------------------------------------------

    def get_part(self) -> int | None:
        """Return the PDF/UA part as an ``int`` (1 for UA-1, 2 for UA-2),
        or ``None`` when absent / unparseable."""
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
        """Set the PDF/UA part. Use :attr:`PART_1` (ISO 14289-1) or
        :attr:`PART_2` (ISO 14289-2)."""
        # Store as int so round-trips preserve numeric type. The parser path
        # (string from XML attribute) is normalised in ``get_part``.
        self._properties[self.PART] = int(value)

    def set_part_value_with_int(self, value: int) -> None:
        """Parity alias of :meth:`set_part` mirroring the
        ``setPartValueWithInt`` shape used on :class:`PDFAIdentificationSchema`.
        """
        self.set_part(int(value))

    def set_part_value_with_string(self, value: str) -> None:
        """Parity alias of :meth:`set_part` accepting a numeric string. Raises
        ``ValueError`` for non-numeric input — mirrors the PDF/A schema's
        ``setPartValueWithString`` semantics."""
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
        """Return the revision year as a string. Stringifies a numeric int
        (stored via :meth:`set_rev`) so the accessor remains symmetric with
        parser-supplied string values."""
        raw = self._properties.get(self.REV)
        if isinstance(raw, int) and not isinstance(raw, bool):
            return str(raw)
        return self.get_unqualified_text_property_value(self.REV)

    def get_rev(self) -> str | None:
        """Alias of :meth:`get_revision`. PDF/UA's ``pdfuaid:rev`` is a year
        string per ISO 14289-2 (e.g. ``"2024"``); the upstream PDF/A schema
        types ``rev`` as ``Integer`` post-PDFBOX-6088, but PDF/UA spec text
        treats it as a string identifier so we keep the string shape."""
        return self.get_revision()

    def set_revision(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.REV)
            return
        self.set_text_property_value(self.REV, value)

    def set_rev(self, value: str | int | None) -> None:
        """Set the revision year. Accepts a string or int; ints are coerced to
        their decimal string form. Pass ``None`` to remove."""
        if value is None:
            self.remove_property(self.REV)
            return
        if isinstance(value, int) and not isinstance(value, bool):
            self.set_text_property_value(self.REV, str(value))
            return
        self.set_text_property_value(self.REV, str(value))

    # --- amendment ----------------------------------------------------

    def get_amendment(self) -> str | None:
        return self.get_unqualified_text_property_value(self.AMD)

    def get_amd(self) -> str | None:
        """Alias of :meth:`get_amendment` mirroring the field-name shape
        of :meth:`PDFAIdentificationSchema.get_amd`."""
        return self.get_amendment()

    def set_amendment(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.AMD)
            return
        self.set_text_property_value(self.AMD, value)

    def set_amd(self, value: str | None) -> None:
        """Alias of :meth:`set_amendment`."""
        self.set_amendment(value)

    # --- correction ---------------------------------------------------

    def get_correction(self) -> str | None:
        """Return the correction identifier (``pdfuaid:corr``). PDF/UA-2 (ISO
        14289-2) introduces formal corrigenda alongside amendments — kept as
        a free-form string for upstream-style passthrough."""
        return self.get_unqualified_text_property_value(self.CORR)

    def get_corr(self) -> str | None:
        """Alias of :meth:`get_correction`."""
        return self.get_correction()

    def set_correction(self, value: str | None) -> None:
        if value is None:
            self.remove_property(self.CORR)
            return
        self.set_text_property_value(self.CORR, value)

    def set_corr(self, value: str | None) -> None:
        """Alias of :meth:`set_correction`."""
        self.set_correction(value)
