from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSNumber, COSStream

from .pd_shading import PDShading

if TYPE_CHECKING:
    from pypdfbox.pdmodel.common.function import PDFunction

_SHADING_TYPE: COSName = COSName.get_pdf_name("ShadingType")
_BITS_PER_COORDINATE: COSName = COSName.get_pdf_name("BitsPerCoordinate")
_BITS_PER_COMPONENT: COSName = COSName.get_pdf_name("BitsPerComponent")
_BITS_PER_FLAG: COSName = COSName.get_pdf_name("BitsPerFlag")
_DECODE: COSName = COSName.get_pdf_name("Decode")
_FUNCTION: COSName = COSName.get_pdf_name("Function")


class PDShadingType6(PDShading):
    """Coons patch mesh shading. Mirrors PDFBox ``PDShadingType6`` lite
    surface.

    Per PDF 32000-1 §8.7.4.5.7 (Table 88), Coons patch mesh streams require
    ``/BitsPerCoordinate``, ``/BitsPerComponent``, ``/BitsPerFlag``, and
    ``/Decode``; ``/Function`` is optional. This wrapper preserves the
    encoded patch stream and exposes metadata only; decoding control points
    and colors into Coons patch geometry is deferred to rendering.
    """

    def __init__(self, dictionary_or_stream: COSDictionary | None = None) -> None:
        if dictionary_or_stream is None:
            stream: COSStream = COSStream()
            stream.set_int(_SHADING_TYPE, PDShading.SHADING_TYPE6)
            super().__init__(stream)
        else:
            super().__init__(dictionary_or_stream)

    def get_shading_type(self) -> int:
        return PDShading.SHADING_TYPE6

    # ---------- /BitsPerCoordinate ----------

    def get_bits_per_coordinate(self) -> int:
        """Returns ``/BitsPerCoordinate``. Per Table 88 the legal values are
        1, 2, 4, 8, 12, 16, 24, 32. Returns ``-1`` when the entry is absent
        (mirrors upstream's ``COSDictionary.getInt`` default)."""
        return self._dict.get_int(_BITS_PER_COORDINATE)

    def set_bits_per_coordinate(self, bits: int) -> None:
        self._dict.set_int(_BITS_PER_COORDINATE, bits)

    # ---------- /BitsPerComponent ----------

    def get_bits_per_component(self) -> int:
        """Returns ``/BitsPerComponent``. Per Table 88 the legal values are
        1, 2, 4, 8, 12, 16. Returns ``-1`` when the entry is absent."""
        return self._dict.get_int(_BITS_PER_COMPONENT)

    def set_bits_per_component(self, bits: int) -> None:
        self._dict.set_int(_BITS_PER_COMPONENT, bits)

    # ---------- /BitsPerFlag ----------

    def get_bits_per_flag(self) -> int:
        """Returns ``/BitsPerFlag``. Per Table 88 the legal values are
        2, 4, 8. Returns ``-1`` when the entry is absent."""
        return self._dict.get_int(_BITS_PER_FLAG)

    def set_bits_per_flag(self, bits: int) -> None:
        self._dict.set_int(_BITS_PER_FLAG, bits)

    # ---------- /Decode ----------

    def get_decode(self) -> list[float] | None:
        """Returns ``/Decode`` as a flat ``list[float]`` of length
        ``2 * (2 + N)`` (xy pair + ``N`` color components, each ``min, max``).

        Returns ``None`` when ``/Decode`` is absent or the entry is not a
        ``COSArray``. The companion COSArray is reachable via
        ``get_cos_object().get_dictionary_object("Decode")`` for callers
        that need the indirect-ref-preserving form.
        """
        v = self._dict.get_dictionary_object(_DECODE)
        if not isinstance(v, COSArray):
            return None
        return v.to_float_array()

    def set_decode(self, values: COSArray | Iterable[float] | None) -> None:
        """Set ``/Decode``. Accepts a ``COSArray`` (stored as-is, preserving
        indirect references) or any iterable of floats (wrapped into a fresh
        ``COSArray`` of ``COSFloat`` entries). ``None`` removes the entry."""
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
        and ``2 + i`` is the i-th color component range."""
        if param_num < 0:
            return None
        v = self._dict.get_dictionary_object(_DECODE)
        if not isinstance(v, COSArray):
            return None
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
        — when ``/Function`` is present the count is fixed at ``1``;
        otherwise it falls back to the color space's component count.
        Returns ``-1`` when neither is available."""
        if self._dict.get_dictionary_object(_FUNCTION) is not None:
            return 1
        cs = self.get_color_space_object()
        if cs is None:
            cs = self.get_color_space()
        get_components = getattr(cs, "get_number_of_components", None)
        if callable(get_components):
            return int(get_components())
        return -1

    # ---------- /Function ----------

    def get_function(self) -> PDFunction | None:
        """Returns the ``/Function`` entry wrapped as a ``PDFunction``
        (dispatched on ``/FunctionType``), or ``None`` when ``/Function``
        is absent. Mirrors upstream ``PDShading.getFunction()`` which
        returns a ``PDFunction``."""
        from pypdfbox.pdmodel.common.function import PDFunction

        item = self._dict.get_dictionary_object(_FUNCTION)
        if item is None:
            return None
        return PDFunction.create(item)

    def set_function(self, value: PDFunction | COSBase | None) -> None:
        """Set ``/Function``. Accepts a ``PDFunction`` (its backing COS
        object is stored), a raw ``COSDictionary`` / ``COSStream``, or
        ``None`` to remove."""
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

    # Number of control points per Coons patch (PDF 32000-1 §8.7.4.5.7).
    _CONTROL_POINTS: int = 12

    def to_paint(self, matrix: Any = None) -> Any:
        """Return a Paint-equivalent for this Coons-patch shading. Mirrors
        upstream ``PDShadingType6.toPaint(Matrix)`` (line 50) which returns
        a ``Type6ShadingPaint(this, matrix)``.

        The pypdfbox renderer is Pillow / aggdraw-based, so the AWT Paint
        contract does not apply. Returning ``None`` matches the lite-surface
        convention used elsewhere in this package: callers in the rendering
        cluster are expected to dispatch on ``get_shading_type()`` and
        materialize patch geometry via ``generate_patch`` / the encoded
        stream rather than via a Paint object."""
        return None

    def generate_patch(
        self,
        points: Sequence[tuple[float, float]],
        color: Sequence[Sequence[float]],
    ) -> dict[str, Any]:
        """Build a single Coons-patch descriptor from 12 control points and
        4 corner colors. Mirrors upstream
        ``PDShadingType6.generatePatch(Point2D[], float[][])`` (line 56)
        which returns ``new CoonsPatch(points, color)``.

        Upstream ``CoonsPatch`` is an internal rendering helper (package-
        private). Until the rendering cluster lands, this method returns a
        dict carrying the raw control-points and corner-color arrays
        unchanged. Validates the 12-point arity per PDF 32000-1 §8.7.4.5.7."""
        pts = list(points)
        if len(pts) != self._CONTROL_POINTS:
            raise ValueError(
                f"Coons patch requires {self._CONTROL_POINTS} control points, "
                f"got {len(pts)}"
            )
        cols = [list(c) for c in color]
        if len(cols) != 4:
            raise ValueError(
                f"Coons patch requires 4 corner colors, got {len(cols)}"
            )
        return {"kind": "coons", "points": pts, "color": cols}

    def get_bounds(self, xform: Any = None, matrix: Any = None) -> Any:
        """Return the bounding rectangle of this shading's mesh, or ``None``
        when the bounds cannot be computed. Mirrors upstream
        ``PDShadingType6.getBounds(AffineTransform, Matrix)`` (line 62)
        which delegates to ``getBounds(xform, matrix, 12)`` on the abstract
        ``PDMeshBasedShadingType`` parent.

        Bounds computation requires walking the encoded patch stream and
        triangulating each Coons patch — that work belongs to the rendering
        cluster (Pillow / aggdraw-based). Returns ``None`` until then,
        matching the base ``PDShading.get_bounds`` lite-surface contract."""
        return None

    # ---------- patch-stream decode ----------

    def parse_patches(
        self,
        stream_bytes: bytes | bytearray | memoryview | None = None,
    ) -> list[Any]:
        """Decode the Coons-patch mesh stream into a list of geometry-only
        :class:`ParsedPatch` records (12 control points + 4 corner-colour
        vectors per patch).

        When ``stream_bytes`` is ``None`` the encoded body is fetched from
        the backing ``COSStream`` (this shading's own ``/Filter`` chain is
        applied, so the caller does not need to decode FlateDecode etc.
        themselves). Returns an empty list when the backing object is not
        a ``COSStream`` or the ``/Decode`` array is missing.

        Mirrors upstream ``PDMeshBasedShadingType.collectPatches`` (Java)
        with the user-space → device-space transform stripped out — that
        belongs to the renderer. Per-vertex colour interpolation through
        ``/Function`` is also deferred (the renderer can apply it to the
        4 corner colours after this method returns).
        """
        if stream_bytes is None:
            cos = self.get_cos_object()
            if not isinstance(cos, COSStream):
                return []
            with cos.create_input_stream() as src:
                stream_bytes = src.read()
        decode = self.get_decode()
        if decode is None:
            return []
        ncc = self.get_number_of_color_components()
        if ncc <= 0:
            return []
        from .pd_mesh_based_shading_type import parse_patch_stream

        return parse_patch_stream(
            stream_bytes,
            bits_per_coordinate=self.get_bits_per_coordinate(),
            bits_per_component=self.get_bits_per_component(),
            bits_per_flag=self.get_bits_per_flag(),
            decode=decode,
            num_color_components=ncc,
            control_points=self._CONTROL_POINTS,
        )


__all__ = ["PDShadingType6"]
