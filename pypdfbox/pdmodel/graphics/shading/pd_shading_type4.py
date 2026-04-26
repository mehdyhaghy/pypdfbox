from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSStream

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

    def get_decode(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_DECODE)
        return v if isinstance(v, COSArray) else None

    def set_decode(self, decode: COSArray | None) -> None:
        if decode is None:
            self._dict.remove_item(_DECODE)
            return
        self._dict.set_item(_DECODE, decode)

    def get_function(self) -> COSBase | None:
        return self._dict.get_dictionary_object(_FUNCTION)

    def set_function(self, function: COSBase | None) -> None:
        if function is None:
            self._dict.remove_item(_FUNCTION)
            return
        self._dict.set_item(_FUNCTION, function)


__all__ = ["PDShadingType4"]
