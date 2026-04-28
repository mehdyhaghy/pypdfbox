from __future__ import annotations

from collections.abc import Iterable

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSStream

from .pd_shading import PDShading

_SHADING_TYPE: COSName = COSName.get_pdf_name("ShadingType")
_BITS_PER_COORDINATE: COSName = COSName.get_pdf_name("BitsPerCoordinate")
_BITS_PER_COMPONENT: COSName = COSName.get_pdf_name("BitsPerComponent")
_VERTICES_PER_ROW: COSName = COSName.get_pdf_name("VerticesPerRow")
_DECODE: COSName = COSName.get_pdf_name("Decode")
_FUNCTION: COSName = COSName.get_pdf_name("Function")


class PDShadingType5(PDShading):
    """Lattice-form Gouraud-shaded triangle mesh shading. Mirrors PDFBox
    ``PDShadingType5`` lite surface.

    Mesh-data decoding (lattice grid → triangles) is deferred until the
    rendering cluster lands.
    """

    def __init__(self, dictionary_or_stream: COSDictionary | None = None) -> None:
        if dictionary_or_stream is None:
            stream: COSStream = COSStream()
            stream.set_int(_SHADING_TYPE, PDShading.SHADING_TYPE5)
            super().__init__(stream)
        else:
            super().__init__(dictionary_or_stream)

    def get_shading_type(self) -> int:
        return PDShading.SHADING_TYPE5

    def get_bits_per_coordinate(self) -> int:
        return self._dict.get_int(_BITS_PER_COORDINATE)

    def set_bits_per_coordinate(self, bits: int) -> None:
        self._dict.set_int(_BITS_PER_COORDINATE, bits)

    def get_bits_per_component(self) -> int:
        return self._dict.get_int(_BITS_PER_COMPONENT)

    def set_bits_per_component(self, bits: int) -> None:
        self._dict.set_int(_BITS_PER_COMPONENT, bits)

    def get_vertices_per_row(self) -> int:
        return self._dict.get_int(_VERTICES_PER_ROW)

    def set_vertices_per_row(self, vertices: int) -> None:
        self._dict.set_int(_VERTICES_PER_ROW, vertices)

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

    def get_function(self):
        from pypdfbox.pdmodel.common.function import PDFunction

        item = self._dict.get_dictionary_object(_FUNCTION)
        if item is None:
            return None
        return PDFunction.create(item)

    def set_function(self, value) -> None:
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


__all__ = ["PDShadingType5"]
