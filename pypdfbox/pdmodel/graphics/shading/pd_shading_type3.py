from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName

from .pd_shading import PDShading

_SHADING_TYPE: COSName = COSName.get_pdf_name("ShadingType")
_COORDS: COSName = COSName.get_pdf_name("Coords")
_DOMAIN: COSName = COSName.get_pdf_name("Domain")
_FUNCTION: COSName = COSName.get_pdf_name("Function")
_EXTEND: COSName = COSName.get_pdf_name("Extend")


class PDShadingType3(PDShading):
    """Radial shading. Mirrors PDFBox ``PDShadingType3`` lite surface.

    ``/Coords`` is a 6-element array ``[x0 y0 r0 x1 y1 r1]`` defining the
    starting and ending circles.
    """

    def __init__(self, dictionary_or_stream: COSDictionary | None = None) -> None:
        super().__init__(dictionary_or_stream)
        if dictionary_or_stream is None:
            self._dict.set_int(_SHADING_TYPE, PDShading.SHADING_TYPE3)

    def get_shading_type(self) -> int:
        return PDShading.SHADING_TYPE3

    def get_coords(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_COORDS)
        return v if isinstance(v, COSArray) else None

    def set_coords(self, coords: COSArray | None) -> None:
        if coords is None:
            self._dict.remove_item(_COORDS)
            return
        self._dict.set_item(_COORDS, coords)

    def get_domain(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_DOMAIN)
        return v if isinstance(v, COSArray) else None

    def set_domain(self, domain: COSArray | None) -> None:
        if domain is None:
            self._dict.remove_item(_DOMAIN)
            return
        self._dict.set_item(_DOMAIN, domain)

    def get_function(self) -> COSBase | None:
        return self._dict.get_dictionary_object(_FUNCTION)

    def set_function(self, function: COSBase | None) -> None:
        if function is None:
            self._dict.remove_item(_FUNCTION)
            return
        self._dict.set_item(_FUNCTION, function)

    def get_extend(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_EXTEND)
        return v if isinstance(v, COSArray) else None

    def set_extend(self, extend: COSArray | None) -> None:
        if extend is None:
            self._dict.remove_item(_EXTEND)
            return
        self._dict.set_item(_EXTEND, extend)


__all__ = ["PDShadingType3"]
