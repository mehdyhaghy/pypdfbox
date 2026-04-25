from __future__ import annotations

from typing import Any

from .cos_base import COSBase
from .i_cos_visitor import ICOSVisitor


class COSFloat(COSBase):
    """
    PDF real number. Preserves the original textual representation when
    constructed from a parsed string so the writer can round-trip the
    exact bytes — important for incremental save and content-stream
    fidelity (PRD §3.5).
    """

    def __init__(self, value: float | str) -> None:
        super().__init__()
        self._original: str | None
        if isinstance(value, str):
            self._original = value
            self._value = float(value)
        else:
            self._value = float(value)
            self._original = None

    @property
    def value(self) -> float:
        return self._value

    def float_value(self) -> float:
        return self._value

    def double_value(self) -> float:
        return self._value

    def int_value(self) -> int:
        return int(self._value)

    def long_value(self) -> int:
        return int(self._value)

    def get_original_form(self) -> str | None:
        """Original parsed string, or ``None`` if constructed from a float."""
        return self._original

    def set_value(self, value: float) -> None:
        self._value = value
        self._original = None

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_float(self)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, COSFloat):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        if self._original is not None:
            return f"COSFloat({self._original!r})"
        return f"COSFloat({self._value})"
