from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName

from .pd_shading import PDShading

_SHADING_TYPE: COSName = COSName.get_pdf_name("ShadingType")
_DOMAIN: COSName = COSName.get_pdf_name("Domain")
_MATRIX: COSName = COSName.get_pdf_name("Matrix")
_FUNCTION: COSName = COSName.get_pdf_name("Function")


class PDShadingType1(PDShading):
    """Function-based shading. Mirrors PDFBox ``PDShadingType1`` lite surface.

    Function evaluation is deferred until the function module lands.
    """

    def __init__(self, dictionary_or_stream: COSDictionary | None = None) -> None:
        super().__init__(dictionary_or_stream)
        if dictionary_or_stream is None:
            self._dict.set_int(_SHADING_TYPE, PDShading.SHADING_TYPE1)

    def get_shading_type(self) -> int:
        return PDShading.SHADING_TYPE1

    def get_domain(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_DOMAIN)
        return v if isinstance(v, COSArray) else None

    def set_domain(self, domain: COSArray | None) -> None:
        if domain is None:
            self._dict.remove_item(_DOMAIN)
            return
        self._dict.set_item(_DOMAIN, domain)

    def get_matrix(self) -> COSArray | None:
        v = self._dict.get_dictionary_object(_MATRIX)
        return v if isinstance(v, COSArray) else None

    def set_matrix(self, matrix: COSArray | None) -> None:
        if matrix is None:
            self._dict.remove_item(_MATRIX)
            return
        self._dict.set_item(_MATRIX, matrix)

    def get_function(self) -> COSBase | None:
        return self._dict.get_dictionary_object(_FUNCTION)

    def set_function(self, function: COSBase | None) -> None:
        if function is None:
            self._dict.remove_item(_FUNCTION)
            return
        self._dict.set_item(_FUNCTION, function)


__all__ = ["PDShadingType1"]
