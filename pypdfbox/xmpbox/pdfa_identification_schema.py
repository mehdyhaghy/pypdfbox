from __future__ import annotations

from typing import TYPE_CHECKING

from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class BadFieldValueException(ValueError):
    """Mirror of upstream ``org.apache.xmpbox.type.BadFieldValueException``.

    Raised when an XMP property is set to a value outside its
    schema-defined value space. Subclasses :class:`ValueError` so callers
    that aren't aware of the upstream class can still catch it
    idiomatically.
    """


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
      * Part 4 uses ``pdfaid:part = 4`` and ``pdfaid:conformance`` is
        ``e`` / ``f`` (or omitted on the legacy PDF/A-2/3 path);
        ``pdfaid:amd`` / ``pdfaid:rev`` carry amendment and revision.
        ``pdfaid:corr`` is a pypdfbox enrichment for correction year strings
        (no upstream typed accessor in 3.0.x).
    """

    NAMESPACE = "http://www.aiim.org/pdfa/ns/id/"
    PREFERRED_PREFIX = "pdfaid"

    # Local-name constants — names match upstream ``public static final`` fields.
    PART = "part"
    AMD = "amd"
    CONFORMANCE = "conformance"
    REV = "rev"
    CORR = "corr"

    # Upstream PDFBOX-6088 — accept legacy A/B/U plus PDF/A-4 e/f.
    _VALID_CONFORMANCE: frozenset[str] = frozenset({"A", "B", "U", "e", "f"})

    def __init__(self, metadata: XMPMetadata, own_prefix: str | None = None) -> None:
        super().__init__(metadata, self.NAMESPACE, own_prefix or self.PREFERRED_PREFIX)

    # --- part (Integer) ----------------------------------------------

    def get_part(self) -> int | None:
        """Mirror of upstream ``getPart()`` — returns the PDF/A part as an
        ``int``, or ``None`` when absent / unparseable."""
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
        """Mirror of upstream ``setPart(Integer)`` — store the PDF/A part as
        a numeric int. The parser path normalises strings on read."""
        self._properties[self.PART] = int(value)

    def set_part_value_with_int(self, value: int) -> None:
        """Mirror of upstream ``setPartValueWithInt(int)`` — alias of
        :meth:`set_part`. Kept for upstream API parity."""
        self.set_part(int(value))

    def set_part_value_with_string(self, value: str) -> None:
        """Mirror of upstream ``setPartValueWithString(String)`` — store the
        part from a numeric string. Raises ``ValueError`` (upstream raises
        ``IllegalArgumentException``) when the string is not a valid
        integer."""
        # ``int(value)`` raises ValueError for "ojoj"-style garbage, which
        # mirrors upstream's IllegalArgumentException semantics.
        self._properties[self.PART] = int(value)

    # --- conformance (single character) ------------------------------

    def get_conformance(self) -> str | None:
        """Mirror of upstream ``getConformance()`` — returns the conformance
        level (``A``/``B``/``U``/``e``/``f``), or ``None`` when absent."""
        return self.get_unqualified_text_property_value(self.CONFORMANCE)

    def set_conformance(self, value: str | None) -> None:
        """Mirror of upstream ``setConformance(String)``. Pass ``None`` to
        remove the entry. Raises :class:`BadFieldValueException` for values
        outside ``{A, B, U, e, f}`` (matches upstream PDFBox 3.0)."""
        if value is None:
            self.remove_property(self.CONFORMANCE)
            return
        if value not in self._VALID_CONFORMANCE:
            raise BadFieldValueException(
                f"The value '{value}' isn't a valid PDF/A conformance level "
                f"(must be A, B, U, e or f)"
            )
        self.set_text_property_value(self.CONFORMANCE, value)

    # --- amendment / revision / correction ---------------------------

    def get_amendment(self) -> str | None:
        """Mirror of upstream ``getAmendment()``."""
        return self.get_unqualified_text_property_value(self.AMD)

    def get_amd(self) -> str | None:
        """Mirror of upstream ``getAmd()`` — alias of
        :meth:`get_amendment`. Upstream exposes both names verbatim."""
        return self.get_amendment()

    def set_amendment(self, value: str | None) -> None:
        """Set the PDF/A amendment identifier. Pass ``None`` to remove."""
        if value is None:
            self.remove_property(self.AMD)
            return
        self.set_text_property_value(self.AMD, value)

    def set_amd(self, value: str | None) -> None:
        """Mirror of upstream ``setAmd(String)`` — alias of
        :meth:`set_amendment`."""
        self.set_amendment(value)

    def get_revision(self) -> str | None:
        """Return the PDF/A revision year as a string. Upstream typed it as
        ``Integer`` post-PDFBOX-6088, but pypdfbox returns the raw string for
        round-trip parity with parsed XMP packets — callers needing a
        numeric value can use :meth:`get_rev`."""
        # Stringify ints so the accessor works after :meth:`set_rev` (which
        # stores a numeric int per upstream IntegerType semantics).
        raw = self._properties.get(self.REV)
        if isinstance(raw, int) and not isinstance(raw, bool):
            return str(raw)
        return self.get_unqualified_text_property_value(self.REV)

    def get_rev(self) -> int | None:
        """Mirror of upstream ``getRev()`` (post-PDFBOX-6088) — returns the
        revision as a numeric ``int`` (e.g. ``2020``), or ``None`` when
        absent / unparseable."""
        raw = self._properties.get(self.REV)
        if raw is None:
            return None
        if isinstance(raw, int) and not isinstance(raw, bool):
            return raw
        text = self.get_unqualified_text_property_value(self.REV)
        if text is None:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    def set_revision(self, value: str | None) -> None:
        """Set the PDF/A revision year as a string. Pass ``None`` to
        remove."""
        if value is None:
            self.remove_property(self.REV)
            return
        self.set_text_property_value(self.REV, value)

    def set_rev(self, value: int) -> None:
        """Mirror of upstream ``setRev(Integer)`` — store the revision year
        as a numeric ``int``."""
        self._properties[self.REV] = int(value)

    def set_rev_value_with_int(self, value: int) -> None:
        """Mirror of upstream ``setRevValueWithInt(int)`` — alias of
        :meth:`set_rev`."""
        self.set_rev(int(value))

    def set_rev_value_with_string(self, value: str) -> None:
        """Mirror of upstream ``setRevValueWithString(String)``. Raises
        ``ValueError`` when the string is not a valid integer."""
        self._properties[self.REV] = int(value)

    def get_correction(self) -> str | None:
        """pypdfbox enrichment — return the correction year (``corr``).

        No upstream typed accessor exists in PDFBox 3.0.x; this is added
        for forward compatibility with PDF/A 4 metadata."""
        return self.get_unqualified_text_property_value(self.CORR)

    def get_corr(self) -> str | None:
        """Alias of :meth:`get_correction` mirroring the field-name shape
        of :meth:`get_amd`."""
        return self.get_correction()

    def set_correction(self, value: str | None) -> None:
        """Set the correction year. Pass ``None`` to remove."""
        if value is None:
            self.remove_property(self.CORR)
            return
        self.set_text_property_value(self.CORR, value)

    def set_corr(self, value: str | None) -> None:
        """Alias of :meth:`set_correction`."""
        self.set_correction(value)
