from __future__ import annotations

import math
import struct
from typing import Any

from .cos_number import COSNumber
from .i_cos_visitor import ICOSVisitor

_FLOAT_MAX = 3.4028234663852886e38  # Float.MAX_VALUE


def _to_float32(value: float) -> float:
    """Round to IEEE-754 single precision; matches Java float conversion."""
    if math.isnan(value):
        return value
    if value > _FLOAT_MAX:
        return _FLOAT_MAX
    if value < -_FLOAT_MAX:
        return -_FLOAT_MAX
    return float(struct.unpack(">f", struct.pack(">f", value))[0])


def _normalize_negatives(text: str) -> str:
    """Recover from common scanner glitches in PDF number literals
    (PDFBOX-2990, PDFBOX-3369, PDFBOX-3500, PDFBOX-4289). Collapses
    ``--16.33`` → ``-16.33`` and moves an internal ``-`` like
    ``0.-262`` to the front, ``0.00000-33917698`` → ``-0.0000033917698``.
    Raises ``OSError`` if the result still has a misplaced ``-``.
    """
    # Numbers in exponential form (``1.4e-46``) carry a legitimate ``-`` in
    # the exponent — leave them alone; ``float()`` parses them directly.
    if "e" in text or "E" in text:
        return text
    if "-" not in text[1:]:
        return text
    leading_neg = text.startswith("-")
    body = text[1:] if leading_neg else text
    if "-" not in body:
        return text
    # Count internal '-' signs in the body. More than one => unrecoverable.
    if body.count("-") > 1:
        raise OSError(f"misplaced '-' in number: {text!r}")
    pre, post = body.split("-", 1)
    if "-" in post:
        raise OSError(f"misplaced '-' in number: {text!r}")
    # Drop trailing zero block of ``pre`` after the decimal point so that
    # ``0.00000-33917698`` becomes ``-0.0000033917698``.
    if "." in pre:
        int_part, frac_part = pre.split(".", 1)
        # We already know ``post`` has no decimal point; insert it after
        # any leading zeros that were already in ``frac_part``.
        zeros = ""
        i = 0
        while i < len(frac_part) and frac_part[i] == "0":
            zeros += "0"
            i += 1
        # Anything to the right of those leading zeros in ``frac_part``
        # was a stray digit; treat it as part of the post block.
        post = frac_part[i:] + post
        recombined = f"{int_part}.{zeros}{post}"
    else:
        recombined = pre + post
    # An internal '-' implies a (re)negation, so the result is always negative
    # regardless of whether the original carried a leading sign.
    return "-" + recombined.lstrip("-")


class COSFloat(COSNumber):
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
            normalized = _normalize_negatives(value)
            try:
                parsed = float(normalized)
            except ValueError as exc:
                raise OSError(f"not a number: {value!r}") from exc
            self._original = value
            # Mirror Java's ``float`` (IEEE-754 single precision). Both the
            # string and direct-float constructors round the same way so two
            # ``COSFloat`` values built from semantically equal inputs compare
            # equal — matches PDFBox's hash/equals contract.
            self._value = _to_float32(parsed)
        else:
            self._value = _to_float32(float(value))
            self._original = None

    @property
    def value(self) -> float:
        return self._value

    def get_value(self) -> float:
        """Upstream-named accessor mirroring ``COSFloat.floatValue()`` /
        the ``getValue()`` accessor pattern used across COS leaf types."""
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
        self._value = _to_float32(value)
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
