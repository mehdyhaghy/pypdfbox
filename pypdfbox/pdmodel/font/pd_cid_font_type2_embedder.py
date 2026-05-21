"""CID-keyed TrueType embedder — builds :class:`PDCIDFontType2` graphs.

Mirrors ``org.apache.pdfbox.pdmodel.font.PDCIDFontType2Embedder`` (PDFBox
3.0, ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/
PDCIDFontType2Embedder.java`` lines 56-718).

Embeds a TrueType into a CIDFontType2 dictionary (the descendant of a
Type0 font). Handles:

* Building the ``/CIDSystemInfo`` (Adobe-Identity).
* Writing the ToUnicode CMap (delegates to :class:`ToUnicodeWriter`).
* Building ``/W`` (horizontal widths) and ``/W2`` (vertical metrics)
  arrays, plus the ``/CIDSet`` for PDF/A compliance.
* Setting ``/CIDToGIDMap`` (Identity or explicit stream for subsets).

The arrays are emitted using PDFBox's three-state encoder
(``FIRST`` / ``BRACKET`` / ``SERIAL``) which collapses runs of identical
widths into the ``c [w1 w2 ... wn]`` and ``c1 c2 w`` forms allowed by the
PDF spec.

**Library-first:** fontTools provides the metrics tables; we never
re-parse the TTF.
"""

from __future__ import annotations

import io
import logging
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.common import PDStream

from .to_unicode_writer import ToUnicodeWriter
from .true_type_embedder import TrueTypeEmbedder

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument

    from .pd_type0_font import PDType0Font

_LOG = logging.getLogger(__name__)


class _State(Enum):
    """Width-encoder state machine. Mirrors upstream ``enum State`` (Java line 453-456)."""

    FIRST = auto()
    BRACKET = auto()
    SERIAL = auto()


