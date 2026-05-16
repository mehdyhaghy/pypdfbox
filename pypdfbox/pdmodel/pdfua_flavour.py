"""
Passive PDF/UA flavour detector.

This module is a pypdfbox addition with **no upstream PDFBox equivalent**.
PDFBox 3.0 ships no PDF/UA flavour-detection helper, and 4.0 dropped the
``preflight`` module entirely (see CLAUDE.md). This module surfaces the
flavour data shape (``part`` + ``rev``) without taking on any validation
responsibility.

Scope: read the document's XMP metadata, look up
``pdfuaid:part`` / ``pdfuaid:rev`` via
:class:`pypdfbox.xmpbox.pdfua_identification_schema.PDFUAIdentificationSchema`,
and report what the metadata claims. **It is not a validator**. A document
that *says* it is PDF/UA-1 may not actually conform to ISO 14289-1; real
conformance validation is out of scope and is the downstream user's choice.

Entry points:

* :class:`PDFUAFlavour` — value object with ``part`` (int) and ``rev``
  (str | None).
* :meth:`PDFUAFlavour.from_document` — classmethod taking a ``PDDocument``
  and returning a flavour, or ``None`` when the document carries no XMP
  metadata or no PDF/UA identification schema.
* :meth:`PDFUAFlavour.from_xmp` — classmethod taking an already-parsed
  :class:`pypdfbox.xmpbox.xmp_metadata.XMPMetadata` instance — handy when
  you have the XMP packet but no ``PDDocument``.
* :data:`KNOWN_PARTS` — the set of PDF/UA part numbers defined by ISO
  14289 (currently ``{1, 2}`` — Part 1 published 2014, Part 2 published
  2024).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.xmpbox.xmp_metadata import XMPMetadata


@dataclass(frozen=True)
class PDFUAFlavour:
    """
    Immutable (part, rev) pair describing a PDF/UA flavour claim.

    ``part`` is the PDF/UA part number (1 or 2 today). ``rev`` is the
    revision year the metadata declares (e.g. ``"2014"`` for ISO 14289-1),
    or ``None`` when ``pdfuaid:rev`` is absent from the packet — which is
    the common case, since the spec does not require ``rev``.
    """

    part: int
    rev: str | None = None

    def is_known(self) -> bool:
        """Return ``True`` if ``part`` is a defined PDF/UA part number."""
        return self.part in KNOWN_PARTS

    def __str__(self) -> str:
        # PDF/UA-1, PDF/UA-2 — matches the human-readable form used by the
        # ISO 14289 standards.
        if self.rev:
            return f"PDF/UA-{self.part} ({self.rev})"
        return f"PDF/UA-{self.part}"

    # ------------------------------------------------------------------
    # factories
    # ------------------------------------------------------------------

    @classmethod
    def from_xmp(cls, metadata: XMPMetadata | None) -> PDFUAFlavour | None:
        """
        Build a flavour from an already-parsed :class:`XMPMetadata` packet.

        Returns ``None`` when:

        * ``metadata`` is ``None``.
        * The packet declares no ``pdfuaid`` schema.
        * The schema is missing ``pdfuaid:part`` (mandatory for any PDF/UA
          flavour).
        """
        if metadata is None:
            return None

        # Local import keeps module load time small and avoids a circular
        # import via xmpbox -> pdmodel (pdmodel.common.PDMetadata).
        from pypdfbox.xmpbox.pdfua_identification_schema import (
            PDFUAIdentificationSchema,
        )

        schema = metadata.get_schema(PDFUAIdentificationSchema)
        if schema is None:
            return None
        # ``get_schema`` returns the base ``XMPSchema`` type; narrow.
        assert isinstance(schema, PDFUAIdentificationSchema)

        part = schema.get_part()
        if part is None:
            return None

        rev = schema.get_revision()
        return cls(part=int(part), rev=rev)

    @classmethod
    def from_document(cls, document: PDDocument) -> PDFUAFlavour | None:
        """
        Build a flavour from a :class:`PDDocument`.

        Reads the document's XMP metadata stream from the catalog
        (``catalog.get_metadata()``), parses it with
        :class:`pypdfbox.xmpbox.dom_xmp_parser.DomXmpParser`, and delegates
        to :meth:`from_xmp`.

        Returns ``None`` when:

        * The catalog has no ``/Metadata`` entry.
        * The metadata stream is empty.
        * The packet parses but carries no ``pdfuaid`` schema (e.g. plain
          XMP metadata on a non-PDF/UA document).

        A malformed XMP packet is treated as "no detectable flavour" rather
        than re-raising — a passive detector should never crash on bad
        metadata.
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


# Defined PDF/UA part numbers per ISO 14289:
#
#   * Part 1 (ISO 14289-1, published 2014) — applies to PDF 1.7.
#   * Part 2 (ISO 14289-2, published 2024) — applies to PDF 2.0.
#
# Future parts will extend this set; ``is_known`` consumers should treat the
# absence of an entry as "claim is outside the standard" rather than as a
# hard validation failure.
KNOWN_PARTS: frozenset[int] = frozenset({1, 2})


__all__ = ["KNOWN_PARTS", "PDFUAFlavour"]
