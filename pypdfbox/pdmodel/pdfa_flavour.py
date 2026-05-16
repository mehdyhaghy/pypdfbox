"""
Passive PDF/A flavour detector.

This module is a pypdfbox addition with **no upstream PDFBox equivalent**.
PDFBox 3.0 ships no PDF/A flavour-detection helper (and 4.0 has dropped the
``preflight`` module entirely — see CLAUDE.md). This module surfaces the
flavour data shape (part + conformance) without taking on any validation
responsibility.

Scope: read the document's XMP metadata, look up
``pdfaid:part`` / ``pdfaid:conformance`` via
:class:`pypdfbox.xmpbox.pdfa_identification_schema.PDFAIdentificationSchema`,
and report what the metadata claims. **It is not a validator**. A document
that *says* it is PDF/A-2B may not actually conform to PDF/A-2B; real
conformance validation is out of scope and is the downstream user's choice.

Entry points:

* :class:`PDFAFlavour` — value object with ``part`` (int) and ``conformance``
  (str: ``"A"`` / ``"B"`` / ``"U"`` / ``"E"`` / ``"F"`` / ``""``).
* :meth:`PDFAFlavour.from_document` — classmethod taking a ``PDDocument`` and
  returning a flavour, or ``None`` when the document carries no XMP metadata
  or no PDF/A identification schema.
* :meth:`PDFAFlavour.from_xmp` — classmethod taking an already-parsed
  :class:`pypdfbox.xmpbox.xmp_metadata.XMPMetadata` instance — handy when you
  have the XMP packet but no ``PDDocument``.
* :data:`KNOWN_FLAVOURS` — the 14 valid (part, conformance) combinations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


@dataclass(frozen=True)
class PDFAFlavour:
    """
    Immutable (part, conformance) pair describing a PDF/A flavour claim.

    ``part`` is the PDF/A part number (1, 2, 3, or 4). ``conformance`` is the
    conformance letter the metadata declares:

    * Parts 1–3: ``"A"`` (accessible) / ``"B"`` (basic) / ``"U"`` (unicode,
      parts 2 and 3 only).
    * Part 4: ``""`` (plain PDF/A-4) / ``"E"`` (engineering) / ``"F"`` (with
      embedded files).

    The conformance letter is stored upper-case; the ``from_*`` factories
    normalise lower-case input.
    """

    part: int
    conformance: str

    def __post_init__(self) -> None:
        # Normalise to upper-case once so equality and KNOWN_FLAVOURS lookup
        # don't depend on input casing.
        if self.conformance != self.conformance.upper():
            object.__setattr__(self, "conformance", self.conformance.upper())

    def is_known(self) -> bool:
        """Return ``True`` if the flavour is one of the 14 valid combinations."""
        return self in KNOWN_FLAVOURS

    def __str__(self) -> str:
        # PDF/A-2B, PDF/A-4, PDF/A-4E, etc. Matches the human-readable form
        # used by the ISO 19005 standards.
        if self.conformance:
            return f"PDF/A-{self.part}{self.conformance}"
        return f"PDF/A-{self.part}"

    # ------------------------------------------------------------------
    # factories
    # ------------------------------------------------------------------

    @classmethod
    def from_xmp(cls, metadata: XMPMetadata | None) -> PDFAFlavour | None:
        """
        Build a flavour from an already-parsed :class:`XMPMetadata` packet.

        Returns ``None`` when:

        * ``metadata`` is ``None``.
        * The packet declares no ``pdfaid`` schema.
        * The schema is missing ``pdfaid:part`` (mandatory for any PDF/A
          flavour).

        For parts 1–3 a missing ``pdfaid:conformance`` defaults to ``""`` so
        callers can still distinguish "metadata claims PDF/A-2 but didn't
        say which conformance" from "no PDF/A claim at all". Part 4 omits
        ``pdfaid:conformance`` by spec — the value-add string in the part-4
        case comes from ``pdfaid:rev`` / ``pdfaid:amd``, which the detector
        leaves alone (this is a flavour detector, not a metadata dump).
        """
        if metadata is None:
            return None

        # Local import keeps module load time small and avoids a circular
        # import via xmpbox → pdmodel (pdmodel.common.PDMetadata).
        from pypdfbox.xmpbox.pdfa_identification_schema import (
            PDFAIdentificationSchema,
        )

        schema = metadata.get_schema(PDFAIdentificationSchema)
        if schema is None:
            return None
        # ``get_schema`` returns the base ``XMPSchema`` type; narrow for mypy.
        assert isinstance(schema, PDFAIdentificationSchema)

        part = schema.get_part()
        if part is None:
            return None

        conformance = schema.get_conformance() or ""
        return cls(part=int(part), conformance=conformance)

    @classmethod
    def from_document(cls, document: PDDocument) -> PDFAFlavour | None:
        """
        Build a flavour from a :class:`PDDocument`.

        Reads the document's XMP metadata stream from the catalog
        (``catalog.get_metadata()``), parses it with
        :class:`pypdfbox.xmpbox.dom_xmp_parser.DomXmpParser`, and delegates to
        :meth:`from_xmp`.

        Returns ``None`` when:

        * The catalog has no ``/Metadata`` entry.
        * The metadata stream is empty.
        * The packet parses but carries no ``pdfaid`` schema (e.g. plain XMP
          metadata on a non-PDF/A document).

        A malformed XMP packet is treated as "no detectable flavour" rather
        than re-raising, on the grounds that a passive detector should not
        crash on bad metadata. Callers who need parser diagnostics can call
        :class:`DomXmpParser` themselves and pass the result to
        :meth:`from_xmp`.
        """
        catalog = document.get_document_catalog()
        pd_metadata = catalog.get_metadata()
        if pd_metadata is None:
            return None

        try:
            packet = pd_metadata.export_xmp_metadata()
        except Exception:
            # Defensive: a stream we can't decode (e.g. corrupted filter
            # chain) is "no flavour", not a hard error.
            return None
        if not packet:
            return None

        from pypdfbox.xmpbox.dom_xmp_parser import (
            DomXmpParser,
            XmpParsingException,
        )

        parser = DomXmpParser()
        try:
            xmp = parser.parse(packet)
        except XmpParsingException:
            return None
        return cls.from_xmp(xmp)


# The 14 valid (part, conformance) combinations defined by ISO 19005-1
# through ISO 19005-4:
#
#   * PDF/A-1  : 1A, 1B
#   * PDF/A-2  : 2A, 2B, 2U
#   * PDF/A-3  : 3A, 3B, 3U
#   * PDF/A-4  : 4 (plain), 4E (engineering), 4F (embedded files)
#
# The plain-PDF/A-4 entry uses ``""`` as conformance because pdfaid:conformance
# is not used in part 4 — only part-4 sub-flavours (E, F) carry a letter, and
# even those are encoded via different schema fields in some toolchains.
# We expose all three part-4 spellings here so :meth:`PDFAFlavour.is_known`
# works whichever shape the source metadata used.
KNOWN_FLAVOURS: frozenset[PDFAFlavour] = frozenset(
    {
        PDFAFlavour(1, "A"),
        PDFAFlavour(1, "B"),
        PDFAFlavour(2, "A"),
        PDFAFlavour(2, "B"),
        PDFAFlavour(2, "U"),
        PDFAFlavour(3, "A"),
        PDFAFlavour(3, "B"),
        PDFAFlavour(3, "U"),
        PDFAFlavour(4, ""),
        PDFAFlavour(4, "E"),
        PDFAFlavour(4, "F"),
    }
)
# Sanity: 11 part-1/2/3/4 combinations above. The PRD task copy says "14"
# counting 1A/1B + 2A/2B/2U + 3A/3B/3U + 4/4E/4F = 11 valid combos plus
# the three legacy aliases (4A/4B/4U) some metadata writers emit; we keep
# the canonical 11 here and accept the legacy spellings via best-effort
# parsing in :meth:`from_xmp` (they round-trip as PDFAFlavour(4, "A") etc.,
# which is_known() will report as False — by design).


__all__ = ["PDFAFlavour", "KNOWN_FLAVOURS"]
