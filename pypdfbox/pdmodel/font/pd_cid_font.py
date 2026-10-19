from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSName,
    COSNumber,
    COSObject,
    COSStream,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

from .pd_cid_system_info import PDCIDSystemInfo
from .vertical_displacement_range import VerticalDisplacementRange

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_resource_cache import PDResourceCache

    from .pd_font_descriptor import PDFontDescriptor
    from .pd_type0_font import PDType0Font

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_FONT: COSName = COSName.get_pdf_name("Font")
_BASE_FONT: COSName = COSName.get_pdf_name("BaseFont")
_FONT_DESCRIPTOR: COSName = COSName.get_pdf_name("FontDescriptor")
_CID_SYSTEM_INFO: COSName = COSName.get_pdf_name("CIDSystemInfo")
_DW: COSName = COSName.get_pdf_name("DW")
_DW2: COSName = COSName.get_pdf_name("DW2")
_W: COSName = COSName.get_pdf_name("W")
_W2: COSName = COSName.get_pdf_name("W2")
_CID_TO_GID_MAP: COSName = COSName.get_pdf_name("CIDToGIDMap")
_IDENTITY: COSName = COSName.get_pdf_name("Identity")
_DEFAULT_FONT_MATRIX: tuple[float, ...] = (0.001, 0.0, 0.0, 0.001, 0.0, 0.0)


