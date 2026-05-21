from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.fontbox.ttf import OTFParser, TrueTypeFont, TTFParser
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

from .pd_cid_font import PDCIDFont

if TYPE_CHECKING:
    from pypdfbox.fontbox.cid_font_mapping import CIDFontMapping
    from pypdfbox.pdmodel.common.pd_stream import PDStream

    from .pd_type0_font import PDType0Font

_LOG = logging.getLogger(__name__)

_CID_TO_GID_MAP: COSName = COSName.get_pdf_name("CIDToGIDMap")
_IDENTITY: COSName = COSName.get_pdf_name("Identity")
_OPEN_TYPE: str = "OpenType"

# Default TrueType units-per-em — matches upstream's fallback when the
# font program is missing or could not be parsed (PDF coordinate space
# is 1000-unit, the actual em is recovered from the embedded /head when
# the program is available).
_DEFAULT_UNITS_PER_EM: int = 1000


class PDCIDFontType2(PDCIDFont):
    """CIDFontType2 — TrueType-based CIDFont. Mirrors PDFBox ``PDCIDFontType2``.

    Wraps the dictionary surface, CID width tables, ``/CIDToGIDMap``
    interpretation, and embedded ``/FontFile2`` access. Renderer-facing
    glyph paths are extracted via fontTools' glyph-set draw protocol on
    the embedded TTF.
    """

    SUB_TYPE = "CIDFontType2"

    def __init__(
        self,
        font_dict: COSDictionary | None = None,
        parent_type0_font: PDType0Font | None = None,
        true_type_font: TrueTypeFont | None = None,
    ) -> None:
        super().__init__(font_dict, parent_type0_font)
        self._cid_to_gid_cache: tuple[int, ...] | None = None
        self._cid_to_gid_cache_loaded = False
        # Embedded ``/FontFile2`` parsed lazily on first glyph access.
        # ``None`` means "not yet attempted"; ``False`` means "tried,
        # no /FontFile2 or parse failed". When ``true_type_font`` is
        # supplied (e.g. by ``PDCIDFontType2Embedder.get_cid_font`` which
        # reuses the already-parsed embedded program), seed the cache so
        # the lazy parse short-circuits.
        self._ttf: TrueTypeFont | None | bool = (
            true_type_font if true_type_font is not None else None
        )
        # Memoised bounding box — mirrors upstream's ``fontBBox`` field
        # so a single resolve runs once per instance even when callers
        # ask for the bbox repeatedly.
        self._font_bbox: PDRectangle | None | bool = False
        # Cache of CIDs for which we already issued a "no mapping" warning
        # so repeated codeToGID calls don't spam the log. Mirrors upstream
        # ``noMapping`` (line 61): ``Set<Integer>`` initialised in the
        # constructor and consulted on the non-embedded /ToUnicode fallback.
        self._no_mapping: set[int] = set()

    def get_subtype(self) -> str | None:
        return self.SUB_TYPE

    # ---------- /CIDToGIDMap interpretation ----------

    def set_cid_to_gid_map(self, value: COSStream | str | None) -> None:
        super().set_cid_to_gid_map(value)
        self.clear_cid_to_gid_map_cache()

    def cid_to_gid(self, cid: int) -> int:
        """Map a CID to a TrueType glyph ID.

        ``/CIDToGIDMap`` stream values are big-endian unsigned shorts,
        one per CID. Missing or ``/Identity`` maps use the CID as the GID.
        CIDs outside an explicit stream map resolve to GID 0, matching the
        embedded-font path in PDFBox ``PDCIDFontType2.codeToGID``.
        """
        if cid < 0:
            return 0
        mapping = self._get_cid_to_gid_map_values()
        if mapping is None:
            return int(cid)
        if cid < len(mapping):
            return mapping[cid]
        return 0

    def code_to_gid(self, code: int) -> int:
        """Return the GID for ``code``.

        Mirrors upstream ``PDCIDFontType2.codeToGID`` — the parent
        :class:`PDType0Font` has already converted character code to CID
        via the active CMap, so for the descendant CIDFontType2 the
        ``code`` argument is the CID to be mapped through ``/CIDToGIDMap``.
        """
        return self.cid_to_gid(code)

    def code_to_cid(self, code: int) -> int:
        """Identity — the parent :class:`PDType0Font` CMap has already
        mapped ``code`` to CID before this descendant is consulted.
        Mirrors upstream ``PDCIDFontType2.codeToCID``.
        """
        return int(code)

    def _code_to_gid(self, code: int, ttf: object | None = None) -> int:
        """Renderer-facing hook mirroring ``PDTrueTypeFont._code_to_gid``."""
        return self.code_to_gid(code)

    def has_cid_to_gid_map(self) -> bool:
        return self._get_cid_to_gid_map_values() is not None

    def clear_cid_to_gid_map_cache(self) -> None:
        self._cid_to_gid_cache = None
        self._cid_to_gid_cache_loaded = False

    def get_cid_to_gid_map_bytes(self) -> bytes | None:
        """Return the raw decoded bytes of the ``/CIDToGIDMap`` stream,
        or ``None`` when the entry is absent or set to the name
        ``/Identity``.

        Mirrors upstream ``PDCIDFontType2.getCIDToGIDMap`` which yields
        the stream payload (callers iterate as big-endian ``uint16``
        GIDs). The parent's :meth:`PDCIDFont.get_cid_to_gid_map` still
        exposes the raw COS entry (``COSStream | str | None``) for
        callers that need to round-trip the dictionary verbatim.
        """
        raw = self._raw_cid_to_gid_entry()
        if isinstance(raw, COSStream):
            return raw.to_byte_array()
        return None

    def is_identity_cid_to_gid_map(self) -> bool:
        """``True`` when ``/CIDToGIDMap`` is the name ``/Identity`` *or*
        is absent — the spec defaults an unset entry to ``/Identity``.
        Mirrors upstream ``PDCIDFontType2.isIdentityCIDToGIDMap``."""
        raw = self._raw_cid_to_gid_entry()
        if raw is None:
            return True
        if isinstance(raw, COSName):
            return raw.name == "Identity"
        if isinstance(raw, str):
            return raw == "Identity"
        return False

    def _raw_cid_to_gid_entry(self) -> Any:
        """Read the ``/CIDToGIDMap`` entry from the underlying dict
        without coercion — used by the upstream-named accessors that
        each interpret it differently."""
        return self._dict.get_dictionary_object(_CID_TO_GID_MAP)

    def _get_cid_to_gid_map_values(self) -> tuple[int, ...] | None:
        if self._cid_to_gid_cache_loaded:
            return self._cid_to_gid_cache
        raw = self._raw_cid_to_gid_entry()
        if raw is None:
            self._cid_to_gid_cache = None
        elif isinstance(raw, COSName):
            # /Identity -> identity mapping (None signals "use cid as gid").
            self._cid_to_gid_cache = None
        elif isinstance(raw, COSStream):
            data = raw.to_byte_array()
            usable = len(data) - (len(data) % 2)
            self._cid_to_gid_cache = tuple(
                int.from_bytes(data[i : i + 2], "big")
                for i in range(0, usable, 2)
            )
        else:
            self._cid_to_gid_cache = None
        self._cid_to_gid_cache_loaded = True
        return self._cid_to_gid_cache

    # ---------- embedded TTF program ----------

    def _get_font_program_stream(self) -> PDStream | None:
        descriptor = self.get_font_descriptor()
        if descriptor is None:
            return None
        for getter in (
            descriptor.get_font_file2,
            descriptor.get_font_file3,
            descriptor.get_font_file,
        ):
            stream = getter()
            if stream is not None:
                return stream
        return None

    def get_true_type_font(self) -> TrueTypeFont | None:
        """Return the parsed :class:`TrueTypeFont` for this font's
        embedded program, or ``None`` if no embedded program exists or
        it cannot be parsed. Result is cached on the instance.

        Mirrors upstream ``PDCIDFontType2`` program probing. Tries
        ``/FontFile2`` first (the canonical form per PDF 32000-1
        §9.6.2 Table 122), then ``/FontFile3`` (embedded OTF), then the
        legacy ``/FontFile`` slot Acrobat accepts for malformed Type2
        descendants (PDFBOX-2599).
        """
        if self._ttf is not None:
            return self._ttf if isinstance(self._ttf, TrueTypeFont) else None

        program_stream = self._get_font_program_stream()
        if program_stream is None:
            self._ttf = False
            return None
        try:
            raw = program_stream.to_byte_array()
            self._ttf = TrueTypeFont.from_bytes(raw)
        except Exception:  # noqa: BLE001
            _LOG.exception("failed to parse font program for %s", self.get_name())
            self._ttf = False
            return None
        return self._ttf

    def get_open_type_font(self) -> TrueTypeFont | None:
        """Return the embedded program as an :class:`OpenTypeFont` when
        the parsed program *is* one and its outlines are supported,
        otherwise ``None``.

        Mirrors upstream's private ``otf`` field (PDCIDFontType2.java
        line 54) and the constructor logic that populates it (lines
        91-93 / 148-149): ``otf`` is non-null only when the parsed font
        is an :class:`OpenTypeFont` *and* its outlines are supported
        (CFF/CFF2-without-CFF1 is rejected upstream as unsupported).
        Pypdfbox lacks a public Java accessor for this field, but the
        rendering layer needs the same probe to decide between the
        ``glyf`` and CFF outline paths — exposing it as a getter keeps
        callers from re-implementing the upstream selection.
        """
        from pypdfbox.fontbox.ttf.open_type_font import (  # noqa: PLC0415
            OpenTypeFont,
        )

        ttf = self.get_true_type_font()
        if ttf is None or not isinstance(ttf, OpenTypeFont):
            return None
        try:
            if not ttf.is_supported_otf():
                return None
        except Exception:  # noqa: BLE001
            return None
        return ttf

    def get_cmap_lookup(self) -> Any:
        """Return the embedded program's unicode cmap lookup, or ``None``.

        Mirrors upstream's private ``cmap`` field (PDCIDFontType2.java
        line 58) populated by ``ttf.getUnicodeCmapLookup(false)`` in the
        constructor (line 152). Used by upstream's :meth:`encode` and the
        non-embedded ``codeToGID`` fallback to translate unicode
        codepoints into TrueType glyph IDs. The lookup is the
        non-strict variant — Acrobat tolerates Mac/Roman or symbol cmaps
        so we follow the same liberal probing.

        Result is *not* cached on the instance — :class:`TrueTypeFont`
        already memoises the chosen subtable, and re-asking is cheap.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return None
        getter = getattr(ttf, "get_unicode_cmap_lookup", None)
        if not callable(getter):
            return None
        try:
            return getter(False)  # noqa: FBT003 — mirror Java boolean
        except Exception:  # noqa: BLE001
            return None

    def get_no_mapping(self) -> set[int]:
        """Return the mutable set of character codes for which no
        unicode-to-GID mapping was found.

        Mirrors upstream's private ``noMapping`` field (PDCIDFontType2.java
        line 61) — a deduplication set that prevents the
        ``codeToGID`` non-embedded fallback from logging the same
        "Failed to find a character mapping" warning multiple times for
        the same code. Exposed so test harnesses (and the rendering
        layer's own logging path) can inspect / reset it.
        """
        return self._no_mapping

    def set_true_type_font(self, ttf: TrueTypeFont | None) -> None:
        """Inject a pre-parsed :class:`TrueTypeFont`. Used by callers
        that already have the font program in hand (avoids a redundant
        re-parse) and by tests that bypass ``/FontFile2``."""
        self._ttf = ttf if ttf is not None else False
        # Bounding box is derived from the TTF head table — invalidate
        # the memoised value when the program changes.
        self._font_bbox = False

    @staticmethod
    def get_parser(
        data: bytes | bytearray, is_embedded: bool = True
    ) -> TTFParser:
        """Return the parser to use for an embedded font program.

        Mirrors upstream private ``PDCIDFontType2.getParser`` — peeks the
        first four bytes of ``data`` and returns an :class:`OTFParser`
        for the OpenType ``OTTO`` magic, otherwise a :class:`TTFParser`.
        The PDF descriptor doesn't disambiguate ``/FontFile2`` payloads
        between TrueType and OpenType-with-CFF, so we sniff the SFNT
        version tag the way fontTools' SFNT loader does.

        ``is_embedded`` is forwarded to the parser so it can apply the
        relaxed checks PDFBox enables for embedded SFNTs (missing
        ``hhea``/``hmtx`` etc. become warnings instead of errors).
        """
        tag = bytes(data[:4]) if data else b""
        if tag == b"OTTO":
            return OTFParser(is_embedded=is_embedded)
        return TTFParser(is_embedded=is_embedded)

    def is_embedded(self) -> bool:
        """``True`` when the descriptor carries an embedded font program
        usable as a CIDFontType2.

        Mirrors upstream ``PDCIDFontType2.isEmbedded`` probing order:
        ``/FontFile2``, then ``/FontFile3``, then legacy ``/FontFile``.
        """
        return self._get_font_program_stream() is not None

    def is_damaged(self) -> bool:
        """``True`` when the descriptor advertises an embedded font
        program but the program could not be parsed.

        Mirrors upstream ``PDCIDFontType2.isDamaged``. Returns ``False``
        when the font is not embedded (nothing to parse, nothing
        damaged) and ``False`` when the parse succeeded.
        """
        if not self.is_embedded():
            return False
        # Force the lazy parse and check whether it surfaced a real TTF.
        self.get_true_type_font()
        return self._ttf is False

    # ---------- glyph metrics from the embedded program ----------

    def get_width_from_font(self, cid: int) -> float:
        """Glyph advance for ``cid`` read directly from the embedded
        TrueType program, in 1/1000 em.

        Mirrors upstream ``PDCIDFontType2.getWidthFromFont``. Resolves
        ``cid`` to a GID via :meth:`cid_to_gid`, asks the embedded
        ``hmtx`` table for the advance, then scales by
        ``1000 / unitsPerEm`` so the result is in PDF text-space units.
        Returns ``0.0`` when no embedded program is available.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return 0.0
        try:
            gid = self.cid_to_gid(cid)
            advance = ttf.get_advance_width(gid)
            units_per_em = ttf.get_units_per_em()
        except Exception:  # noqa: BLE001
            return 0.0
        if units_per_em <= 0:
            return 0.0
        return float(advance) * 1000.0 / float(units_per_em)

    def get_height(self, cid: int) -> float:
        """Vertical extent of glyph ``cid`` in 1/1000 em.

        Mirrors upstream ``PDCIDFontType2.getHeight``. Reads
        ``yMax - yMin`` from the embedded ``glyf`` table for the
        resolved GID, scaled by ``1000 / unitsPerEm``. Falls back to
        the parent's ``/W2`` lookup when no embedded program is
        available.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return super().get_height(cid)
        try:
            gid = self.cid_to_gid(cid)
        except Exception:  # noqa: BLE001
            return super().get_height(cid)
        if gid <= 0:
            return super().get_height(cid)
        units_per_em = ttf.get_units_per_em()
        if units_per_em <= 0:
            return 0.0
        inner = getattr(ttf, "_tt", None)
        if inner is None or "glyf" not in inner:
            return 0.0
        try:
            order = inner.getGlyphOrder()
            if not 0 <= gid < len(order):
                return 0.0
            name = order[gid]
            glyph = inner["glyf"][name]
            y_min = int(getattr(glyph, "yMin", 0))
            y_max = int(getattr(glyph, "yMax", 0))
        except (KeyError, AttributeError):
            return 0.0
        return float(y_max - y_min) * 1000.0 / float(units_per_em)

    def get_average_font_width(self) -> float:
        """Mean glyph advance across the embedded program (1/1000 em).

        Mirrors upstream ``PDCIDFontType2.getAverageFontWidth``. Walks
        the embedded ``hmtx`` table and averages the *positive* advance
        widths (zero-width slots, typically ``.notdef`` and combining
        marks, are excluded so they don't drag the mean toward zero).
        Falls back to the parent's ``/W``-based average — and ultimately
        to ``/DW`` — when no embedded program is available.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return super().get_average_font_width()
        units_per_em = ttf.get_units_per_em()
        if units_per_em <= 0:
            return super().get_average_font_width()
        try:
            advances = ttf.advance_widths
        except Exception:  # noqa: BLE001
            return super().get_average_font_width()
        positive = [w for w in advances if w > 0]
        if not positive:
            return super().get_average_font_width()
        mean_units = sum(positive) / float(len(positive))
        return mean_units * 1000.0 / float(units_per_em)

    def get_font_matrix(self) -> list[float]:
        """Return the 6-element font matrix mapping glyph space to text
        space (``[1/upem 0 0 1/upem 0 0]`` for TrueType).

        Mirrors upstream ``PDCIDFontType2.getFontMatrix``. Falls back to
        a 1000-unit em (``1/1000``) when no embedded program is
        available — that matches PDF 32000-1's default for fonts with
        no explicit matrix and keeps callers from dividing by zero.
        """
        ttf = self.get_true_type_font()
        if ttf is not None:
            try:
                upem = ttf.get_units_per_em()
            except Exception:  # noqa: BLE001
                upem = _DEFAULT_UNITS_PER_EM
            if upem <= 0:
                upem = _DEFAULT_UNITS_PER_EM
        else:
            upem = _DEFAULT_UNITS_PER_EM
        scale = 1.0 / float(upem)
        return [scale, 0.0, 0.0, scale, 0.0, 0.0]

    def get_bounding_box(self) -> PDRectangle | None:
        """Return the font's bounding box.

        Mirrors upstream ``PDCIDFontType2.getBoundingBox``. Memoises the
        result on first call (matching upstream's ``fontBBox`` field),
        delegating the actual resolve to :meth:`generate_bounding_box`
        which encodes the descriptor-first / TTF-fallback ordering.
        """
        if self._font_bbox is not False:
            return self._font_bbox  # type: ignore[return-value]
        bbox = self.generate_bounding_box()
        self._font_bbox = bbox
        return bbox

    def generate_bounding_box(self) -> PDRectangle | None:
        """Resolve the font's bounding box from the descriptor or
        embedded TTF.

        Mirrors upstream private ``PDCIDFontType2.generateBoundingBox``:
        prefer the descriptor's ``/FontBBox`` when present and *not*
        all-zero, otherwise fall back to the embedded TTF's ``head``
        table. Returns ``None`` when neither source is available — the
        upstream signature throws ``IOException`` on a missing program,
        but pypdfbox treats absent metrics as soft-null (callers know to
        skip layout for bbox-less fonts).
        """
        descriptor = self.get_font_descriptor()
        if descriptor is not None:
            bbox = descriptor.get_font_bounding_box()
            if bbox is not None and (
                float(bbox.lower_left_x) != 0.0
                or float(bbox.lower_left_y) != 0.0
                or float(bbox.upper_right_x) != 0.0
                or float(bbox.upper_right_y) != 0.0
            ):
                return PDRectangle(
                    float(bbox.lower_left_x),
                    float(bbox.lower_left_y),
                    float(bbox.upper_right_x),
                    float(bbox.upper_right_y),
                )
        ttf = self.get_true_type_font()
        if ttf is not None:
            try:
                x_min, y_min, x_max, y_max = ttf.get_font_bbox()
            except Exception:  # noqa: BLE001
                return super().get_bounding_box()
            return PDRectangle(
                float(x_min),
                float(y_min),
                float(x_max),
                float(y_max),
            )
        return super().get_bounding_box()

    def has_glyph(self, cid: int) -> bool:
        """``True`` when ``cid`` resolves to a non-``.notdef`` glyph.

        Prefers the embedded TTF (a glyph maps to GID != 0); falls back
        to the parent's ``/W``/``/DW`` advance heuristic when no font
        program is available.
        """
        ttf = self.get_true_type_font()
        if ttf is not None:
            try:
                gid = self.cid_to_gid(cid)
            except Exception:  # noqa: BLE001
                return super().has_glyph(cid)
            return gid > 0
        return super().has_glyph(cid)

    def get_glyph_path(self, cid: int) -> list[tuple[Any, ...]]:
        """Glyph outline for ``cid`` in *font units*.

        Resolves ``cid`` to a GID via :meth:`cid_to_gid`, then draws the
        TTF glyph through fontTools' glyph-set draw protocol into the
        same ``("moveto", x, y)`` / ``("lineto", x, y)`` /
        ``("curveto", x1, y1, x2, y2, x3, y3)`` / ``("closepath",)``
        format used by the Type1/CFF code path. Returns ``[]`` when no
        embedded program is available or the glyph cannot be drawn.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return []
        try:
            gid = self.cid_to_gid(cid)
            glyph_name = ttf._tt.getGlyphName(gid)  # noqa: SLF001
            glyph_set = ttf._tt.getGlyphSet()  # noqa: SLF001
            glyph = glyph_set[glyph_name]
        except Exception:  # noqa: BLE001
            return []
        from pypdfbox.fontbox.type1.type1_font import _make_path_pen  # noqa: PLC0415

        pen = _make_path_pen()
        try:
            glyph.draw(pen)
        except Exception:  # noqa: BLE001
            return []
        return list(pen.commands)

    def get_normalized_path(self, cid: int) -> list[tuple[Any, ...]]:
        """Glyph outline for ``cid`` normalized to 1/1000 em.

        Mirrors upstream ``PDCIDFontType2.getNormalizedPath`` which
        scales the embedded TTF's outline by ``1000 / unitsPerEm`` so
        downstream consumers (text extraction, structure tagging) get a
        single unit system regardless of the font program's native upem.
        Returns ``[]`` when no embedded program is available, the glyph
        cannot be drawn, or the path is empty (matches upstream's
        ``new GeneralPath()`` empty fallback).

        Honours the upstream Acrobat-quirk: when the font is *not*
        embedded and the resolved GID is 0 (notdef), no path is drawn
        — Acrobat suppresses notdef boxes for substitute fonts (see
        upstream comment referencing PDFBOX-2372).
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return []
        try:
            gid = self.cid_to_gid(cid)
        except Exception:  # noqa: BLE001
            return []
        # Acrobat draws no notdef for substitute (non-embedded) fonts.
        if gid == 0 and not self.is_embedded():
            return []
        path = self.get_glyph_path(cid)
        if not path:
            return []
        units_per_em = ttf.get_units_per_em()
        if units_per_em <= 0 or units_per_em == 1000:
            return path
        scale = 1000.0 / float(units_per_em)
        scaled: list[tuple[Any, ...]] = []
        for cmd in path:
            if len(cmd) <= 1:
                # ("closepath",) — no coordinates to scale.
                scaled.append(cmd)
                continue
            head = cmd[0]
            coords = tuple(float(v) * scale for v in cmd[1:])
            scaled.append((head, *coords))
        return scaled

    # ---------- glyph-ID encoding ----------

    def encode_glyph_id(self, glyph_id: int) -> bytes:
        """Encode a glyph index as the two-byte big-endian sequence
        used in Identity-H / Identity-V content streams.

        Mirrors upstream ``PDCIDFontType2.encodeGlyphId(int glyphId)``:
        CIDs in a TrueType-backed Type0 font are always 2-byte (16-bit)
        on the wire. Wider GIDs are masked to 16 bits — matching the
        Java cast ``(byte)(glyphId >> 8 & 0xff)`` / ``(byte)(glyphId &
        0xff)``.
        """
        gid = int(glyph_id) & 0xFFFF
        return bytes((gid >> 8 & 0xFF, gid & 0xFF))

    # ---------- glyph-path entry points (upstream-named aliases) ----------

    def get_path(self, code: int) -> list[tuple[Any, ...]]:
        """Glyph outline for ``code`` in *font units*.

        Mirrors upstream ``PDCIDFontType2.getPath(int)``. Routes through
        :meth:`get_path_from_outlines` when the embedded program is an
        OpenType wrapper carrying CFF/CFF2 (PostScript) outlines, and
        through :meth:`get_glyph_path` (TTF ``glyf``) otherwise. Returns
        ``[]`` when no embedded program is available or the glyph cannot
        be drawn — matching upstream's ``new GeneralPath()`` empty
        fallback.
        """
        if self.is_open_type_post_script():
            path = self.get_path_from_outlines(code)
            return path if path is not None else []
        return self.get_glyph_path(code)

    def get_path_from_outlines(
        self, code: int
    ) -> list[tuple[Any, ...]] | None:
        """Outline path for ``code`` from a CFF/CFF2 OpenType program.

        Mirrors upstream private ``PDCIDFontType2.getPathFromOutlines``.
        Resolves ``code`` to a GID via :meth:`code_to_gid`, then asks the
        CFF Type 2 charstring engine for its path. Returns ``None`` when
        the program is not OpenType-PostScript or the charstring cannot
        be materialised — callers (``getPath`` / ``getNormalizedPath``)
        substitute an empty path. Exposed as protected (rather than
        private) because the rendering layer needs to reproduce the
        upstream branching.
        """
        ttf = self.get_true_type_font()
        if ttf is None or not self.is_open_type_post_script():
            return None
        try:
            gid = self.code_to_gid(code)
        except Exception:  # noqa: BLE001
            return None
        # OpenType-PostScript programs expose Type 2 charstrings via the
        # CFF table; pypdfbox routes through fontTools' glyph-set draw
        # protocol exactly the way the TrueType path does — the glyph
        # set abstracts the outline format away.
        try:
            glyph_name = ttf._tt.getGlyphName(gid)  # noqa: SLF001
            glyph_set = ttf._tt.getGlyphSet()  # noqa: SLF001
            glyph = glyph_set[glyph_name]
        except Exception:  # noqa: BLE001
            return None
        from pypdfbox.fontbox.type1.type1_font import _make_path_pen  # noqa: PLC0415

        pen = _make_path_pen()
        try:
            glyph.draw(pen)
        except Exception:  # noqa: BLE001
            return None
        commands = list(pen.commands)
        return commands if commands else None

    # ---------- unicode -> bytes encoding ----------

    def encode(self, unicode_codepoint: int) -> bytes:
        """Encode a single unicode codepoint as the descendant byte
        sequence for a Type 0 content stream.

        Mirrors upstream ``PDCIDFontType2.encode(int)``. Resolution
        order matches upstream:

        1. Embedded font + Identity-H/V parent CMap → resolve via the
           TTF unicode cmap (``cmap.getGlyphId``);
        2. Embedded font + predefined parent CMap → resolve through the
           parent's UCS-2 CMap (CID → unicode → CID);
        3. Fall back to the parent's ``/ToUnicode`` CMap, returning the
           raw byte sequence it carries for the unicode string;
        4. Non-embedded font → resolve directly via the TTF unicode
           cmap.

        Raises ``ValueError`` (mirrors upstream's
        ``IllegalArgumentException``) when no glyph can be located —
        the caller should never see GID 0 for unicode it knows the font
        covers.
        """
        from pypdfbox.pdmodel.font.pd_type0_font import (  # noqa: PLC0415
            PDType0Font,
        )

        cid: int = -1
        parent = self.get_parent()
        embedded = self.is_embedded()
        ttf = self.get_true_type_font()
        cmap_subtable = ttf.get_unicode_cmap_subtable() if ttf is not None else None

        if embedded:
            parent_cmap_name: str | None = None
            if isinstance(parent, PDType0Font):
                parent_cmap = parent.get_cmap()
                if parent_cmap is not None:
                    parent_cmap_name = getattr(parent_cmap, "name", None)
            if parent_cmap_name is not None and parent_cmap_name.startswith(
                "Identity-"
            ):
                if cmap_subtable is not None:
                    cid = cmap_subtable.get_glyph_id(unicode_codepoint)
            elif isinstance(parent, PDType0Font):
                ucs2 = parent.get_cmap_ucs2()
                if ucs2 is not None:
                    cid = ucs2.to_cid(unicode_codepoint)

            if cid in (-1, 0):
                # Fall back to the parent's /ToUnicode CMap, which (if
                # present) yields the raw byte sequence for this
                # unicode codepoint directly.
                if isinstance(parent, PDType0Font):
                    to_unicode_cmap = parent.get_to_unicode_cmap()
                    if to_unicode_cmap is not None:
                        codes = to_unicode_cmap.get_codes_from_unicode(
                            chr(unicode_codepoint)
                        )
                        if codes is not None:
                            return bytes(codes)
                if cid == -1:
                    cid = 0
        else:
            if cmap_subtable is None:
                raise ValueError(
                    f"No glyph for U+{unicode_codepoint:04X} in font "
                    f"{self.get_name()}"
                )
            cid = cmap_subtable.get_glyph_id(unicode_codepoint)

        if cid == 0:
            raise ValueError(
                f"No glyph for U+{unicode_codepoint:04X} in font "
                f"{self.get_name()}"
            )
        return self.encode_glyph_id(cid)

    # ---------- font lookup / substitution ----------

    def find_font_or_substitute(self) -> CIDFontMapping | None:
        """Locate the embedded :class:`TrueTypeFont` or — failing that —
        a substitute via the global :class:`FontMappers` registry.

        Mirrors upstream private ``PDCIDFontType2.findFontOrSubstitute``.
        Used when the descriptor lacks an embedded program: PDFBox asks
        the FontMappers registry for a matching CID font (preferred) or
        a name-keyed TrueType substitute. Returns the
        :class:`CIDFontMapping` so callers can both inspect whether the
        match was a fallback and reach the underlying font program.

        Returns ``None`` when no FontMapper override is registered and
        the bundled :class:`DefaultFontMapper` declines to substitute
        — pypdfbox's default mapper has no on-disk CID font scanner, so
        fail-soft is the right behaviour (callers fall back to GID 0 /
        notdef rather than throwing).
        """
        from pypdfbox.fontbox.font_mappers import FontMappers  # noqa: PLC0415

        try:
            mapper = FontMappers.instance()
        except Exception:  # noqa: BLE001
            return None
        get_cid_font = getattr(mapper, "get_cid_font", None)
        if not callable(get_cid_font):
            return None
        try:
            return get_cid_font(
                self.get_base_font() or self.get_name() or "",
                self.get_font_descriptor(),
                self.get_cid_system_info(),
            )
        except Exception:  # noqa: BLE001
            return None

    # ---------- OpenType wrapper predicates ----------

    def is_open_type_post_script(self) -> bool:
        """``True`` when the embedded font program is an OpenType file
        with PostScript (CFF/CFF2) outlines.

        Mirrors upstream's ``otf != null && otf.isPostScript()`` guard
        used to decide between the TrueType ``glyf`` outline path and
        the CFF Type 2 charstring outline path inside ``getPath`` /
        ``getNormalizedPath``. Exposed as a predicate so callers that
        reproduce the upstream branching can ask the question directly
        instead of duck-typing the parsed program.
        """
        ttf = self.get_true_type_font()
        if ttf is None:
            return False
        is_post_script = getattr(ttf, "is_post_script", None)
        if not callable(is_post_script):
            return False
        try:
            return bool(is_post_script())
        except Exception:  # noqa: BLE001
            return False


__all__ = ["PDCIDFontType2"]
