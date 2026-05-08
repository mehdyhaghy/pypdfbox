from __future__ import annotations

import math

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

    # ---------- presence predicates ----------
    #
    # PDF 32000-1 §7.10.3 requires ``/N``; ``/C0`` and ``/C1`` are optional
    # (defaulting to ``[0]`` and ``[1]``). The ``has_*`` predicates let
    # callers introspect the *physical* presence of each key in the COS
    # dictionary so that round-trip writers can emit only the keys that
    # were originally present, and lint tooling can flag dictionaries that
    # rely on the defaults. There is no direct upstream equivalent — Java
    # PDFBox calls ``getCOSObject().containsKey(...)`` inline at the call
    # site; we expose the predicate explicitly to match the project's
    # consistent ``has_*`` accessor surface (see e.g. PDActionLaunch,
    # PDDocumentInformation).

    def has_c0(self) -> bool:
        """``True`` iff ``/C0`` is explicitly present in the underlying
        dictionary (regardless of array contents). ``False`` when the key
        is absent and :meth:`get_c0` is materialising the spec default."""
        return self.get_cos_object().contains_key(_C0)

    def has_c1(self) -> bool:
        """``True`` iff ``/C1`` is explicitly present in the underlying
        dictionary. ``False`` when the key is absent and :meth:`get_c1` is
        materialising the spec default."""
        return self.get_cos_object().contains_key(_C1)

    def has_n(self) -> bool:
        """``True`` iff ``/N`` is explicitly present in the underlying
        dictionary. ``False`` when :meth:`get_n` is falling back to the
        documented ``1.0`` default (see :meth:`get_n` for the divergence
        from upstream's ``-1.0``)."""
        return self.get_cos_object().contains_key(_N)

    # ---------- output dimensionality ----------

    def get_output_dimensions(self) -> int:
        """Return the implicit output dimensionality of this Type 2 function.

        For Type 2, ``/Range`` is optional (PDF 32000-1 §7.10.3) — when
        present it defines output dimensions, but when absent the output
        dimension is inferred from ``min(len(/C0), len(/C1))`` to match
        upstream eval allocation (``new float[Math.min(c0.size(),
        c1.size())]``). This helper returns whichever count eval will
        actually produce, so callers building shading dictionaries can
        size downstream buffers without re-deriving the rule.
        """
        rng_pairs = self.get_ranges_for_outputs()
        if rng_pairs:
            return len(rng_pairs)
        return min(len(self.get_c0()), len(self.get_c1()))

    # ---------- evaluation ----------

    def eval(self, input: list[float]) -> list[float]:  # noqa: A002 - upstream parameter name
        """Exponential interpolation per PDF 32000-1 §7.10.3.

        ``y[j] = C0[j] + x**N * (C1[j] - C0[j])`` for each output ``j``.
        Type 2 always takes a single input; only ``input[0]`` is used.
        Output is clipped to ``/Range`` when present.

        Output dimension is ``min(len(/C0), len(/C1))`` to match upstream
        PDFBox ``PDFunctionType2.eval`` (``new float[Math.min(c0.size(),
        c1.size())]``).
        """
        clipped = self.clip_input(input)
        x = clipped[0] if clipped else 0.0
        c0 = self.get_c0()
        c1 = self.get_c1()
        n = self.get_n()
        x_pow = _pow_as_pdf_float(x, n)
        # Sized by min(c0, c1) — upstream parity.
        size = min(len(c0), len(c1))
        result = [c0[j] + x_pow * (c1[j] - c0[j]) for j in range(size)]
        return self._clip_output_to_range_dimensions(result)

    def _clip_output_to_range_dimensions(self, values: list[float]) -> list[float]:
        """Clip Type 2 outputs, sizing the result to explicit /Range pairs.

        PDFBox's base ``clipToRange(float[])`` returns one value per range pair
        whenever ``/Range`` is present. Keep that Type 2 parity locally without
        changing this port's shared ``clip_output`` helper, whose public
        contract preserves values beyond the declared range pairs.
        """
        ranges = self.get_ranges_for_outputs()
        if not ranges:
            return list(values)
        out: list[float] = []
        for i, (lo, hi) in enumerate(ranges):
            if i >= len(values):
                break
            v = values[i]
            if lo > hi:
                lo, hi = hi, lo
            out.append(min(max(v, lo), hi))
        return out

    def __str__(self) -> str:
        """Mirror upstream ``toString()`` —
        ``"FunctionType2{C0: <c0> C1: <c1> N: <n>}"``."""
        return (
            "FunctionType2{"
            f"C0: {self.get_c0_array()} "
            f"C1: {self.get_c1_array()} "
            f"N: {self.get_n()}}}"
        )


def _pow_as_pdf_float(base: float, exponent: float) -> float:
    """Evaluate exponentiation in the Java/PDFBox-style float domain."""
    try:
        return math.pow(base, exponent)
    except ValueError:
        return math.nan


__all__ = ["PDFunctionType2"]
