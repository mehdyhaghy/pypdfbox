from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase, COSFloat

from .pd_function import PDFunction

_C0 = "C0"
_C1 = "C1"
_N = "N"


class PDFunctionType2(PDFunction):
    """
    Type 2 (exponential interpolation) function. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.common.function.PDFunctionType2``.

    The defining keys are ``/C0`` and ``/C1`` (output coefficient arrays)
    plus ``/N`` (the interpolation exponent). Per PDF 32000-1 §7.10.3,
    ``/C0`` defaults to ``[0]`` and ``/C1`` to ``[1]`` when absent.
    """

    def __init__(self, function: COSBase | None = None) -> None:
        super().__init__(function)

    def get_function_type(self) -> int:
        return 2

    # ---------- /C0 ----------

    def get_c0(self) -> list[float]:
        item = self.get_cos_object().get_dictionary_object(_C0)
        if isinstance(item, COSArray):
            return item.to_float_array()
        return [0.0]

    def set_c0(self, c0: list[float] | tuple[float, ...]) -> None:
        arr = COSArray()
        arr.set_float_array(c0)
        self.get_cos_object().set_item(_C0, arr)

    # ---------- /C1 ----------

    def get_c1(self) -> list[float]:
        item = self.get_cos_object().get_dictionary_object(_C1)
        if isinstance(item, COSArray):
            return item.to_float_array()
        return [1.0]

    def set_c1(self, c1: list[float] | tuple[float, ...]) -> None:
        arr = COSArray()
        arr.set_float_array(c1)
        self.get_cos_object().set_item(_C1, arr)

    # ---------- /N ----------

    def get_n(self) -> float:
        return self.get_cos_object().get_float(_N, 1.0)

    def set_n(self, n: float) -> None:
        self.get_cos_object().set_item(_N, COSFloat(n))


__all__ = ["PDFunctionType2"]
