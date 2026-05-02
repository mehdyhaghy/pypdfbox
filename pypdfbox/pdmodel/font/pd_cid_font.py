from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSNumber, COSStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

from .pd_cid_system_info import PDCIDSystemInfo
from .pd_font import PDFont

if TYPE_CHECKING:
    from .pd_type0_font import PDType0Font

_CID_SYSTEM_INFO: COSName = COSName.get_pdf_name("CIDSystemInfo")
_DW: COSName = COSName.get_pdf_name("DW")
_DW2: COSName = COSName.get_pdf_name("DW2")
_W: COSName = COSName.get_pdf_name("W")
_W2: COSName = COSName.get_pdf_name("W2")
_CID_TO_GID_MAP: COSName = COSName.get_pdf_name("CIDToGIDMap")
_IDENTITY: COSName = COSName.get_pdf_name("Identity")


class PDCIDFont(PDFont):
    """Abstract CIDFont wrapper. Mirrors PDFBox ``PDCIDFont``.

    A CIDFont is the descendant of a composite ``PDType0Font``; although its
    ``/Type`` is ``/Font`` it is not directly usable as a font. Concrete
    subclasses (``PDCIDFontType0``, ``PDCIDFontType2``) set ``/Subtype``.

    Lite — the ``PDFontLike`` / ``PDVectorFont`` mixins are deferred.
    This wrapper exposes the COS-level accessors over the dictionary
    entries enumerated in PDF 32000-1 §9.7.4 plus parsing of the ``/W``
    and ``/W2`` width tables (§9.7.4.3) into ``CID -> width`` maps.
    """

    def __init__(
        self,
        font_dict: COSDictionary | None = None,
        parent_type0_font: PDType0Font | None = None,
    ) -> None:
        super().__init__(font_dict)
        self._parent = parent_type0_font
        # Lazy caches for parsed /W and /W2 tables (PDF 32000-1 §9.7.4.3).
        self._widths: dict[int, float] | None = None
        self._widths2: dict[int, tuple[float, float, float]] | None = None

    # ---------- subtype (abstract) ----------

    def get_subtype(self) -> str | None:  # pragma: no cover - overridden
        raise NotImplementedError("PDCIDFont subclasses must implement get_subtype()")

    # ---------- font identity ----------

    def get_base_font(self) -> str | None:
        """``/BaseFont`` — the PostScript name of the CIDFont.

        Mirrors upstream ``PDCIDFont.getBaseFont``. PDFBox surfaces this
        in addition to ``getName`` (the latter aliases the former on
        :class:`PDCIDFont`); we expose both so that ports of upstream
        callers find the API they expect.
        """
        return self._dict.get_name(COSName.get_pdf_name("BaseFont"))

    # ---------- parent Type0 font ----------

    def get_parent(self) -> PDType0Font | None:
        return self._parent

    # ---------- /CIDSystemInfo ----------

    def get_cid_system_info(self) -> PDCIDSystemInfo | None:
        v = self._dict.get_dictionary_object(_CID_SYSTEM_INFO)
        if isinstance(v, COSDictionary):
            return PDCIDSystemInfo(v)
        return None

    def set_cid_system_info(self, info: PDCIDSystemInfo | None) -> None:
        if info is None:
            self._dict.remove_item(_CID_SYSTEM_INFO)
            return
        self._dict.set_item(_CID_SYSTEM_INFO, info.get_cos_object())

    # ---------- /DW (default width) ----------

    def get_dw(self) -> int:
        return self._dict.get_int(_DW, 1000)

    def set_dw(self, width: int) -> None:
        self._dict.set_int(_DW, int(width))

    # ---------- /DW2 (default vertical metrics) ----------

    def get_dw2(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_DW2)
        if isinstance(v, COSArray):
            return v
        return None

    def set_dw2(self, arr: COSArray | None) -> None:
        if arr is None:
            self._dict.remove_item(_DW2)
            return
        self._dict.set_item(_DW2, arr)

    # ---------- /W (per-CID horizontal widths) ----------

    def get_w(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_W)
        if isinstance(v, COSArray):
            return v
        return None

    def set_w(self, arr: COSArray | None) -> None:
        if arr is None:
            self._dict.remove_item(_W)
            return
        self._dict.set_item(_W, arr)

    # ---------- /W2 (per-CID vertical widths) ----------

    def get_w2(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_W2)
        if isinstance(v, COSArray):
            return v
        return None

    def set_w2(self, arr: COSArray | None) -> None:
        if arr is None:
            self._dict.remove_item(_W2)
            return
        self._dict.set_item(_W2, arr)

    # ---------- parsed width tables (PDF 32000-1 §9.7.4.3) ----------

    def get_default_width(self) -> float:
        """Return ``/DW`` as a float, defaulting to 1000 per the spec."""
        return self._dict.get_float(_DW, 1000.0)

    def get_widths(self) -> dict[int, float]:
        """Parse ``/W`` into a ``CID -> width`` map (1/1000 em).

        Per PDF 32000-1 §9.7.4.3 the ``/W`` array uses two interleaved
        forms:

        * ``c [w1 w2 w3 ...]`` — consecutive CIDs starting at ``c`` get
          widths ``w1``, ``w2``, ...
        * ``c1 c2 w`` — every CID in the inclusive range ``c1..c2`` gets
          width ``w``.

        Result is cached on first call. Mutating ``/W`` after the cache is
        populated requires :meth:`clear_widths_cache`.
        """
        if self._widths is not None:
            return self._widths
        widths: dict[int, float] = {}
        w = self.get_w()
        if w is not None:
            self._parse_w_array(w, widths)
        self._widths = widths
        return widths

    def get_glyph_width(self, cid: int) -> float:
        """Width of ``cid`` in 1/1000 em, falling back to ``/DW`` when unmapped."""
        widths = self.get_widths()
        w = widths.get(cid)
        if w is not None:
            return w
        return self.get_default_width()

    def clear_widths_cache(self) -> None:
        """Drop cached parsed ``/W`` and ``/W2`` tables."""
        self._widths = None
        self._widths2 = None

    @staticmethod
    def _parse_w_array(arr: COSArray, out: dict[int, float]) -> None:
        i = 0
        n = arr.size()
        while i < n:
            first = arr.get_object(i)
            if not isinstance(first, COSNumber):
                # Malformed — skip to next slot rather than raise; mirrors
                # PDFBox's lenient parsing.
                i += 1
                continue
            c = first.int_value()
            if i + 1 >= n:
                break
            second = arr.get_object(i + 1)
            if isinstance(second, COSArray):
                # Form 1: c [w1 w2 w3 ...]
                for k in range(second.size()):
                    item = second.get_object(k)
                    if isinstance(item, COSNumber):
                        out[c + k] = item.float_value()
                i += 2
            elif isinstance(second, COSNumber):
                # Form 2: c1 c2 w
                if i + 2 >= n:
                    break
                third = arr.get_object(i + 2)
                if not isinstance(third, COSNumber):
                    i += 3
                    continue
                c2 = second.int_value()
                w = third.float_value()
                for cid in range(c, c2 + 1):
                    out[cid] = w
                i += 3
            else:
                i += 2

    # ---------- /DW2 + parsed /W2 (vertical metrics, §9.7.4.3) ----------

    def get_default_position_vector(self) -> tuple[float, float]:
        """Return ``(v_y, v_x)`` from ``/DW2``; defaults to ``(880, -1000)``.

        Note: ``/DW2`` per spec is ``[ position_vector_y displacement_vector_y ]``
        but is widely treated as ``(v_y, v_x)``. We return both values and
        leave interpretation to the caller. Default per spec is
        ``[880 -1000]``.
        """
        arr = self.get_dw2()
        if arr is None or arr.size() < 2:
            return (880.0, -1000.0)
        a = arr.get_object(0)
        b = arr.get_object(1)
        v_y = a.float_value() if isinstance(a, COSNumber) else 880.0
        v_x = b.float_value() if isinstance(b, COSNumber) else -1000.0
        return (v_y, v_x)

    def get_widths2(self) -> dict[int, tuple[float, float, float]]:
        """Parse ``/W2`` into ``CID -> (w1y, v_x, v_y)`` (1/1000 em).

        Per PDF 32000-1 §9.7.4.3 the ``/W2`` array uses two interleaved
        forms; each width entry is the triple ``[w1y v_x v_y]``:

        * ``c [w1y_1 v_x_1 v_y_1 w1y_2 v_x_2 v_y_2 ...]`` — consecutive
          CIDs starting at ``c`` get the successive triples.
        * ``c1 c2 w1y v_x v_y`` — every CID in ``c1..c2`` gets the same
          triple.

        Result is cached on first call.
        """
        if self._widths2 is not None:
            return self._widths2
        widths: dict[int, tuple[float, float, float]] = {}
        w2 = self.get_w2()
        if w2 is not None:
            self._parse_w2_array(w2, widths)
        self._widths2 = widths
        return widths

    @staticmethod
    def _parse_w2_array(
        arr: COSArray, out: dict[int, tuple[float, float, float]]
    ) -> None:
        i = 0
        n = arr.size()
        while i < n:
            first = arr.get_object(i)
            if not isinstance(first, COSNumber):
                i += 1
                continue
            c = first.int_value()
            if i + 1 >= n:
                break
            second = arr.get_object(i + 1)
            if isinstance(second, COSArray):
                # Form 1: c [w1y_1 v_x_1 v_y_1 w1y_2 v_x_2 v_y_2 ...]
                inner = second
                m = inner.size()
                k = 0
                while k + 2 < m:
                    a = inner.get_object(k)
                    b = inner.get_object(k + 1)
                    d = inner.get_object(k + 2)
                    if (
                        isinstance(a, COSNumber)
                        and isinstance(b, COSNumber)
                        and isinstance(d, COSNumber)
                    ):
                        out[c + (k // 3)] = (
                            a.float_value(),
                            b.float_value(),
                            d.float_value(),
                        )
                    k += 3
                i += 2
            elif isinstance(second, COSNumber):
                # Form 2: c1 c2 w1y v_x v_y
                if i + 4 >= n:
                    break
                third = arr.get_object(i + 2)
                fourth = arr.get_object(i + 3)
                fifth = arr.get_object(i + 4)
                if not (
                    isinstance(third, COSNumber)
                    and isinstance(fourth, COSNumber)
                    and isinstance(fifth, COSNumber)
                ):
                    i += 5
                    continue
                c2 = second.int_value()
                triple = (
                    third.float_value(),
                    fourth.float_value(),
                    fifth.float_value(),
                )
                for cid in range(c, c2 + 1):
                    out[cid] = triple
                i += 5
            else:
                i += 2

    # ---------- /CIDToGIDMap ----------

    def get_cid_to_gid_map(self) -> COSStream | str | None:
        """Return the ``/CIDToGIDMap`` entry.

        Per PDF 32000-1 §9.7.4.2 the value is either a stream of glyph
        indices or the name ``/Identity``. Returns the raw ``COSStream``,
        the name string, or ``None`` when absent.
        """
        v = self._dict.get_dictionary_object(_CID_TO_GID_MAP)
        if isinstance(v, COSStream):
            return v
        if isinstance(v, COSName):
            return v.name
        return None

    def set_cid_to_gid_map(self, value: COSStream | str | None) -> None:
        if value is None:
            self._dict.remove_item(_CID_TO_GID_MAP)
            return
        if isinstance(value, COSStream):
            self._dict.set_item(_CID_TO_GID_MAP, value)
            return
        if isinstance(value, str):
            self._dict.set_name(_CID_TO_GID_MAP, value)
            return
        raise TypeError(
            "set_cid_to_gid_map expects COSStream, str, or None; "
            f"got {type(value).__name__}"
        )

    # ---------- embedded font program ----------

    def is_embedded(self) -> bool:
        """``True`` when the descriptor carries a ``/FontFile``, ``/FontFile2``
        or ``/FontFile3`` stream. Mirrors upstream ``PDCIDFont.isEmbedded``.
        """
        fd = self.get_font_descriptor()
        if fd is None:
            return False
        return (
            fd.get_font_file() is not None
            or fd.get_font_file2() is not None
            or fd.get_font_file3() is not None
        )

    def get_program(self) -> bytes | None:
        """Decoded bytes of the embedded font program, or ``None`` if not
        embedded. Reads the first non-null stream from ``/FontFile``,
        ``/FontFile2``, then ``/FontFile3`` (the order PDFBox tries).
        """
        fd = self.get_font_descriptor()
        if fd is None:
            return None
        for getter in (fd.get_font_file, fd.get_font_file2, fd.get_font_file3):
            stream = getter()
            if stream is None:
                continue
            with stream.create_input_stream() as fh:
                return fh.read()
        return None

    # ---------- bounding box ----------

    def get_bounding_box(self) -> PDRectangle | None:
        """Return the descriptor's ``/FontBBox`` as a :class:`PDRectangle`.

        Mirrors upstream ``PDCIDFont.getBoundingBox`` when the bounding box
        is sourced from the descriptor; ``None`` when no descriptor / bbox
        is present. Returns ``None`` for malformed (non-4-entry) arrays.
        """
        fd = self.get_font_descriptor()
        if fd is None:
            return None
        bbox = fd.get_font_b_box()
        if bbox is None or bbox.size() < 4:
            return None
        try:
            return PDRectangle.from_cos_array(bbox)
        except (TypeError, ValueError):
            return None

    # ---------- average advance ----------

    def get_average_font_width(self) -> float:
        """Mean glyph advance across the parsed ``/W`` table, falling back
        to ``/DW`` when ``/W`` contributes no positive entries. Matches the
        scale upstream ``PDCIDFont.getAverageFontWidth`` returns (1/1000 em).
        """
        widths = self.get_widths()
        positive = [w for w in widths.values() if w > 0.0]
        if positive:
            return sum(positive) / len(positive)
        return float(self.get_default_width())

    # ---------- glyph queries ----------

    def has_glyph(self, cid: int) -> bool:
        """``True`` when ``cid`` resolves to a non-zero advance — either
        explicitly via ``/W`` or via a non-zero ``/DW`` fallback.
        """
        widths = self.get_widths()
        w = widths.get(cid)
        if w is not None:
            return w > 0.0
        return self.get_default_width() > 0.0

    # ---------- displacement / vertical metrics ----------

    def get_displacement(self, cid: int) -> tuple[float, float]:
        """Glyph displacement vector in em (1/1000 em scaled to em).

        Horizontal default: ``(width/1000, 0)``. Subclasses (or future
        vertical-writing wiring) may override.
        """
        return (self.get_glyph_width(cid) / 1000.0, 0.0)

    def get_position_vector(self, cid: int) -> tuple[float, float]:
        """Position vector ``(v_x, v_y)`` for ``cid`` in 1/1000 em.

        Looks up ``/W2`` triples ``(w1y, v_x, v_y)``; CIDs outside the
        table fall back to upstream's default-position-vector formula
        ``(width(cid)/2, dw2[0])`` — half the horizontal advance for
        ``v_x`` and ``/DW2``'s position-vector-y (defaulting to ``880``)
        for ``v_y``. Mirrors upstream
        ``PDCIDFont.getDefaultPositionVector`` /
        ``PDCIDFont.getPositionVector``.
        """
        triple = self.get_widths2().get(cid)
        if triple is not None:
            _, v_x, v_y = triple
            return (v_x, v_y)
        # /DW2 is [position_vector_y displacement_vector_y]; the upstream
        # default position vector is (widthForCID(cid)/2, dw2[0]).
        v_y_default, _ = self.get_default_position_vector()
        return (self.get_glyph_width(cid) / 2.0, v_y_default)

    def get_height(self, cid: int) -> float:
        """Vertical advance for ``cid`` (the ``w1y`` component of ``/W2``).

        Returns ``0.0`` when the font has no ``/W2`` entry for ``cid`` —
        matches PDFBox behaviour for horizontally-written CID fonts.
        """
        triple = self.get_widths2().get(cid)
        if triple is None:
            return 0.0
        return triple[0]

    # ---------- code -> CID ----------

    def code_to_cid(self, code: int) -> int:
        """Map a character code to a CID.

        For a bare ``PDCIDFont`` outside a Type0 parent, the code is the CID
        — there is no CMap to consult. Subclasses or the parent
        :class:`PDType0Font` perform the real mapping; this default keeps
        the upstream signature usable on either subtype.
        """
        return int(code)

    # ---------- code -> width (PDFontLike contract) ----------

    def get_width(self, code: int) -> float:
        """Width of the glyph for character ``code`` in 1/1000 em.

        Mirrors upstream ``PDCIDFont.getWidth(int code)``: resolves
        ``code -> CID`` via :meth:`code_to_cid`, then looks up the CID's
        advance through :meth:`get_glyph_width` (which honours ``/W``
        with ``/DW`` fallback). Surfaced separately from
        :meth:`get_glyph_width` because PDFBox callers commonly hold a
        character code rather than a CID.
        """
        return self.get_glyph_width(self.code_to_cid(code))

    def has_explicit_width(self, code: int) -> bool:
        """``True`` when ``code`` resolves to a CID that has its own
        entry in ``/W``. Mirrors upstream
        ``PDCIDFont.hasExplicitWidth(int code)``.

        Distinct from :meth:`has_glyph` — that method also returns
        ``True`` when only ``/DW`` makes the CID renderable. This one
        reports whether the ``/W`` table specifically carries the CID
        (the renderer uses it to decide whether to override embedded
        program widths per PDFBOX-563).
        """
        cid = self.code_to_cid(code)
        return cid in self.get_widths()

    # ---------- vertical displacement (PDF 32000-1 §9.7.4.3) ----------

    def get_vertical_displacement_vector_y(self, code: int) -> float:
        """``w1y`` — the y-component of the vertical displacement vector
        for ``code`` in 1/1000 em. Mirrors upstream
        ``PDCIDFont.getVerticalDisplacementVectorY(int code)``.

        Resolves ``code -> CID`` via :meth:`code_to_cid` and then looks
        up the CID in the parsed ``/W2`` table. CIDs absent from ``/W2``
        fall back to the ``displacementVectorY`` slot of ``/DW2``
        (which per spec defaults to ``-1000``).
        """
        cid = self.code_to_cid(code)
        triple = self.get_widths2().get(cid)
        if triple is not None:
            return triple[0]
        # /DW2 is [position_vector_y displacement_vector_y]; the second
        # entry is what we want here. get_default_position_vector
        # returns (v_y, v_x) — i.e. (position_vector_y, displacement_vector_y).
        _, displacement_vector_y = self.get_default_position_vector()
        return displacement_vector_y

    # ---------- /CIDToGIDMap binary parsing ----------

    def read_cid_to_gid_map(self) -> list[int] | None:
        """Decode the ``/CIDToGIDMap`` stream to a list of GIDs indexed
        by CID. Mirrors upstream ``PDCIDFont.readCIDToGIDMap``.

        Returns ``None`` when ``/CIDToGIDMap`` is absent or is the name
        ``/Identity`` (callers treat absence as identity per PDF 32000-1
        §9.7.4.2). The stream is a packed sequence of 16-bit
        big-endian unsigned GID words; trailing odd bytes are ignored
        the way the upstream loop ignores them.
        """
        v = self._dict.get_dictionary_object(_CID_TO_GID_MAP)
        if not isinstance(v, COSStream):
            return None
        with v.create_input_stream() as fh:
            raw = fh.read()
        n = len(raw) // 2
        result = [0] * n
        offset = 0
        for i in range(n):
            result[i] = (raw[offset] & 0xFF) << 8 | (raw[offset + 1] & 0xFF)
            offset += 2
        return result


__all__ = ["PDCIDFont"]