class PDCIDFontType2Embedder(TrueTypeEmbedder):
    """CID-keyed TTF embedder for :class:`PDType0Font` parents.

    Mirrors upstream Java line 56-718.
    """

    def __init__(
        self,
        document: PDDocument,
        dict_: COSDictionary,
        ttf: Any,
        embed_subset: bool,
        parent: PDType0Font,
        vertical: bool,
    ) -> None:
        # Mirror upstream constructor (Java line 76-101).
        super().__init__(document, dict_, ttf, embed_subset)
        self._document_ref: PDDocument = document
        self._dict: COSDictionary = dict_
        self._parent: PDType0Font = parent
        self._vertical: bool = vertical
        dict_.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type0"))
        dict_.set_name(COSName.BASE_FONT, self.font_descriptor.get_font_name() or "")
        dict_.set_item(
            COSName.ENCODING,
            COSName.get_pdf_name("Identity-V" if vertical else "Identity-H"),
        )
        self._cid_font: COSDictionary = self._create_cid_font()
        descendant_fonts = COSArray()
        descendant_fonts.add(self._cid_font)
        dict_.set_item(COSName.get_pdf_name("DescendantFonts"), descendant_fonts)
        if not embed_subset:
            self._build_to_unicode_cmap(None)

    # ---------- subclass hook ----------

    def build_subset(
        self,
        ttf_subset: io.BufferedIOBase,
        tag: str,
        gid_to_cid: dict[int, int],
    ) -> None:
        """Rebuild the embedded subset using the freshly subsetted TTF.

        Mirrors upstream ``buildSubset`` (Java line 107-127).
        """
        cid_to_gid: dict[int, int] = {}
        for new_gid, old_gid in gid_to_cid.items():
            cid_to_gid[old_gid] = new_gid
        self._build_to_unicode_cmap(gid_to_cid)
        if self._vertical:
            self._build_vertical_metrics_for_subset(cid_to_gid)
        self._build_font_file2(ttf_subset)
        self._add_name_tag(tag)
        self._build_widths_for_subset(cid_to_gid)
        self._build_cid_to_gid_map(cid_to_gid)
        self._build_cid_set(cid_to_gid)

    # ---------- builders ----------

    def create_cid_font(self) -> COSDictionary:
        """Public spelling of :meth:`_create_cid_font`.

        Mirrors upstream private ``createCIDFont`` (Java line 195-231).
        """
        return self._create_cid_font()

    def build_to_unicode_c_map(
        self, new_gid_to_old_cid: dict[int, int] | None
    ) -> None:
        """Public spelling of :meth:`_build_to_unicode_cmap`.

        Mirrors upstream private ``buildToUnicodeCMap`` (Java line 129-184).
        """
        self._build_to_unicode_cmap(new_gid_to_old_cid)

    def build_cid_to_gid_map(self, cid_to_gid: dict[int, int]) -> None:
        """Public spelling of :meth:`_build_cid_to_gid_map`.

        Mirrors upstream private ``buildCIDToGIDMap`` (Java line 274-295).
        """
        self._build_cid_to_gid_map(cid_to_gid)

    def build_cid_set(self, cid_to_gid: dict[int, int]) -> None:
        """Public spelling of :meth:`_build_cid_set`.

        Mirrors upstream private ``buildCIDSet`` (Java line 301-315).
        """
        self._build_cid_set(cid_to_gid)

    def build_widths(
        self, cid_to_gid_or_cos_dict: dict[int, int] | COSDictionary
    ) -> None:
        """Dispatch to the subset or full-embed builder.

        Mirrors the two overloaded upstream ``buildWidths`` signatures
        (Java line 320-350 and 439-451).
        """
        if isinstance(cid_to_gid_or_cos_dict, dict):
            self._build_widths_for_subset(cid_to_gid_or_cos_dict)
        else:
            self._build_widths_full(cid_to_gid_or_cos_dict)

    def build_vertical_metrics(
        self, cid_to_gid_or_cos_dict: dict[int, int] | COSDictionary
    ) -> None:
        """Dispatch to the subset or full-embed vertical-metrics builder.

        Mirrors upstream overloaded ``buildVerticalMetrics`` (Java line
        378-434 and 557-586).
        """
        if isinstance(cid_to_gid_or_cos_dict, dict):
            self._build_vertical_metrics_for_subset(cid_to_gid_or_cos_dict)
        else:
            self._build_vertical_metrics_full(cid_to_gid_or_cos_dict)

    def build_vertical_header(self, cid_font: COSDictionary) -> bool:
        """Populate ``/W2`` and ``/DW2`` defaults from the ``vhea`` table.

        Mirrors upstream private ``buildVerticalHeader`` (Java line
        352-376). Returns ``True`` if a ``vhea`` table is present.
        """
        try:
            self._ttf["vhea"]
        except KeyError:
            _LOG.warning(
                "Font to be subset is set to vertical, but has no 'vhea' table"
            )
            return False
        self._build_vertical_metrics_full(cid_font)
        return True

    def check_for_cid_gid_identity(self) -> None:
        """Validate that CID == GID for a non-subset OTF.

        Mirrors upstream private ``checkForCidGidIdentity`` (Java line
        233-262). When the embedded font is an OTF/CFF CID-keyed font we
        need cid == gid; otherwise the embedded ``/CIDToGIDMap Identity``
        contract is broken. fontTools doesn't always expose a charset
        accessor on subset OTFs, so we no-op if we can't read it.
        """
        try:
            cff_table = self._ttf["CFF "]
        except KeyError:
            return
        charset = getattr(getattr(cff_table, "cff", None), "charset", None)
        if charset is None:
            return
        try:
            glyph_count = int(self._ttf["maxp"].numGlyphs)
        except (KeyError, AttributeError):
            return
        for gid in range(glyph_count):
            try:
                cid = int(charset[gid])
            except (IndexError, TypeError, ValueError):
                return
            if cid != gid:
                raise RuntimeError(
                    f"CID and GID not identical: CID {cid} != GID {gid}, "
                    "use a ttf font instead"
                )

    def add_name_tag(self, tag: str) -> None:
        """Public spelling of :meth:`_add_name_tag`.

        Mirrors upstream private ``addNameTag`` (Java line 264-272).
        """
        self._add_name_tag(tag)

    def to_cid_system_info(
        self, registry: str, ordering: str, supplement: int
    ) -> COSDictionary:
        """Build a fresh ``/CIDSystemInfo`` dictionary.

        Mirrors upstream private ``toCIDSystemInfo`` (Java line 186-193).
        """
        return _to_cid_system_info(registry, ordering, supplement)

    def get_widths(self, widths: list[int]) -> COSArray:
        """Run the three-state width compressor.

        Mirrors upstream private ``getWidths(int[])`` (Java line 458-552).
        """
        try:
            head = self._ttf["head"]
            scaling = 1000.0 / float(getattr(head, "unitsPerEm", 1000) or 1000)
        except KeyError:
            scaling = 1.0
        return _encode_widths(widths, scaling)

    def get_vertical_metrics(self, values: list[int]) -> COSArray:
        """Run the three-state compressor on vertical-metrics triples.

        Mirrors upstream private ``getVerticalMetrics(int[])`` (Java line
        588-708). pypdfbox shares the width encoder for the simplified
        subset path; the full-fidelity vertical encoder isn't ported.
        """
        try:
            head = self._ttf["head"]
            scaling = 1000.0 / float(getattr(head, "unitsPerEm", 1000) or 1000)
        except KeyError:
            scaling = 1.0
        return _encode_widths(values, scaling)

    def _create_cid_font(self) -> COSDictionary:
        """Construct the descendant CIDFontType2 dictionary.

        Mirrors upstream ``createCIDFont`` (Java line 195-231).
        """
        cid_font = COSDictionary()
        cid_font.set_item(COSName.TYPE, COSName.FONT)
        cid_font.set_item(
            COSName.SUBTYPE, COSName.get_pdf_name("CIDFontType2")
        )
        cid_font.set_name(COSName.BASE_FONT, self.font_descriptor.get_font_name() or "")
        cid_font.set_item(
            COSName.get_pdf_name("CIDSystemInfo"),
            _to_cid_system_info("Adobe", "Identity", 0),
        )
        cid_font.set_item(COSName.FONT_DESC, self.font_descriptor.get_cos_object())
        # Bind ``self._cid_font`` BEFORE invoking the vertical-metrics
        # builder: the helper writes ``/DW2`` and ``/W2`` directly through
        # ``self._cid_font`` (mirroring upstream which mutates the bound
        # field, not a local). When this method runs from the constructor
        # the outer assignment at ``__init__`` has not happened yet, so
        # the vertical branch must see the freshly-built dict here.
        self._cid_font = cid_font
        self._build_widths_full(cid_font)
        if self._vertical:
            self._build_vertical_metrics_full(cid_font)
        cid_font.set_item(COSName.get_pdf_name("CIDToGIDMap"), COSName.IDENTITY)
        return cid_font

    def _build_to_unicode_cmap(
        self, new_gid_to_old_cid: dict[int, int] | None
    ) -> None:
        """Write the ToUnicode CMap stream.

        Mirrors upstream ``buildToUnicodeCMap`` (Java line 129-184).
        """
        writer = ToUnicodeWriter()
        has_surrogates = False
        cmap = self._get_unicode_cmap_reverse()
        try:
            max_glyphs = int(self._ttf["maxp"].numGlyphs)
        except KeyError:
            max_glyphs = 0
        for gid in range(1, max_glyphs + 1):
            if new_gid_to_old_cid is not None:
                if gid not in new_gid_to_old_cid:
                    continue
                cid = new_gid_to_old_cid[gid]
            else:
                cid = gid
            codes = cmap.get(cid)
            if codes:
                code_point = codes[0]
                if code_point > 0xFFFF:
                    has_surrogates = True
                writer.add(cid, chr(code_point))
        buf = io.BytesIO()
        writer.write_to(buf)
        buf.seek(0)
        stream = PDStream(self._document_ref, buf, COSName.FLATE_DECODE)
        if has_surrogates:
            try:
                if float(self._document_ref.get_version()) < 1.5:
                    self._document_ref.set_version(1.5)
            except (AttributeError, TypeError, ValueError):
                pass
        self._dict.set_item(COSName.get_pdf_name("ToUnicode"), stream.get_cos_object())

    def _build_cid_to_gid_map(self, cid_to_gid: dict[int, int]) -> None:
        """Write the ``/CIDToGIDMap`` stream.

        Mirrors upstream ``buildCIDToGIDMap`` (Java line 274-295).
        """
        cid_max = max(cid_to_gid)
        buffer = bytearray(cid_max * 2 + 2)
        for i in range(cid_max + 1):
            gid = cid_to_gid.get(i)
            if gid is not None:
                buffer[i * 2] = (gid >> 8) & 0xFF
                buffer[i * 2 + 1] = gid & 0xFF
        stream = PDStream(
            self._document_ref,
            io.BytesIO(bytes(buffer)),
            COSName.FLATE_DECODE,
        )
        self._cid_font.set_item(
            COSName.get_pdf_name("CIDToGIDMap"), stream.get_cos_object()
        )

    def _build_cid_set(self, cid_to_gid: dict[int, int]) -> None:
        """Write the ``/CIDSet`` stream (PDF/A requirement).

        Mirrors upstream ``buildCIDSet`` (Java line 301-315).
        """
        cid_max = max(cid_to_gid)
        buffer = bytearray(cid_max // 8 + 1)
        for cid in range(cid_max + 1):
            mask = 1 << (7 - cid % 8)
            buffer[cid // 8] |= mask
        stream = PDStream(
            self._document_ref,
            io.BytesIO(bytes(buffer)),
            COSName.FLATE_DECODE,
        )
        self.font_descriptor.set_cid_set(stream)

    def _build_widths_for_subset(self, cid_to_gid: dict[int, int]) -> None:
        """Emit ``/W`` widths for a subset font.

        Mirrors upstream ``buildWidths(TreeMap)`` (Java line 320-350).
        """
        try:
            head = self._ttf["head"]
            hmtx = self._ttf["hmtx"]
        except KeyError:
            return
        scaling = 1000.0 / float(getattr(head, "unitsPerEm", 1000) or 1000)
        widths = COSArray()
        inner = COSArray()
        prev = float("-inf")
        for cid in sorted(cid_to_gid):
            gid = cid_to_gid[cid]
            try:
                advance, _lsb = hmtx[self._ttf.getGlyphName(gid)]
            except (AttributeError, KeyError, TypeError):
                continue
            width = round(advance * scaling)
            if width == 1000:
                continue
            if prev != cid - 1:
                inner = COSArray()
                widths.add(COSInteger(int(cid)))
                widths.add(inner)
            inner.add(COSInteger(int(width)))
            prev = cid
        self._cid_font.set_item(COSName.get_pdf_name("W"), widths)

    def _build_widths_full(self, cid_font: COSDictionary) -> None:
        """Emit ``/W`` widths for a full-embed font.

        Mirrors upstream ``buildWidths(COSDictionary)`` (Java line 439-451).
        """
        try:
            num_glyphs = int(self._ttf["maxp"].numGlyphs)
            head = self._ttf["head"]
            hmtx = self._ttf["hmtx"]
        except KeyError:
            return
        scaling = 1000.0 / float(getattr(head, "unitsPerEm", 1000) or 1000)
        gid_widths: list[int] = []
        for cid in range(num_glyphs):
            try:
                advance, _lsb = hmtx[self._ttf.getGlyphName(cid)]
            except (AttributeError, KeyError, TypeError):
                advance = 0
            gid_widths.append(cid)
            gid_widths.append(int(advance))
        cid_font.set_item(
            COSName.get_pdf_name("W"), _encode_widths(gid_widths, scaling)
        )

    def _build_vertical_metrics_for_subset(self, cid_to_gid: dict[int, int]) -> None:
        """Emit ``/W2`` for subsets when vertical writing is in use.

        Mirrors upstream ``buildVerticalMetrics(TreeMap)`` (Java line
        378-434). Trimmed — fontTools doesn't always expose ``vhea`` /
        ``vmtx`` on partial TTFs, so we no-op when those tables are
        missing rather than synthesise zeros.
        """
        try:
            vhea = self._ttf["vhea"]
            vmtx = self._ttf["vmtx"]
            head = self._ttf["head"]
            hmtx = self._ttf["hmtx"]
        except KeyError:
            _LOG.warning("Vertical writing requested but font lacks vhea/vmtx")
            return
        scaling = 1000.0 / float(getattr(head, "unitsPerEm", 1000) or 1000)
        v_y = round(float(getattr(vhea, "ascent", 0) or 0) * scaling)
        w1 = round(-float(getattr(vhea, "advanceHeightMax", 0) or 0) * scaling)
        if v_y != 880 or w1 != -1000:
            cos_dw2 = COSArray()
            cos_dw2.add(COSInteger(int(v_y)))
            cos_dw2.add(COSInteger(int(w1)))
            self._cid_font.set_item(COSName.get_pdf_name("DW2"), cos_dw2)
        heights = COSArray()
        inner = COSArray()
        prev = float("-inf")
        for cid in sorted(cid_to_gid):
            try:
                advance_v, tsb = vmtx[self._ttf.getGlyphName(cid)]
                advance_h, _lsb = hmtx[self._ttf.getGlyphName(cid)]
            except (AttributeError, KeyError, TypeError):
                continue
            try:
                glyph = self._ttf["glyf"][self._ttf.getGlyphName(cid)]
                y_max = float(getattr(glyph, "yMax", 0) or 0)
            except (KeyError, AttributeError):
                y_max = 0
            height = round((y_max + tsb) * scaling)
            advance = round(-advance_v * scaling)
            if height == v_y and advance == w1:
                continue
            if prev != cid - 1:
                inner = COSArray()
                heights.add(COSInteger(int(cid)))
                heights.add(inner)
            inner.add(COSInteger(int(advance)))
            inner.add(COSInteger(int(round(advance_h * scaling / 2))))
            inner.add(COSInteger(int(height)))
            prev = cid
        self._cid_font.set_item(COSName.get_pdf_name("W2"), heights)

    def _build_vertical_metrics_full(self, cid_font: COSDictionary) -> None:
        """Skip ``/W2`` for full embeds when no vhea is present.

        Mirrors upstream ``buildVerticalMetrics(COSDictionary)`` (Java line
        557-586). We delegate to the subset variant under the same
        ``vhea`` precondition.
        """
        try:
            self._ttf["vhea"]
            self._ttf["vmtx"]
        except KeyError:
            return
        try:
            num_glyphs = int(self._ttf["maxp"].numGlyphs)
        except KeyError:
            return
        self._build_vertical_metrics_for_subset({c: c for c in range(num_glyphs)})

    # ---------- helpers ----------

    def _build_font_file2(self, ttf_subset: io.BufferedIOBase) -> None:
        """Embed *ttf_subset* as ``/FontFile2``."""
        data = ttf_subset.read()
        stream = PDStream(self._document_ref, io.BytesIO(data), COSName.FLATE_DECODE)
        stream.get_cos_object().set_long(COSName.get_pdf_name("Length1"), len(data))
        self.font_descriptor.set_font_file2(stream)

    def _add_name_tag(self, tag: str) -> None:
        """Prepend *tag* to ``BaseFont`` and ``FontName``.

        Mirrors upstream ``addNameTag`` (Java line 264-272).
        """
        name = self.font_descriptor.get_font_name() or ""
        new_name = tag + name
        self._dict.set_name(COSName.BASE_FONT, new_name)
        self.font_descriptor.set_font_name(new_name)
        self._cid_font.set_name(COSName.BASE_FONT, new_name)

    def _get_unicode_cmap_reverse(self) -> dict[int, list[int]]:
        """Return CID -> [code_point, ...] from the TTF cmap."""
        try:
            cmap_table = self._ttf["cmap"]
            best_cmap = cmap_table.getBestCmap()
        except (KeyError, AttributeError):
            return {}
        if best_cmap is None:
            return {}
        result: dict[int, list[int]] = {}
        for cp, name in best_cmap.items():
            try:
                gid = int(self._ttf.getGlyphID(name) or 0)
            except (AttributeError, TypeError):
                continue
            result.setdefault(gid, []).append(cp)
        return result

    def get_cid_font(self) -> Any:
        """Return the descendant :class:`PDCIDFontType2`.

        Mirrors upstream ``getCIDFont`` (Java line 713-717).
        """
        from .pd_cid_font_type2 import PDCIDFontType2

        return PDCIDFontType2(self._cid_font, self._parent, self._ttf)


def _to_cid_system_info(
    registry: str, ordering: str, supplement: int
) -> COSDictionary:
    """Build a fresh ``/CIDSystemInfo`` dictionary.

    Mirrors upstream private ``toCIDSystemInfo`` (Java line 186-193).
    """
    info = COSDictionary()
    info.set_string(COSName.get_pdf_name("Registry"), registry)
    info.set_string(COSName.get_pdf_name("Ordering"), ordering)
    info.set_int(COSName.get_pdf_name("Supplement"), supplement)
    return info


def _encode_widths(widths: list[int], scaling: float) -> COSArray:
    """Run the upstream three-state width compressor.

    Mirrors upstream ``getWidths(int[])`` (Java line 458-552).
    """
    if len(widths) < 2:
        raise ValueError("length of widths must be >= 2")
    last_cid = widths[0]
    last_value = round(widths[1] * scaling)
    inner = COSArray()
    outer = COSArray()
    outer.add(COSInteger(int(last_cid)))
    state = _State.FIRST
    i = 2
    while i < len(widths) - 1:
        cid = widths[i]
        value = round(widths[i + 1] * scaling)
        if state is _State.FIRST:
            if cid == last_cid + 1 and value == last_value:
                state = _State.SERIAL
            elif cid == last_cid + 1:
                state = _State.BRACKET
                inner = COSArray()
                inner.add(COSInteger(int(last_value)))
            else:
                inner = COSArray()
                inner.add(COSInteger(int(last_value)))
                outer.add(inner)
                outer.add(COSInteger(int(cid)))
        elif state is _State.BRACKET:
            if cid == last_cid + 1 and value == last_value:
                state = _State.SERIAL
                outer.add(inner)
                outer.add(COSInteger(int(last_cid)))
            elif cid == last_cid + 1:
                inner.add(COSInteger(int(last_value)))
            else:
                state = _State.FIRST
                inner.add(COSInteger(int(last_value)))
                outer.add(inner)
                outer.add(COSInteger(int(cid)))
        elif state is _State.SERIAL:  # noqa: SIM102 - upstream branch structure
            if cid != last_cid + 1 or value != last_value:
                outer.add(COSInteger(int(last_cid)))
                outer.add(COSInteger(int(last_value)))
                outer.add(COSInteger(int(cid)))
                state = _State.FIRST
        last_value = value
        last_cid = cid
        i += 2
    if state is _State.FIRST:
        inner = COSArray()
        inner.add(COSInteger(int(last_value)))
        outer.add(inner)
    elif state is _State.BRACKET:
        inner.add(COSInteger(int(last_value)))
        outer.add(inner)
    elif state is _State.SERIAL:
        outer.add(COSInteger(int(last_cid)))
        outer.add(COSInteger(int(last_value)))
    return outer


__all__ = ["PDCIDFontType2Embedder"]
