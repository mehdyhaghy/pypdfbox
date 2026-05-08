from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSStream

from .pd_shading import PDShading

if TYPE_CHECKING:
    from pypdfbox.pdmodel.common.function import PDFunction

_SHADING_TYPE: COSName = COSName.get_pdf_name("ShadingType")
_BITS_PER_COORDINATE: COSName = COSName.get_pdf_name("BitsPerCoordinate")
_BITS_PER_COMPONENT: COSName = COSName.get_pdf_name("BitsPerComponent")
_BITS_PER_FLAG: COSName = COSName.get_pdf_name("BitsPerFlag")
_DECODE: COSName = COSName.get_pdf_name("Decode")
_FUNCTION: COSName = COSName.get_pdf_name("Function")


class PDShadingType7(PDShading):
    """Tensor-product patch mesh shading. Mirrors PDFBox ``PDShadingType7``
    lite surface.

    Per PDF 32000-1 §8.7.4.5.8 (Table 89), tensor-product patch mesh
    streams require ``/BitsPerCoordinate``, ``/BitsPerComponent``,
    ``/BitsPerFlag``, and ``/Decode``; ``/Function`` is optional. This
    wrapper preserves the encoded patch stream and exposes metadata only;
    decoding the 16 control points and colors into tensor-product patch
    geometry is deferred to rendering.
    """

    def __init__(self, dictionary_or_stream: COSDictionary | None = None) -> None:
        if dictionary_or_stream is None:
            stream: COSStream = COSStream()
            stream.set_int(_SHADING_TYPE, PDShading.SHADING_TYPE7)
            super().__init__(stream)
        else:
            super().__init__(dictionary_or_stream)

    def get_shading_type(self) -> int:
        return PDShading.SHADING_TYPE7

    # ---------- /BitsPerCoordinate ----------

    def get_bits_per_coordinate(self) -> int:
        """Returns ``/BitsPerCoordinate``. Per Table 89 the legal values are
        1, 2, 4, 8, 12, 16, 24, 32. Returns ``-1`` when the entry is absent
        (mirrors upstream's ``COSDictionary.getInt`` default)."""
        return self._dict.get_int(_BITS_PER_COORDINATE)

    def set_bits_per_coordinate(self, bits: int) -> None:
        self._dict.set_int(_BITS_PER_COORDINATE, bits)

    # ---------- /BitsPerComponent ----------

    def get_bits_per_component(self) -> int:
        """Returns ``/BitsPerComponent``. Per Table 89 the legal values are
        1, 2, 4, 8, 12, 16. Returns ``-1`` when the entry is absent."""
        return self._dict.get_int(_BITS_PER_COMPONENT)

    def set_bits_per_component(self, bits: int) -> None:
        self._dict.set_int(_BITS_PER_COMPONENT, bits)

    # ---------- /BitsPerFlag ----------

    def get_bits_per_flag(self) -> int:
        """Returns ``/BitsPerFlag``. Per Table 89 the legal values are
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
        try:
            return (float(lo.value), float(hi.value))  # type: ignore[union-attr]
        except (AttributeError, TypeError, ValueError):
            return None

    def get_number_of_color_components(self) -> int:
        """Return the number of color components for this shading.

        Mirrors upstream ``PDTriangleBasedShadingType.getNumberOfColorComponents``
        — when ``/Function`` is present the count is fixed at ``1``;
        otherwise it falls back to the color space's component count.
        Returns ``-1`` when neither is available."""
        if self._dict.get_dictionary_object(_FUNCTION) is not None:
            return 1
        cs = self.get_color_space()
        if cs is None:
            return -1
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


__all__ = ["PDShadingType7"]
