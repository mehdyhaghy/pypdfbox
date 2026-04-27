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
        """Return ``/C0`` as a Python list of floats. Defaults to ``[0.0]``
        when the key is absent, per PDF 32000-1 §7.10.3."""
        item = self.get_cos_object().get_dictionary_object(_C0)
        if isinstance(item, COSArray):
            return item.to_float_array()
        return [0.0]

    def get_c0_array(self) -> COSArray:
        """Return the underlying ``/C0`` ``COSArray``, materialising the
        spec default ``[0.0]`` when the key is absent.

        Mirrors upstream ``PDFunctionType2.getC0()`` which returns a
        ``COSArray`` directly. We keep both the list-returning ``get_c0``
        (Pythonic, the longstanding API in this port) and this
        array-returning variant for callers that need to mutate the
        underlying COS object in place.
        """
        item = self.get_cos_object().get_dictionary_object(_C0)
        if isinstance(item, COSArray):
            return item
        default = COSArray()
        default.set_float_array([0.0])
        return default

    def set_c0(self, c0: list[float] | tuple[float, ...] | COSArray) -> None:
        """Set ``/C0``. Accepts a numeric sequence or a pre-built ``COSArray``
        — the latter mirrors upstream ``setC0(COSArray)`` for callers that
        already hold a COS array."""
        if isinstance(c0, COSArray):
            self.get_cos_object().set_item(_C0, c0)
            return
        arr = COSArray()
        arr.set_float_array(c0)
        self.get_cos_object().set_item(_C0, arr)

    # ---------- /C1 ----------

    def get_c1(self) -> list[float]:
        """Return ``/C1`` as a Python list of floats. Defaults to ``[1.0]``
        when the key is absent, per PDF 32000-1 §7.10.3."""
        item = self.get_cos_object().get_dictionary_object(_C1)
        if isinstance(item, COSArray):
            return item.to_float_array()
        return [1.0]

    def get_c1_array(self) -> COSArray:
        """Return the underlying ``/C1`` ``COSArray`` (or the spec default
        ``[1.0]`` when absent). See :meth:`get_c0_array` for rationale."""
        item = self.get_cos_object().get_dictionary_object(_C1)
        if isinstance(item, COSArray):
            return item
        default = COSArray()
        default.set_float_array([1.0])
        return default

    def set_c1(self, c1: list[float] | tuple[float, ...] | COSArray) -> None:
        """Set ``/C1``. Accepts a numeric sequence or a pre-built ``COSArray``."""
        if isinstance(c1, COSArray):
            self.get_cos_object().set_item(_C1, c1)
            return
        arr = COSArray()
        arr.set_float_array(c1)
        self.get_cos_object().set_item(_C1, arr)

    # ---------- /N ----------

    def get_n(self) -> float:
        """Return ``/N`` (the interpolation exponent), defaulting to ``1.0``."""
        return self.get_cos_object().get_float(_N, 1.0)

    def set_n(self, n: float) -> None:
        """Set ``/N`` (the interpolation exponent)."""
        self.get_cos_object().set_item(_N, COSFloat(n))

    # ---------- evaluation ----------

    def eval(self, input: list[float]) -> list[float]:  # noqa: A002 - upstream parameter name
        """Exponential interpolation per PDF 32000-1 §7.10.3.

        ``y[j] = C0[j] + x**N * (C1[j] - C0[j])`` for each output ``j``.
        Type 2 always takes a single input; only ``input[0]`` is used.
        Output is clipped to ``/Range`` when present.

        Output dimension is ``len(/C0)``, matching upstream PDFBox
        ``PDFunctionType2.eval`` which sizes the result by ``c0.size()``
        only. If ``/C1`` is shorter (a malformed function), missing entries
        are treated as ``0.0`` so eval never raises ``IndexError`` —
        upstream would throw ``ArrayIndexOutOfBoundsException`` here, but
        we surface a defined fallback because shading renderers call this
        in tight inner loops.
        """
        clipped = self.clip_input(input)
        x = clipped[0] if clipped else 0.0
        c0 = self.get_c0()
        c1 = self.get_c1()
        n = self.get_n()
        x_pow = x ** n
        # Sized by /C0 per spec. /C1 short-fall is padded with 0.0 to keep
        # eval defined when callers feed in a malformed dictionary.
        if len(c1) < len(c0):
            c1 = c1 + [0.0] * (len(c0) - len(c1))
        result = [c0[j] + x_pow * (c1[j] - c0[j]) for j in range(len(c0))]
        return self.clip_output(result)


__all__ = ["PDFunctionType2"]
