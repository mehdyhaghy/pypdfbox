from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSNumber, COSStream

from .pd_shading import PDShading

_SHADING_TYPE: COSName = COSName.get_pdf_name("ShadingType")
_BITS_PER_COORDINATE: COSName = COSName.get_pdf_name("BitsPerCoordinate")
_BITS_PER_COMPONENT: COSName = COSName.get_pdf_name("BitsPerComponent")
_BITS_PER_FLAG: COSName = COSName.get_pdf_name("BitsPerFlag")
_DECODE: COSName = COSName.get_pdf_name("Decode")
_FUNCTION: COSName = COSName.get_pdf_name("Function")


class PDShadingType4(PDShading):
    """Free-form Gouraud-shaded triangle mesh shading. Mirrors PDFBox
    ``PDShadingType4`` lite surface.

    Type 4 shadings are stream-based: the encoded triangle mesh lives in
    the stream body. Mesh-data decoding is deferred until the rendering
    cluster lands.
    """

    def __init__(self, dictionary_or_stream: COSDictionary | None = None) -> None:
        if dictionary_or_stream is None:
            stream: COSStream = COSStream()
            stream.set_int(_SHADING_TYPE, PDShading.SHADING_TYPE4)
            super().__init__(stream)
        else:
            super().__init__(dictionary_or_stream)

    def get_shading_type(self) -> int:
        return PDShading.SHADING_TYPE4

    def get_bits_per_coordinate(self) -> int:
        return self._dict.get_int(_BITS_PER_COORDINATE)

    def set_bits_per_coordinate(self, bits: int) -> None:
        self._dict.set_int(_BITS_PER_COORDINATE, bits)

    def get_bits_per_component(self) -> int:
        return self._dict.get_int(_BITS_PER_COMPONENT)

    def set_bits_per_component(self, bits: int) -> None:
        self._dict.set_int(_BITS_PER_COMPONENT, bits)

    def get_bits_per_flag(self) -> int:
        return self._dict.get_int(_BITS_PER_FLAG)

    def set_bits_per_flag(self, bits: int) -> None:
        self._dict.set_int(_BITS_PER_FLAG, bits)

    def get_decode(self) -> list[float] | None:
        v = self._dict.get_dictionary_object(_DECODE)
        if not isinstance(v, COSArray):
            return None
        return v.to_float_array()

    def set_decode(self, values: COSArray | Iterable[float] | None) -> None:
        if values is None:
            self._dict.remove_item(_DECODE)
            return
        if isinstance(values, COSArray):
            self._dict.set_item(_DECODE, values)
            return
        array = COSArray()
        array.set_float_array(values)
        self._dict.set_item(_DECODE, array)

    def get_decode_for_parameter(self, param_num: int) -> tuple[float, float] | None:
        """Return the decode ``(min, max)`` pair at index ``param_num`` from
        ``/Decode``, or ``None`` when ``/Decode`` is missing or too short.

        Mirrors upstream ``PDTriangleBasedShadingType.getDecodeForParameter``
        — index 0 is the x-coordinate range, 1 is the y-coordinate range,
        and ``2 + i`` is the i-th color component range. Each pair occupies
        two consecutive entries, so the array must have at least
        ``param_num * 2 + 2`` elements."""
        if param_num < 0:
            return None
        v = self._dict.get_dictionary_object(_DECODE)
        if not isinstance(v, COSArray):
            return None
        # Upstream's PDRange ctor reads positions 2*i and 2*i+1, so the
        # array must contain at least 2*param_num + 2 entries.
        needed = param_num * 2 + 2
        if v.size() < needed:
            return None
        lo = v.get_object(param_num * 2)
        hi = v.get_object(param_num * 2 + 1)
        if not isinstance(lo, COSNumber) or not isinstance(hi, COSNumber):
            return None
        return (lo.float_value(), hi.float_value())

    def get_number_of_color_components(self) -> int:
        """Return the number of color components for this shading.

        Mirrors upstream ``PDTriangleBasedShadingType.getNumberOfColorComponents``
        — when ``/Function`` is present, color values are produced by the
        function (single-input → ``n`` outputs), so the count is fixed at
        ``1`` from the mesh-stream's perspective; otherwise it falls back
        to the color space's component count. Returns ``-1`` when neither
        is available."""
        if self._dict.get_dictionary_object(_FUNCTION) is not None:
            return 1
        cs = self.get_color_space_object()
        if cs is None:
            cs = self.get_color_space()
        get_components = getattr(cs, "get_number_of_components", None)
        if callable(get_components):
            return int(get_components())
        return -1

    def get_function(self) -> Any:
        from pypdfbox.pdmodel.common.function import PDFunction

        item = self._dict.get_dictionary_object(_FUNCTION)
        if item is None:
            return None
        return PDFunction.create(item)

    def set_function(self, value: Any) -> None:
        from pypdfbox.pdmodel.common.function import PDFunction

        if value is None:
            self._dict.remove_item(_FUNCTION)
            return
        if isinstance(value, PDFunction):
            self._dict.set_item(_FUNCTION, value.get_cos_object())
            return
        if isinstance(value, COSBase):
            self._dict.set_item(_FUNCTION, value)
            return
        raise TypeError(
            "set_function expects PDFunction, COSDictionary, COSStream, "
            f"or None; got {type(value).__name__}"
        )

    # ---------- rendering hooks (lite-surface stubs) ----------

    def to_paint(self, matrix: Any = None) -> Any:
        """Return a Paint-equivalent for this free-form Gouraud-shaded
        triangle-mesh shading. Mirrors upstream
        ``PDShadingType4.toPaint(Matrix)`` (line 86), which constructs a
        ``Type4ShadingPaint(this, matrix)``.

        The pypdfbox renderer is Pillow-based, so the AWT ``Paint`` contract
        does not apply. Returning ``None`` matches the lite-surface
        convention used by the other shading types in this package: callers
        in the rendering cluster are expected to dispatch on
        ``get_shading_type()`` and materialize triangles via
        ``collect_triangles`` rather than via a Paint object."""
        return None

    def collect_triangles(
        self, xform: Any = None, matrix: Any = None
    ) -> list[Any]:
        """Decode the free-form mesh stream into a list of shaded triangles.
        Mirrors upstream ``PDShadingType4.collectTriangles`` (line 92).

        Free-form Gouraud (PDF 32000-1 §8.7.4.5.5): each vertex is preceded
        by a flag of ``/BitsPerFlag`` bits whose two least-significant bits
        select the topology. Flag ``0`` starts a new triangle (three fresh
        vertices follow); flags ``1`` and ``2`` extend the previous triangle
        by sharing two of its corners with the next vertex; any other value
        is treated as end-of-stream. Bits-per-flag must be 2, 4, or 8 per
        the spec, but upstream only masks the low two bits.

        The pypdfbox renderer is Pillow-based, so this lite-surface stub
        validates the prerequisite ``/Decode`` entries and returns an empty
        list — full mesh decoding is deferred until the rendering cluster
        lands. Returning an empty list is the same fallback upstream uses
        for missing/degenerate input."""
        # Backing object must be a stream — upstream returns
        # Collections.emptyList() when the dictionary isn't a COSStream
        # (line 99).
        if not isinstance(self._dict, COSStream):
            return []
        range_x = self.get_decode_for_parameter(0)
        range_y = self.get_decode_for_parameter(1)
        if range_x is None or range_y is None:
            return []
        if range_x[0] == range_x[1] or range_y[0] == range_y[1]:
            return []
        n = self.get_number_of_color_components()
        for i in range(n):
            if self.get_decode_for_parameter(2 + i) is None:
                # Upstream raises IOException("Range missing in shading
                # /Decode entry") at line 115; we mirror that contract by
                # raising OSError per the project's IOException -> OSError
                # convention.
                raise OSError("Range missing in shading /Decode entry")
        # Mesh decoding deferred to rendering cluster.
        return []


__all__ = ["PDShadingType4"]
