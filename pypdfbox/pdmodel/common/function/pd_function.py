from __future__ import annotations

from typing import Iterable

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSFloat, COSStream
from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel.common.pd_range import PDRange
from pypdfbox.pdmodel.common.pd_stream import PDStream

_FUNCTION_TYPE = "FunctionType"
_DOMAIN = "Domain"
_RANGE = "Range"
_TYPE = "Type"
_FUNCTION = "Function"
_IDENTITY = "Identity"


class PDFunction:
    """
    Base PDF function wrapper. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.common.function.PDFunction``.

    A PDFunction wraps either a ``COSDictionary`` (Type 2, 3) or a
    ``COSStream`` (Type 0, 4). The dictionary/stream provides ``/FunctionType``,
    ``/Domain``, and (for sampled / output-clipped functions) ``/Range``.

    Function evaluation (``eval(input)``) is implemented for Type 2
    (exponential interpolation) and Type 3 (stitching). Type 0 (sampled-table
    interpolation) and Type 4 (PostScript calculator) eval are deferred —
    see ``CHANGES.md``. The structural accessors below cover callers that
    introspect or build function dictionaries (e.g. shading dictionaries,
    tint transforms).
    """

    # ---------- /FunctionType code constants ----------
    # Mirror the literal values listed in PDFBox's ``getFunctionType()``
    # javadoc (PDF 32000-1 §7.10.2). Surfaced as class-level attributes so
    # callers can branch on a named constant rather than a magic int —
    # e.g. ``if fn.get_function_type() == PDFunction.FUNCTION_TYPE_SAMPLED``.
    FUNCTION_TYPE_SAMPLED: int = 0
    FUNCTION_TYPE_EXPONENTIAL: int = 2
    FUNCTION_TYPE_STITCHING: int = 3
    FUNCTION_TYPE_POSTSCRIPT: int = 4

    def __init__(self, function: COSBase | None = None) -> None:
        if function is None:
            self._function_dictionary: COSDictionary = COSDictionary()
            self._function_stream: PDStream | None = None
        elif isinstance(function, COSStream):
            self._function_stream = PDStream(function)
            self._function_dictionary = function
            # Mirror upstream: stream-backed functions advertise /Type /Function
            # so that tools that introspect the stream dictionary recognise it.
            function.set_item(_TYPE, COSName.get_pdf_name(_FUNCTION))
        elif isinstance(function, COSDictionary):
            self._function_dictionary = function
            self._function_stream = None
        else:
            raise TypeError(
                "PDFunction expects COSDictionary or COSStream, "
                f"got {type(function).__name__}"
            )

    # ---------- factory ----------

    @staticmethod
    def create(function: COSBase | None) -> PDFunction | None:
        """Dispatch on ``/FunctionType`` to the concrete subclass.

        Returns ``None`` if ``function`` is ``None``. The PDF name
        ``/Identity`` is recognised as a sentinel and returns a
        :class:`PDFunctionTypeIdentity` (mirrors upstream PDFBox handling
        of ``COSName.IDENTITY`` in soft-mask / TR dictionaries). Raises
        ``ValueError`` for an unsupported function type so callers can
        distinguish a missing function from an invalid one (mirrors
        upstream ``IOException``).
        """
        # Local imports to avoid circular references.
        from .pd_function_type0 import PDFunctionType0
        from .pd_function_type2 import PDFunctionType2
        from .pd_function_type3 import PDFunctionType3
        from .pd_function_type4 import PDFunctionType4

        if function is None:
            return None
        # /Identity sentinel — used by transfer / soft-mask dictionaries.
        if isinstance(function, COSName) and function.get_name() == _IDENTITY:
            return PDFunctionTypeIdentity()
        if not isinstance(function, (COSDictionary, COSStream)):
            raise TypeError(
                "PDFunction.create expects COSDictionary or COSStream, "
                f"got {type(function).__name__}"
            )
        function_type = function.get_int(_FUNCTION_TYPE, -1)
        if function_type == 0:
            return PDFunctionType0(function)
        if function_type == 2:
            return PDFunctionType2(function)
        if function_type == 3:
            return PDFunctionType3(function)
        if function_type == 4:
            return PDFunctionType4(function)
        raise ValueError(f"Unsupported /FunctionType value: {function_type}")

    # ---------- core ----------

    def get_cos_object(self) -> COSDictionary:
        return self._function_dictionary

    def get_pd_stream(self) -> PDStream | None:
        """Returns the underlying ``PDStream`` for stream-backed functions
        (Type 0 and Type 4); ``None`` for dictionary-backed functions."""
        return self._function_stream

    def is_stream_backed(self) -> bool:
        """``True`` when the function is wrapped around a ``COSStream``
        (Type 0 sampled, Type 4 PostScript calculator); ``False`` for
        dictionary-backed functions (Type 2 exponential, Type 3 stitching).

        pypdfbox extension — upstream callers branch on
        ``getPDStream() != null`` to make the same distinction. Surfacing
        a named predicate avoids the recurring ``is not None`` idiom and
        documents the intent at the call site.
        """
        return self._function_stream is not None

    def get_function_type(self) -> int:
        """Subclasses override with their concrete type number (0, 2, 3, 4)."""
        raise NotImplementedError("PDFunction subclasses must implement get_function_type")

    # ---------- /Domain ----------

    def get_domain(self) -> COSArray | None:
        item = self._function_dictionary.get_dictionary_object(_DOMAIN)
        if isinstance(item, COSArray):
            return item
        return None

    def set_domain(self, domain: COSArray | None) -> None:
        if domain is None:
            self._function_dictionary.remove_item(_DOMAIN)
        else:
            self._function_dictionary.set_item(_DOMAIN, domain)

    def get_number_of_input_parameters(self) -> int:
        """Pairs in ``/Domain`` — one (min, max) per input dimension."""
        domain = self.get_domain()
        if domain is None:
            return 0
        return domain.size() // 2

    def get_domain_for_input(self, n: int) -> tuple[float, float]:
        """Return the ``(min, max)`` ``/Domain`` pair for input dimension ``n``.

        Mirrors PDFBox ``getDomainForInput(int)``. Raises ``IndexError`` when
        ``n`` is out of range or ``/Domain`` is absent / malformed.
        """
        ranges = self.get_ranges_for_inputs()
        if n < 0 or n >= len(ranges):
            raise IndexError(
                f"input dimension {n} out of range (have {len(ranges)})"
            )
        return ranges[n]

    def get_range_for_input(self, n: int) -> tuple[float, float]:
        """Alias for ``get_domain_for_input`` — preserves the upstream PDFBox
        naming (``getRangeForInput``) which is a long-standing misnomer for
        the ``/Domain`` pair."""
        return self.get_domain_for_input(n)

    def get_pd_range_for_input(self, n: int) -> PDRange:
        """Return a :class:`PDRange` wrapper over the ``/Domain`` pair for
        input dimension ``n``.

        Mirrors the upstream return type of PDFBox ``getDomainForInput(int)``
        which returns a ``PDRange`` — this accessor preserves that surface
        for callers translated straight from Java (``range.getMin()`` /
        ``range.getMax()``). The tuple-returning :meth:`get_domain_for_input`
        remains the Pythonic default. Raises ``ValueError`` when ``/Domain``
        is absent (upstream NPE on the same path).
        """
        domain = self.get_domain()
        if domain is None:
            raise ValueError("PDFunction has no /Domain entry")
        return PDRange(domain, int(n))

    # ---------- /Range ----------

    def get_range(self) -> COSArray | None:
        item = self._function_dictionary.get_dictionary_object(_RANGE)
        if isinstance(item, COSArray):
            return item
        return None

    def set_range(self, value: COSArray | None) -> None:
        if value is None:
            self._function_dictionary.remove_item(_RANGE)
        else:
            self._function_dictionary.set_item(_RANGE, value)

    def get_number_of_output_parameters(self) -> int:
        """Pairs in ``/Range`` — one (min, max) per output dimension. Returns
        ``0`` when ``/Range`` is absent (legal for Type 2 / 3 per PDF 32000-1
        §7.10.3)."""
        rng = self.get_range()
        if rng is None:
            return 0
        return rng.size() // 2

    def get_range_for_output(self, n: int) -> tuple[float, float]:
        """Return the ``(min, max)`` ``/Range`` pair for output dimension ``n``.

        Mirrors PDFBox ``getRangeForOutput(int)``. Raises ``IndexError`` when
        ``n`` is out of range or ``/Range`` is absent.
        """
        ranges = self.get_ranges_for_outputs()
        if n < 0 or n >= len(ranges):
            raise IndexError(
                f"output dimension {n} out of range (have {len(ranges)})"
            )
        return ranges[n]

    def get_pd_range_for_output(self, n: int) -> PDRange:
        """Return a :class:`PDRange` wrapper over the ``/Range`` pair for
        output dimension ``n``.

        Mirrors the upstream return type of PDFBox ``getRangeForOutput(int)``
        which returns a ``PDRange`` — this accessor preserves that surface
        for callers translated straight from Java. The tuple-returning
        :meth:`get_range_for_output` remains the Pythonic default. Raises
        ``ValueError`` when ``/Range`` is absent (upstream NPE on the same
        path).
        """
        rng = self.get_range()
        if rng is None:
            raise ValueError("PDFunction has no /Range entry")
        return PDRange(rng, int(n))

    # ---------- evaluation ----------

    def get_ranges_for_inputs(self) -> list[tuple[float, float]]:
        """Return ``/Domain`` paired as ``(min, max)`` tuples — one per input
        dimension. Empty list when ``/Domain`` is absent or malformed."""
        domain = self.get_domain()
        if domain is None:
            return []
        flat = domain.to_float_array()
        # Guard against odd lengths by truncating to the largest even prefix.
        return [(flat[2 * i], flat[2 * i + 1]) for i in range(len(flat) // 2)]

    def get_ranges_for_outputs(self) -> list[tuple[float, float]]:
        """Return ``/Range`` paired as ``(min, max)`` tuples — one per output
        dimension. Empty list when ``/Range`` is absent."""
        rng = self.get_range()
        if rng is None:
            return []
        flat = rng.to_float_array()
        return [(flat[2 * i], flat[2 * i + 1]) for i in range(len(flat) // 2)]

    def clip_input(self, values: list[float]) -> list[float]:
        """Clamp each input to its ``/Domain`` ``(min, max)`` pair.

        Per PDF 32000-1 §7.10.2, inputs outside the declared domain are
        clipped, not rejected. Excess inputs (beyond the declared dimension
        count) pass through unchanged.
        """
        ranges = self.get_ranges_for_inputs()
        out: list[float] = []
        for i, v in enumerate(values):
            if i < len(ranges):
                lo, hi = ranges[i]
                if lo > hi:
                    lo, hi = hi, lo
                out.append(min(max(v, lo), hi))
            else:
                out.append(v)
        return out

    def clip_output(self, values: list[float]) -> list[float]:
        """Clamp each output to its ``/Range`` ``(min, max)`` pair when
        ``/Range`` is present. Returns inputs unchanged when ``/Range`` is
        absent (legal for Type 2 / 3)."""
        ranges = self.get_ranges_for_outputs()
        if not ranges:
            return list(values)
        out: list[float] = []
        for i, v in enumerate(values):
            if i < len(ranges):
                lo, hi = ranges[i]
                if lo > hi:
                    lo, hi = hi, lo
                out.append(min(max(v, lo), hi))
            else:
                out.append(v)
        return out

    def eval(self, input: list[float]) -> list[float]:  # noqa: A002 - upstream parameter name
        """Evaluate the function at ``input``. Subclasses override.

        Default raises ``NotImplementedError``; Type 0 (sampled) and Type 4
        (PostScript calculator) eval are deferred — callers should rely on
        the structural accessors instead.
        """
        raise NotImplementedError(
            f"eval() is not implemented for {type(self).__name__}"
        )

    def eval_function(self, input: list[float]) -> list[float]:  # noqa: A002 - upstream parameter name
        """Alias for :meth:`eval` — mirrors the upstream PDFBox convenience
        method ``evalFunction(float[])`` which delegates straight to ``eval``."""
        return self.eval(input)

    # ---------- type predicates ----------

    def is_function_type_0(self) -> bool:
        """True when this function reports ``/FunctionType 0`` (sampled)."""
        try:
            return self.get_function_type() == 0
        except NotImplementedError:
            return False

    def is_function_type_2(self) -> bool:
        """True when this function reports ``/FunctionType 2`` (exponential)."""
        try:
            return self.get_function_type() == 2
        except NotImplementedError:
            return False

    def is_function_type_3(self) -> bool:
        """True when this function reports ``/FunctionType 3`` (stitching)."""
        try:
            return self.get_function_type() == 3
        except NotImplementedError:
            return False

    def is_function_type_4(self) -> bool:
        """True when this function reports ``/FunctionType 4`` (PostScript)."""
        try:
            return self.get_function_type() == 4
        except NotImplementedError:
            return False

    # ---------- helpers ----------

    @staticmethod
    def to_array(numbers: Iterable[float]) -> COSArray:
        """Build a ``COSArray`` of ``COSFloat`` from an iterable of numbers.

        Mirrors PDFBox ``PDFunction.toCOSArray(float[])`` — used when callers
        need to round-trip Python floats into a function dictionary's
        ``/Domain`` / ``/Range`` / ``/C0`` / ``/C1`` arrays.
        """
        arr = COSArray()
        for n in numbers:
            arr.add(COSFloat(float(n)))
        return arr

    @staticmethod
    def interpolate(
        x: float,
        x_range_min: float,
        x_range_max: float,
        y_range_min: float,
        y_range_max: float,
    ) -> float:
        """Linear interpolation helper (PDF 32000-1 §7.10.2 ``interpolate``).

        Maps ``x`` from ``[x_range_min, x_range_max]`` linearly into
        ``[y_range_min, y_range_max]``. When ``x_range_max == x_range_min``
        (degenerate domain) returns ``y_range_min`` — mirrors upstream
        PDFBOX-5593 / PR #162 to avoid division-by-zero.
        """
        if x_range_max == x_range_min:
            return y_range_min
        return y_range_min + (
            (x - x_range_min) * (y_range_max - y_range_min)
            / (x_range_max - x_range_min)
        )

    # ---------- upstream-named aliases ----------

    def get_domain_values(self) -> COSArray | None:
        """Upstream-named alias for :meth:`get_domain` (PDFBox protected
        ``getDomainValues()``). Returns the raw ``/Domain`` ``COSArray`` or
        ``None`` when the key is absent / malformed."""
        return self.get_domain()

    def get_range_values(self) -> COSArray | None:
        """Upstream-named alias for :meth:`get_range` (PDFBox protected
        ``getRangeValues()``). Returns the raw ``/Range`` ``COSArray`` or
        ``None`` when the key is absent."""
        return self.get_range()

    def set_domain_values(self, domain_values: COSArray | None) -> None:
        """Upstream-named alias for :meth:`set_domain` (PDFBox
        ``setDomainValues(COSArray)``)."""
        self.set_domain(domain_values)

    def set_range_values(self, range_values: COSArray | None) -> None:
        """Upstream-named alias for :meth:`set_range` (PDFBox
        ``setRangeValues(COSArray)``)."""
        self.set_range(range_values)

    def clip_to_range(self, values: list[float]) -> list[float]:
        """Upstream-named alias for :meth:`clip_output` (PDFBox
        ``clipToRange(float[])``)."""
        return self.clip_output(values)

    @staticmethod
    def clip_value_to_range(x: float, range_min: float, range_max: float) -> float:
        """Upstream-named alias for the scalar clamp helper (PDFBox
        ``clipToRange(float, float, float)``). Returns ``x`` clamped to
        ``[range_min, range_max]``; tolerates ``range_min > range_max`` by
        normalising the pair first."""
        lo, hi = (range_min, range_max) if range_min <= range_max else (range_max, range_min)
        if x < lo:
            return lo
        if x > hi:
            return hi
        return x

    def __str__(self) -> str:
        """Mirror upstream ``toString()`` — ``"FunctionType<n>"``."""
        try:
            return f"FunctionType{self.get_function_type()}"
        except (NotImplementedError, Exception):  # pragma: no cover - defensive
            return "FunctionType?"


class PDFunctionTypeIdentity(PDFunction):
    """The ``/Identity`` function — returns its inputs unchanged.

    Mirrors PDFBox ``PDFunctionTypeIdentity``. Used in transfer / soft-mask
    dictionaries where the spec allows the literal name ``/Identity`` in
    place of a function dictionary. ``get_function_type`` is undefined per
    upstream (it raises) — callers should branch on ``isinstance`` instead.
    """

    def __init__(self, function: COSBase | None = None) -> None:
        # Mirrors upstream signature ``PDFunctionTypeIdentity(COSBase function)``
        # which discards the argument and passes ``null`` to ``super``. The
        # parameter exists purely to keep call sites translated from Java
        # (``new PDFunctionTypeIdentity(base)``) compiling without edits.
        super().__init__(None)

    def get_function_type(self) -> int:  # pragma: no cover - upstream behaviour
        raise NotImplementedError(
            "PDFunctionTypeIdentity has no /FunctionType — branch on isinstance"
        )

    def eval(self, input: list[float]) -> list[float]:  # noqa: A002 - upstream parameter name
        return list(input)

    def get_range(self) -> COSArray | None:
        # Upstream returns null so the base ``clipToRange`` is a no-op.
        return None

    def get_range_values(self) -> COSArray | None:
        """Upstream-named alias for :meth:`get_range`. Mirrors the protected
        override ``PDFunctionTypeIdentity.getRangeValues()`` which returns
        ``null`` so that the base ``clipToRange`` short-circuits."""
        return None

    def __str__(self) -> str:
        return "FunctionTypeIdentity"


__all__ = ["PDFunction", "PDFunctionTypeIdentity"]
