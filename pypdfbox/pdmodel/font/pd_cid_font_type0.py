from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.fontbox.cff.cff_font import CFFFont

from .pd_cid_font import PDCIDFont

if TYPE_CHECKING:
    from .pd_type0_font import PDType0Font

_LOG = logging.getLogger(__name__)

_CID_FONT_TYPE0C: str = "CIDFontType0C"
_OPEN_TYPE: str = "OpenType"


class PDCIDFontType0(PDCIDFont):
    """CIDFontType0 — CFF-based CIDFont. Mirrors PDFBox ``PDCIDFontType0``.

    The descendant of a composite ``PDType0Font`` whose embedded font
    program is a Compact Font Format (CFF) stream marked
    ``/Subtype /CIDFontType0C`` (or, less commonly, ``/OpenType`` with a
    CFF table) on the descriptor's ``/FontFile3``.

    Glyph metric / outline access goes through the same
    :class:`CFFFont` primitive as :class:`PDType1CFont`, but indexed by
    CID rather than by glyph name. CID-keyed CFF fonts use a charset
    that maps CIDs directly into the CharStrings INDEX — fontTools
    surfaces CharString entries keyed by ``"cid12345"`` zero-padded
    names. We reuse :class:`CFFFont` for parsing and width extraction
    and translate ``cid -> "cidNNNNN"`` ourselves.
    """

    SUB_TYPE = "CIDFontType0"

    def __init__(
        self,
        font_dict: COSDictionary | None = None,
        parent_type0_font: PDType0Font | None = None,
    ) -> None:
        super().__init__(font_dict, parent_type0_font)
        # Lazily-loaded embedded CFF program. ``None`` = not yet
        # attempted; ``False`` = tried, no /FontFile3 or parse failed.
        self._cff: CFFFont | None | bool = None

    def get_subtype(self) -> str | None:
        return self.SUB_TYPE

    # ---------- code -> CID ----------

    def code_to_cid(self, code: int) -> int:  # type: ignore[override]
        """For CID-keyed CFF fonts the "code" arriving at this layer is
        already the CID (the parent :class:`PDType0Font`'s ``/Encoding``
        CMap performed ``code -> CID`` upstream). Identity mapping here
        mirrors upstream ``PDCIDFontType0.codeToCID``.
        """
        return int(code)

    # ---------- /FontFile3 + /Subtype /CIDFontType0C wiring ----------

    def is_embedded(self) -> bool:  # type: ignore[override]
        """``True`` when the descriptor carries an embedded font program.

        Returns ``True`` when any of ``/FontFile``, ``/FontFile2``, or
        ``/FontFile3`` is present — matching :meth:`PDCIDFont.is_embedded`
        for descriptor-level liveness — *or* when a ``/FontFile3`` with
        ``/Subtype /CIDFontType0C`` (or ``/OpenType``) is present, which
        is the canonical embedded form for a CIDFontType0 per
        PDF 32000-1 §9.6.2.2 and §9.7.4.2. The combined check keeps
        legacy descriptor inputs working while still surfacing the
        CID-keyed CFF case explicitly through :meth:`is_cff_embedded`.
        """
        if super().is_embedded():
            return True
        return self.is_cff_embedded()

    def is_cff_embedded(self) -> bool:
        """``True`` when the descriptor carries a ``/FontFile3`` whose
        own ``/Subtype`` is ``/CIDFontType0C`` (or ``/OpenType``).

        This is the strict upstream ``PDCIDFontType0.isEmbedded`` form —
        a CFF-program-backed CIDFontType0 program lives only in
        ``/FontFile3`` with the correct subtype. Exposed separately so
        callers that need the strict check (renderer / metrics paths)
        can ask for it without losing the legacy descriptor liveness
        signal carried by :meth:`is_embedded`.
        """
        descriptor = self.get_font_descriptor()
        if descriptor is None:
            return False
        font_file3 = descriptor.get_font_file3()
        if font_file3 is None:
            return False
        subtype = font_file3.get_cos_object().get_name(COSName.SUBTYPE)  # type: ignore[attr-defined]
        return subtype in (_CID_FONT_TYPE0C, _OPEN_TYPE)

    def get_cff_font(self) -> CFFFont | None:
        """Return the parsed CFF program for this font's
        ``/FontFile3`` stream, or ``None`` if the font is not embedded
        or the stream cannot be parsed. Result is cached on the
        instance.
        """
        if self._cff is not None:
            return self._cff if isinstance(self._cff, CFFFont) else None

        descriptor = self.get_font_descriptor()
        if descriptor is None:
            self._cff = False
            return None
        font_file3 = descriptor.get_font_file3()
        if font_file3 is None:
            self._cff = False
            return None
        try:
            raw = font_file3.to_byte_array()
            self._cff = CFFFont.from_bytes(raw)
        except Exception:  # noqa: BLE001
            _LOG.exception("failed to parse /FontFile3 for %s", self.get_name())
            self._cff = False
            return None
        return self._cff

    def set_cff_font(self, font: CFFFont | None) -> None:
        """Inject a pre-parsed :class:`CFFFont`. Mirrors the equivalent
        injector on :class:`PDType1CFont` — lets callers that already
        have the font program in hand bypass ``/FontFile3`` parsing,
        and lets tests skip the byte-level fixture round-trip.
        """
        self._cff = font if font is not None else False

    # ---------- glyph widths ----------

    def _cff_glyph_name(self, cid: int) -> str:
        """fontTools surfaces CID-keyed CFF charstrings under the name
        ``"cidNNNNN"`` (5-digit zero-padded). The ``.notdef`` glyph is
        always CID 0.
        """
        if cid == 0:
            return ".notdef"
        return f"cid{cid:05d}"

    def _cff_program_width(self, cid: int) -> float | None:
        """Width contributed by the embedded CFF program for ``cid``.
        Returns ``None`` when there is no program, the CID is unmapped,
        or the program reports a zero advance. Width is normalized to
        1/1000 em (the PDF width unit) regardless of the program's
        native units-per-em.
        """
        program = self.get_cff_font()
        if program is None:
            return None
        name = self._cff_glyph_name(cid)
        if not program.has_glyph(name):
            return None
        units_per_em = program.units_per_em
        if units_per_em <= 0:
            return None
        advance = program.get_width(name)
        if advance <= 0.0:
            return None
        return advance * 1000.0 / units_per_em

    def get_glyph_width(self, cid: int) -> float:  # type: ignore[override]
        """Width of ``cid`` in 1/1000 em.

        Resolution order, mirroring upstream ``PDCIDFontType0``:

        1. ``/W`` (per-CID widths, parsed by :class:`PDCIDFont`).
        2. Embedded CFF program width when available.
        3. ``/DW`` default (defaults to 1000 per spec).
        """
        widths = self.get_widths()
        explicit = widths.get(cid)
        if explicit is not None:
            return explicit
        program_width = self._cff_program_width(cid)
        if program_width is not None:
            return program_width
        return self.get_default_width()

    # ---------- glyph paths ----------

    def get_glyph_path(self, cid: int) -> list[tuple]:
        """CFF outline for ``cid``, in font units. Returns ``[]`` when
        the font has no embedded CFF program or the CID is unmapped.

        For CID-keyed CFF the charset maps CIDs directly into the
        CharStrings INDEX; fontTools exposes those entries under
        ``"cidNNNNN"`` keys so we translate the CID accordingly. If
        the running ``CFFFont`` build doesn't expose CID-keyed glyph
        names this path returns ``[]`` and rendering is expected to
        fall back to the .notdef box, matching upstream behaviour for
        unembedded CIDFontType0 instances.
        """
        program = self.get_cff_font()
        if program is None:
            return []
        name = self._cff_glyph_name(cid)
        if not program.has_glyph(name):
            return []
        return program.get_path(name)


__all__ = ["PDCIDFontType0"]
