from __future__ import annotations

from typing import Any, ClassVar

from .cos_number import COSNumber
from .i_cos_visitor import ICOSVisitor

# Java's Integer.valueOf caches -128..127 by default; PDFBox extends to
# -100..256 for the COS hot path. We mirror that range so common values
# (zero, small page indices, byte counts) are shared instances.
_CACHE_LOW = -100
_CACHE_HIGH = 256


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

    def is_valid(self) -> bool:
        return self._valid

    def set_valid(self, valid: bool) -> None:
        self._valid = valid

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_integer(self)

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
