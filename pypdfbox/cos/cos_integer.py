from __future__ import annotations

from typing import IO, Any, ClassVar

from .cos_number import COSNumber
from .i_cos_visitor import ICOSVisitor

# Java's Integer.valueOf caches -128..127 by default; PDFBox extends to
# -100..256 for the COS hot path. We mirror that range so common values
# (zero, small page indices, byte counts) are shared instances.
_CACHE_LOW = -100
_CACHE_HIGH = 256

# Java ``Long`` range — used for ``OUT_OF_RANGE_MIN`` / ``OUT_OF_RANGE_MAX``.
_LONG_MIN = -(2**63)
_LONG_MAX = 2**63 - 1


class COSInteger(COSNumber):
    """PDF integer object."""

    _cache: ClassVar[dict[int, COSInteger]] = {}

    def __init__(self, value: int) -> None:
        super().__init__()
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("COSInteger value must be int")
        self._value = value
        # PDFBOX-5176: integers parsed from input outside Java's Long range
        # are kept (Python ints are unbounded) but flagged invalid so the
        # writer / consumer can react. Defaults to True; set via ``set_valid``.
        self._valid: bool = True

    # PDFBox-style static factory. Java overloads ``COSInteger.get(long)`` vs
    # ``COSNumber.get(String)``; Python sees the same name on the subclass
    # so we silence mypy's LSP complaint here.
    @classmethod
    def get(cls, value: int) -> COSInteger:  # type: ignore[override]
        """Return a cached instance for small values, else a new one."""
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("COSInteger value must be int")
        if _CACHE_LOW <= value <= _CACHE_HIGH:
            cached = cls._cache.get(value)
            if cached is None:
                cached = cls(value)
                cls._cache[value] = cached
            return cached
        return cls(value)

    @property
    def value(self) -> int:
        return self._value

    def int_value(self) -> int:
        return self._value

    def long_value(self) -> int:
        # Python ints are unbounded; long_value exists for PDFBox API parity.
        return self._value

    def float_value(self) -> float:
        return float(self._value)

    def double_value(self) -> float:
        # Python has a single float type (IEEE-754 double); ``double_value``
        # is provided for PDFBox API parity.
        return float(self._value)

    def get_value(self) -> int:
        """Mirror PDFBox's ``COSInteger.getValue()`` accessor."""
        return self._value

    def is_valid(self) -> bool:
        return self._valid

    def set_valid(self, valid: bool) -> None:
        self._valid = valid

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_integer(self)

    def write_pdf(self, output: IO[bytes]) -> None:
        """Write the integer's decimal form to *output* using ISO-8859-1.

        Mirrors PDFBox's ``COSInteger.writePDF(OutputStream)``.
        """
        output.write(str(self._value).encode("iso-8859-1"))

    def equals(self, other: object) -> bool:
        """Java-style value-equality predicate. Mirrors ``COSInteger.equals``."""
        return isinstance(other, COSInteger) and self._value == other._value

    def hash_code(self) -> int:
        """Mirror Java's ``COSInteger.hashCode()``.

        Upstream uses the ``java.lang.Long`` recipe ``(int)(value ^ (value >> 32))``
        — XOR the high and low 32-bit halves of the 64-bit value and truncate
        to a signed 32-bit int. We replicate the bit-level result here so two
        ``COSInteger``s with the same numeric value yield equal hash codes
        even when the underlying Python int range exceeds ``long``.
        """
        # Mask to unsigned 64-bit, arithmetic shift right 32 (preserves sign
        # by using the original signed value), XOR, then truncate to int32.
        v = self._value
        # Java arithmetic >> 32 on a signed long.
        high = v >> 32
        low = v & 0xFFFFFFFF
        xored = (high ^ low) & 0xFFFFFFFF
        # Convert to signed 32-bit.
        if xored >= 0x80000000:
            xored -= 0x1_0000_0000
        return xored

    def to_string(self) -> str:
        """Mirror Java's ``COSInteger.toString()`` — ``"COSInt{<value>}"``."""
        return f"COSInt{{{self._value}}}"

    @classmethod
    def get_invalid(cls, max_value: bool) -> COSInteger:
        """Mirror Java's private ``COSInteger.getInvalid(boolean)`` factory.

        Returns a fresh ``COSInteger`` carrying ``Long.MAX_VALUE`` (or
        ``Long.MIN_VALUE``) and flagged invalid — used by upstream to build
        the ``OUT_OF_RANGE_MAX`` / ``OUT_OF_RANGE_MIN`` sentinels.
        """
        instance = cls(_LONG_MAX if max_value else _LONG_MIN)
        instance.set_valid(False)
        return instance

    def compare_to(self, other: COSInteger) -> int:
        """Numeric comparison returning -1, 0, or 1 — mirrors
        ``COSInteger.compareTo(COSInteger)`` (Java's ``Comparable`` contract).
        """
        if not isinstance(other, COSInteger):
            raise TypeError("compare_to requires another COSInteger")
        if self._value < other._value:
            return -1
        if self._value > other._value:
            return 1
        return 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, COSInteger):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        return f"COSInteger({self._value})"


COSInteger.ZERO = COSInteger.get(0)  # type: ignore[attr-defined]
COSInteger.ONE = COSInteger.get(1)  # type: ignore[attr-defined]
COSInteger.TWO = COSInteger.get(2)  # type: ignore[attr-defined]
COSInteger.THREE = COSInteger.get(3)  # type: ignore[attr-defined]

# Sentinel singletons returned by ``COSNumber.get`` when the textual literal
# parses to a value outside Java's ``Long`` range — mirrors PDFBox's
# ``COSInteger.OUT_OF_RANGE_MAX`` / ``OUT_OF_RANGE_MIN`` (PDFBOX-5176).
# Both carry ``is_valid()`` == ``False`` so writers / consumers can react.
_OUT_OF_RANGE_MAX = COSInteger(_LONG_MAX)
_OUT_OF_RANGE_MAX.set_valid(False)
_OUT_OF_RANGE_MIN = COSInteger(_LONG_MIN)
_OUT_OF_RANGE_MIN.set_valid(False)
COSInteger.OUT_OF_RANGE_MAX = _OUT_OF_RANGE_MAX  # type: ignore[attr-defined]
COSInteger.OUT_OF_RANGE_MIN = _OUT_OF_RANGE_MIN  # type: ignore[attr-defined]