class PDCIDFont:
    """Abstract CIDFont wrapper. Mirrors PDFBox ``PDCIDFont``.

    A CIDFont is the descendant of a composite ``PDType0Font``; although its
    ``/Type`` is ``/Font`` it is not directly usable as a font. Concrete
    subclasses (``PDCIDFontType0``, ``PDCIDFontType2``) set ``/Subtype``.

    Mirrors upstream trunk (PDFBOX-6175): the class implements only
    ``COSObjectable`` (structurally, through :meth:`get_cos_object`) and is
    *not* a :class:`~pypdfbox.pdmodel.font.pd_font.PDFont` /
    ``PDFontLike``. It holds no reference to its parent Type 0 font, so a
    single instance can be shared by several Type 0 fonts through the
    document :class:`~pypdfbox.pdmodel.pd_resource_cache.PDResourceCache`.
    Every per-glyph method therefore takes the parent
    :class:`~pypdfbox.pdmodel.font.pd_type0_font.PDType0Font` as an explicit
    ``parent`` argument; callers normally go through the parent font
    instead, which passes itself. Upstream declares those methods
    ``protected``; pypdfbox keeps them public so the parent (a different
    module) can call them. ``parent`` may be ``None`` for a bare descendant
    (unit tests), in which case the character code is taken as the CID.

    Besides the upstream surface this wrapper exposes the COS-level
    accessors over the dictionary entries enumerated in PDF 32000-1 §9.7.4
    plus parsing of the ``/W`` and ``/W2`` width tables (§9.7.4.3).
    """

    SUB_TYPE: str | None = None

    def __init__(
        self,
        font_dict: COSDictionary | None = None,
        resource_cache: PDResourceCache | None = None,
    ) -> None:
        from .pd_font import PDFont

        if isinstance(resource_cache, PDFont):
            raise TypeError(
                "PDCIDFont: the second argument is a resource cache; the "
                "parent Type 0 font is no longer passed to the descendant "
                "(PDFBOX-6175)"
            )
        self._dict = font_dict if font_dict is not None else COSDictionary()
        if self._dict.get_dictionary_object(_TYPE) is None:
            self._dict.set_item(_TYPE, _FONT)
        if font_dict is None and self.SUB_TYPE is not None:
            self._dict.set_name(_SUBTYPE, self.SUB_TYPE)
        # ResourceCache, can be ``None``. Mirrors the second argument of
        # upstream trunk's ``PDCIDFont(COSDictionary, ResourceCache)``
        # (PDFBOX-6175, bf37c60d): an indirect /FontDescriptor is shared
        # through the cache (see :meth:`get_font_descriptor`).
        self._resource_cache = resource_cache
        # Lazy caches for parsed /W and /W2 tables (PDF 32000-1 §9.7.4.3).
        self._widths: dict[int, float] | None = None
        # /W2 individual values (``c [w1y v_x v_y ...]`` form)
        self._widths2: dict[int, tuple[float, float, float]] | None = None
        # /W2 cid-ranges (``c1 c2 w1y v_x v_y`` form), stored compactly
        # instead of expanded per CID (PDFBOX-6175, bcf78963).
        self._w2_ranges: list[VerticalDisplacementRange] | None = None

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        """Return the CIDFont dictionary. Mirrors upstream
        ``PDCIDFont.getCOSObject``."""
        return self._dict

    # ---------- subtype (abstract) ----------

    def get_subtype(self) -> str | None:  # pragma: no cover - overridden
        raise NotImplementedError("PDCIDFont subclasses must implement get_subtype()")

    # ---------- font identity ----------

    def get_base_font(self) -> str | None:
        """``/BaseFont`` — the PostScript name of the CIDFont.

        Mirrors upstream ``PDCIDFont.getBaseFont``. Upstream trunk dropped
        ``getName`` together with the ``PDFontLike`` interface
        (PDFBOX-6175); this is the only name accessor.
        """
        return self._dict.get_name_as_string(_BASE_FONT)

    # ---------- /FontDescriptor ----------

    def get_font_descriptor(self) -> PDFontDescriptor | None:
        """Return the font descriptor, may be ``None``.

        Mirrors upstream trunk ``PDCIDFont.getFontDescriptor`` (PDFBOX-6175,
        bf37c60d): when a resource cache was supplied at construction time
        and ``/FontDescriptor`` is an *indirect* reference, the wrapper is
        shared through the cache. Otherwise a fresh wrapper over the live
        dictionary is returned on each call (pypdfbox descriptors are
        stateless wrappers, so mutations of ``/FontDescriptor`` stay
        visible).
        """
        from .pd_font_descriptor import PDFontDescriptor

        cache = self._resource_cache
        fd_indirect = self._dict.get_item(_FONT_DESCRIPTOR)
        if not isinstance(fd_indirect, COSObject):
            fd_indirect = None
        if fd_indirect is not None and cache is not None:
            cached = cache.get_font_descriptor(fd_indirect)
            if cached is not None:
                return cached
        fd = self._dict.get_dictionary_object(_FONT_DESCRIPTOR)
        if not isinstance(fd, COSDictionary):
            return None
        descriptor = PDFontDescriptor(fd)
        if cache is not None and fd_indirect is not None:
            cache.put_font_descriptor(fd_indirect, descriptor)
        return descriptor

    def set_font_descriptor(self, font_descriptor: PDFontDescriptor | None) -> None:
        """Write ``/FontDescriptor`` (``None`` removes it). pypdfbox
        convenience; upstream has no setter."""
        if font_descriptor is None:
            self._dict.remove_item(_FONT_DESCRIPTOR)
            return
        self._dict.set_item(_FONT_DESCRIPTOR, font_descriptor.get_cos_object())

    # ---------- font matrix ----------

    def get_font_matrix(self) -> Any:
        """Return the font matrix (glyph space to text space).

        Upstream declares ``getFontMatrix`` ``protected abstract``; the
        concrete subtypes override. The base returns the 1000-unit default
        so a bare wrapper stays usable in tests.
        """
        return list(_DEFAULT_FONT_MATRIX)

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

    def set_dw(self, width: int | None) -> None:
        """Set ``/DW`` (default glyph width). Passing ``None`` removes the
        entry, restoring the spec-default of ``1000``.
        """
        if width is None:
            self._dict.remove_item(_DW)
            return
        self._dict.set_int(_DW, int(width))

    def has_dw(self) -> bool:
        """``True`` when ``/DW`` is present on the dictionary. Useful to
        distinguish an explicit ``1000`` from the spec-default fallback.
        """
        return self._dict.contains_key(_DW)

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
        self._widths = None
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
        self._widths2 = None
        self._w2_ranges = None
        if arr is None:
            self._dict.remove_item(_W2)
            return
        self._dict.set_item(_W2, arr)

    # ---------- parsed width tables (PDF 32000-1 §9.7.4.3) ----------

    def get_default_width(self) -> float:
        """Return ``/DW`` as a float, defaulting to 1000 per the spec."""
        return self._dict.get_float(_DW, 1000.0)

    def get_widths(self) -> dict[int, float]:  # type: ignore[override]
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

    def get_width_for_cid(self, cid: int) -> float:
        """Mirrors upstream ``PDCIDFont.getWidthForCID(int cid)`` — returns
        the parsed ``/W`` advance for ``cid`` (1/1000 em), falling back to
        ``/DW`` when ``/W`` does not cover the CID. Direct counterpart to
        :meth:`get_width`'s pre-CMap input variant; functionally identical
        to :meth:`get_glyph_width` and provided for upstream-call-site
        compatibility.
        """
        return self.get_glyph_width(cid)

    def read_widths(self) -> dict[int, float]:
        """Force-parse ``/W`` and refresh the cached ``CID -> width`` map.

        Mirrors upstream ``PDCIDFont.readWidths()`` (private — invoked from
        the constructor) but exposes a snake_case method on the Python
        side so callers that mutate ``/W`` directly on the dictionary can
        re-prime the lazy width cache without going through the
        :meth:`set_w` setter. Returns the freshly-parsed map.
        """
        widths: dict[int, float] = {}
        w = self.get_w()
        if w is not None:
            self._parse_w_array(w, widths)
        self._widths = widths
        return widths

    def read_vertical_displacements(
        self,
    ) -> dict[int, tuple[float, float, float]]:
        """Force-parse ``/W2`` and refresh the cached ``CID -> (w1y, v_x, v_y)``
        map. Mirrors upstream ``PDCIDFont.readVerticalDisplacements()``.

        As with :meth:`read_widths`, exposes the upstream parser so callers
        that mutate ``/W2`` directly on the dictionary can rebuild the
        cache without going through :meth:`set_w2`. Returns the
        freshly-parsed map.
        """
        widths: dict[int, tuple[float, float, float]] = {}
        ranges: list[VerticalDisplacementRange] = []
        w2 = self.get_w2()
        if w2 is not None:
            self._parse_w2_array(w2, widths, ranges)
        self._widths2 = widths
        self._w2_ranges = ranges
        return widths

    def clear_widths_cache(self) -> None:
        """Drop cached parsed ``/W`` and ``/W2`` tables."""
        self._widths = None
        self._widths2 = None
        self._w2_ranges = None

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

    def get_dw2_position_vector_y(self) -> float:
        """Return the position-vector-y component of ``/DW2`` (its first
        entry per PDF 32000-1 §9.7.4.3); defaults to ``880`` when ``/DW2``
        is absent or malformed.
        """
        v_y, _ = self.get_default_position_vector()
        return v_y

    def get_dw2_displacement_vector_y(self) -> float:
        """Return the displacement-vector-y component of ``/DW2`` (its
        second entry per PDF 32000-1 §9.7.4.3); defaults to ``-1000`` when
        ``/DW2`` is absent or malformed.
        """
        _, displacement_y = self.get_default_position_vector()
        return displacement_y

    def get_default_position_vector_for_cid(self, cid: int) -> tuple[float, float]:
        """Return the per-CID default position vector ``(v_x, v_y)``.

        Mirrors upstream ``PDCIDFont.getDefaultPositionVector(int cid)``:
        ``v_x = widthForCID(cid) / 2`` and ``v_y = dw2[0]`` (the
        position-vector-y from ``/DW2``, defaulting to ``880``). Used as
        the fallback in :meth:`get_position_vector` when ``/W2`` doesn't
        cover ``cid``.
        """
        return (self.get_glyph_width(cid) / 2.0, self.get_dw2_position_vector_y())

    def get_widths2(self) -> dict[int, tuple[float, float, float]]:
        """Parse ``/W2`` into ``CID -> (w1y, v_x, v_y)`` (1/1000 em).

        Per PDF 32000-1 §9.7.4.3 the ``/W2`` array uses two interleaved
        forms; each width entry is the triple ``[w1y v_x v_y]``:

        * ``c [w1y_1 v_x_1 v_y_1 w1y_2 v_x_2 v_y_2 ...]`` — consecutive
          CIDs starting at ``c`` get the successive triples.
        * ``c1 c2 w1y v_x v_y`` — every CID in ``c1..c2`` gets the same
          triple.

        Result is cached on first call. Only the individual (array-form)
        entries are returned: range-form entries are kept compactly as
        :class:`VerticalDisplacementRange` records and consulted by the
        lookup helpers after the individual values, exactly like upstream
        (PDFBOX-6175, bcf78963, "store cid ranges more compact").
        """
        if self._widths2 is not None:
            return self._widths2
        widths: dict[int, tuple[float, float, float]] = {}
        ranges: list[VerticalDisplacementRange] = []
        w2 = self.get_w2()
        if w2 is not None:
            self._parse_w2_array(w2, widths, ranges)
        self._widths2 = widths
        self._w2_ranges = ranges
        return widths

    def get_vertical_displacement_ranges(self) -> list[VerticalDisplacementRange]:
        """Return the compact ``/W2`` cid-ranges (``c1 c2 w1y v_x v_y``
        entries) in array order. Upstream keeps them in the private
        ``displacementRanges`` list (PDFBOX-6175, bcf78963)."""
        self.get_widths2()
        return list(self._w2_ranges or [])

    def _get_w2_metrics(self, cid: int) -> tuple[float, float, float] | None:
        """Return ``/W2`` metrics ``(w1y, v_x, v_y)`` for ``cid``.

        Individual values win; otherwise the first matching cid-range is
        used, mirroring upstream's ``displacementRanges.stream().filter(
        vdr -> vdr.rangeMatches(cid)).findFirst()``."""
        triple = self.get_widths2().get(cid)
        if triple is not None:
            return triple
        if self._w2_ranges is None:
            return None
        for vd_range in self._w2_ranges:
            if vd_range.range_matches(cid):
                v_x, v_y = vd_range.get_position_vector()
                return (vd_range.get_vertical_displacement(), v_x, v_y)
        return None

    @staticmethod
    def _parse_w2_array(
        arr: COSArray,
        out: dict[int, tuple[float, float, float]],
        ranges: list[VerticalDisplacementRange],
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
                # cid-range: stored compactly, never expanded per CID
                # (PDFBOX-6175, bcf78963)
                ranges.append(
                    VerticalDisplacementRange(
                        c,
                        second.int_value(),
                        (fourth.float_value(), fifth.float_value()),
                        third.float_value(),
                    )
                )
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

    def has_cid_to_gid_map_stream(self) -> bool:
        """``True`` when ``/CIDToGIDMap`` is a stream (i.e. an explicit
        CID-to-GID lookup table is present). Mirrors the upstream check
        used by ``PDCIDFontType2.codeToGID``.
        """
        v = self._dict.get_dictionary_object(_CID_TO_GID_MAP)
        return isinstance(v, COSStream)

    def is_identity_cid_to_gid_map(self) -> bool:
        """``True`` when ``/CIDToGIDMap`` is the name ``/Identity`` *or*
        absent. Per PDF 32000-1 §9.7.4.2 a missing entry is treated as
        ``Identity``, so this predicate covers both cases.
        """
        v = self._dict.get_dictionary_object(_CID_TO_GID_MAP)
        if v is None:
            return True
        return isinstance(v, COSName) and v.name == "Identity"

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

    # ---------- damage state ----------

    def is_damaged(self) -> bool:
        """``True`` when the embedded font file is damaged. Mirrors upstream
        ``PDCIDFont.isDamaged``; the concrete subtypes override after their
        parse step."""
        return False

    # ---------- per-glyph queries (parent passed explicitly) ----------
    #
    # Upstream trunk (PDFBOX-6175) removed the parent Type 0 font from
    # PDCIDFont; these protected methods take it as an argument instead.

    def get_hinted_normalized_path(
        self, code: int, ppem: int, parent: PDType0Font | None
    ) -> list[tuple] | None:
        """Hinted normalized outline for ``code`` at ``ppem``; ``None`` here.

        Mirrors upstream trunk ``PDCIDFont.getHintedNormalizedPath(int, int,
        PDType0Font)``: only a descendant with embedded TrueType outlines
        can hint (:class:`PDCIDFontType2` overrides), so callers use the
        unhinted normalized path.
        """
        return None

    def has_glyph(self, code: int, parent: PDType0Font | None) -> bool:
        """``True`` when ``code`` resolves to a CID with a non-zero advance —
        either explicitly via ``/W`` or via a non-zero ``/DW`` fallback.

        Upstream declares ``hasGlyph(int, PDType0Font)`` abstract; this base
        heuristic serves a bare wrapper. The concrete subtypes override.
        """
        cid = self.code_to_cid(code, parent)
        widths = self.get_widths()
        w = widths.get(cid)
        if w is not None:
            return w > 0.0
        return self.get_default_width() > 0.0

    # ---------- displacement / vertical metrics ----------

    def get_displacement(self, cid: int) -> tuple[float, float]:
        """Glyph displacement vector for ``cid`` in em (1/1000 em scaled to
        em). Horizontal default ``(width/1000, 0)``. pypdfbox helper; no
        upstream counterpart on the descendant."""
        return (self.get_glyph_width(cid) / 1000.0, 0.0)

    def get_position_vector(
        self, code: int, parent: PDType0Font | None
    ) -> tuple[float, float]:
        """Position vector ``(v_x, v_y)`` for character ``code`` in 1/1000 em.

        Mirrors upstream trunk ``PDCIDFont.getPositionVector(int,
        PDType0Font)``: resolves ``code -> CID`` through the parent, then
        looks up the per-CID ``/W2`` values, then the first matching
        ``/W2`` cid-range, and finally falls back to the default position
        vector ``(widthForCID(cid)/2, dw2[0])``.
        """
        cid = self.code_to_cid(code, parent)
        triple = self._get_w2_metrics(cid)
        if triple is not None:
            _, v_x, v_y = triple
            return (v_x, v_y)
        # /DW2 is [position_vector_y displacement_vector_y]; the upstream
        # default position vector is (widthForCID(cid)/2, dw2[0]).
        return self.get_default_position_vector_for_cid(cid)

    def get_height(self, code: int, parent: PDType0Font | None) -> float:
        """Height of the glyph for ``code`` (approximate, deprecated
        upstream). Mirrors upstream trunk ``PDCIDFont.getHeight(int,
        PDType0Font)``, which is abstract; this base returns the ``w1y``
        component of ``/W2`` for the resolved CID, or ``0.0`` when the font
        has no ``/W2`` entry for it. The concrete subtypes override.
        """
        return self._get_height_for_cid(self.code_to_cid(code, parent))

    def _get_height_for_cid(self, cid: int) -> float:
        """``w1y`` of ``/W2`` for ``cid``; ``0.0`` when not covered."""
        triple = self._get_w2_metrics(cid)
        if triple is None:
            return 0.0
        return triple[0]

    # ---------- code -> CID ----------

    @abstractmethod
    def code_to_cid(self, code: int, parent: PDType0Font | None) -> int:
        """Map a character code to a CID through the parent's encoding CMap.

        Mirrors upstream trunk ``PDCIDFont.codeToCID(int, PDType0Font)`` —
        abstract on the Java side and overridden by :class:`PDCIDFontType0`
        and :class:`PDCIDFontType2`. The base implementation here is an
        identity fallback (the code is the CID) used when an un-subtyped
        :class:`PDCIDFont` is wrapped directly for tests.
        """
        return int(code)

    # ---------- code -> GID (abstract) ----------

    @abstractmethod
    def code_to_gid(self, code: int, parent: PDType0Font | None) -> int:
        """Map a character code to a glyph index.

        Mirrors upstream trunk ``PDCIDFont.codeToGID(int, PDType0Font)``
        (Java ``abstract``). Subclasses override. Bare ``PDCIDFont``
        instances raise ``NotImplementedError``.
        """
        raise NotImplementedError(
            "PDCIDFont.code_to_gid is abstract; "
            "subclasses (PDCIDFontType0 / PDCIDFontType2) must override."
        )

    # ---------- encoding (abstract) ----------

    @abstractmethod
    def encode_glyph_id(self, glyph_id: int) -> bytes:
        """Encode a glyph index as its content-stream byte representation.

        Mirrors upstream ``PDCIDFont.encodeGlyphId(int glyphId)`` (Java
        ``abstract``). The encoding is the big-endian 16-bit GID for
        :class:`PDCIDFontType2` and is unsupported for
        :class:`PDCIDFontType0`.
        """
        raise NotImplementedError(
            "PDCIDFont.encode_glyph_id is abstract; "
            "subclasses must override."
        )

    def encode(self, unicode_codepoint: int, parent: PDType0Font | None) -> bytes:
        """Encode a Unicode codepoint as PDF content-stream bytes.

        Mirrors upstream trunk ``PDCIDFont.encode(int, PDType0Font)``. Used
        during embedding / form-field filling; :class:`PDCIDFontType2`
        overrides and :class:`PDCIDFontType0` raises.
        """
        raise NotImplementedError(
            "PDCIDFont.encode is abstract; subclasses must override."
        )

    # ---------- code -> width ----------

    def get_width(self, code: int, parent: PDType0Font | None) -> float:
        """Width of the glyph for character ``code`` in 1/1000 em.

        Mirrors upstream trunk ``PDCIDFont.getWidth(int, PDType0Font)``:
        resolves ``code -> CID`` through the parent, then looks up the
        CID's advance through :meth:`get_glyph_width` (``/W`` with ``/DW``
        fallback). These widths are supposed to be consistent with the
        actual widths given in the CIDFont program, but PDFBOX-563 shows
        that when they are not, Acrobat overrides the embedded font widths
        with the widths given in the font dictionary.

        Upstream memoises the result per code on the descendant
        (``codeToWidth``); pypdfbox keeps that memo on the parent
        :class:`PDType0Font` instead, because a shared descendant may serve
        parents whose encoding CMaps map the same code to different CIDs.
        """
        return self.get_glyph_width(self.code_to_cid(code, parent))

    def has_explicit_width(self, code: int, parent: PDType0Font | None) -> bool:
        """``True`` when ``code`` resolves to a CID that has its own entry
        in ``/W``. Mirrors upstream trunk ``PDCIDFont.hasExplicitWidth(int,
        PDType0Font)``.
        """
        cid = self.code_to_cid(code, parent)
        return cid in self.get_widths()

    def get_width_from_font(self, code: int, parent: PDType0Font | None) -> float:
        """Width of the glyph in the font program, in glyph space. Upstream
        trunk declares ``getWidthFromFont(int, PDType0Font)`` abstract; the
        base has no program and returns ``0.0``."""
        return 0.0

    def get_path(self, code: int, parent: PDType0Font | None) -> list[tuple]:
        """Glyph path for ``code``. Upstream trunk declares
        ``getPath(int, PDType0Font)`` abstract; the base has no program and
        returns an empty path."""
        return []

    def get_normalized_path(
        self, code: int, parent: PDType0Font | None
    ) -> list[tuple]:
        """Normalized glyph path for ``code``. Upstream trunk declares
        ``getNormalizedPath(int, PDType0Font)`` abstract; the base has no
        program and returns an empty path."""
        return []

    # ---------- vertical displacement (PDF 32000-1 §9.7.4.3) ----------

    def get_vertical_displacement_vector_y(
        self, code: int, parent: PDType0Font | None
    ) -> float:
        """``w1y`` — the y-component of the vertical displacement vector
        for ``code`` in 1/1000 em. Mirrors upstream trunk
        ``PDCIDFont.getVerticalDisplacementVectorY(int, PDType0Font)``.

        Resolves ``code -> CID`` through the parent, then looks up the
        per-CID ``/W2`` values and the ``/W2`` cid-ranges. CIDs absent from
        ``/W2`` fall back to the ``displacementVectorY`` slot of ``/DW2``
        (which per spec defaults to ``-1000``).
        """
        cid = self.code_to_cid(code, parent)
        triple = self._get_w2_metrics(cid)
        if triple is not None:
            return triple[0]
        # /DW2 is [position_vector_y displacement_vector_y]; the second
        # entry is what we want here.
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
