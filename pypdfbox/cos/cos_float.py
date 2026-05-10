from __future__ import annotations

import math
import struct
from decimal import Decimal
from typing import IO, Any, ClassVar

from .cos_number import COSNumber
from .i_cos_visitor import ICOSVisitor

_FLOAT_MAX = 3.4028234663852886e38  # Float.MAX_VALUE
_FLOAT_MIN_NORMAL = 1.1754943508222875e-38  # Float.MIN_NORMAL (2**-126)


def _to_float32(value: float) -> float:
    """Round to IEEE-754 single precision and clamp out-of-range magnitudes
    to ``±MAX_VALUE``. Used by the direct-float constructor and ``set_value``;
    pypdfbox callers expect bounded output so signed infinities never leak
    into the model. Subnormals are *not* flushed here — that's the additional
    step ``COSFloat.coerce`` applies on the string-construction path."""
    if math.isnan(value):
        return value
    if value > _FLOAT_MAX or value == math.inf:
        return _FLOAT_MAX
    if value < -_FLOAT_MAX or value == -math.inf:
        return -_FLOAT_MAX
    return float(struct.unpack(">f", struct.pack(">f", value))[0])


def _coerce(value: float) -> float:
    """Mirror upstream ``COSFloat.coerce``: ``+INF → MAX_VALUE``,
    ``-INF → -MAX_VALUE``, ``|x| < MIN_NORMAL → 0`` (PDF spec, Appendix C
    "Implementation Limits"). NaN passes through unchanged. Only invoked
    from the string-construction path, matching upstream Java semantics."""
    if math.isnan(value):
        return value
    if value == math.inf:
        return _FLOAT_MAX
    if value == -math.inf:
        return -_FLOAT_MAX
    if value != 0.0 and abs(value) < _FLOAT_MIN_NORMAL:
        return 0.0
    return value


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

    # Canonical ``0.0`` / ``1.0`` instances — mirrors PDFBox's
    # ``COSFloat.ZERO`` and ``COSFloat.ONE`` class constants. Bound at module
    # load below.
    ZERO: ClassVar[COSFloat]
    ONE: ClassVar[COSFloat]

    def __init__(self, value: float | str) -> None:
        super().__init__()
        self._original: str | None
        if isinstance(value, str):
            normalized = _normalize_negatives(value)
            try:
                parsed = float(normalized)
            except ValueError as exc:
                raise OSError(f"not a number: {value!r}") from exc
            # Mirror Java's ``float`` (IEEE-754 single precision) followed by
            # ``COSFloat.coerce`` for the string-construction path: subnormals
            # flush to 0 and ±infinity clamp to ±MAX_VALUE.
            coerced = _coerce(_to_float32(parsed))
            # Preserve the raw bytes only if the round-trip is faithful —
            # mirrors upstream's ``f == parsedValue ? aFloat : null``.
            self._original = value if _to_float32(parsed) == coerced else None
            self._value = coerced
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

    def getValue(self) -> float:  # noqa: N802 - upstream Java name
        return self.get_value()

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

    def getOriginalForm(self) -> str | None:  # noqa: N802 - upstream Java name
        return self.get_original_form()

    def set_value(self, value: float) -> None:
        self._value = _to_float32(value)
        self._original = None

    def setValue(self, value: float) -> None:  # noqa: N802 - upstream Java name
        self.set_value(value)

    def format_string(self) -> str:
        """Textual form used by ``write_pdf`` — mirrors PDFBox's private
        ``formatString``. If the original parsed text is available, that
        wins (preserves round-trip). Otherwise we use Python's ``str(float)``,
        falling back to ``Decimal.normalize``-style plain notation when the
        result contains an exponent (PDFBox uses ``BigDecimal.toPlainString``).
        """
        if self._original is not None:
            return self._original
        s = repr(self._value) if isinstance(self._value, float) else str(self._value)
        if "e" not in s and "E" not in s:
            return s
        return format(Decimal(s).normalize(), "f")

    def write_pdf(self, output: IO[bytes]) -> None:
        """Write the formatted real-number literal to *output* as ISO-8859-1.

        Mirrors PDFBox's ``COSFloat.writePDF(OutputStream)``.
        """
        output.write(self.format_string().encode("iso-8859-1"))

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_float(self)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, COSFloat):
            # Mirror upstream ``Float.floatToIntBits(a) == Float.floatToIntBits(b)``:
            # two NaN ``COSFloat`` values must compare equal (Python's ``==``
            # would say ``False``), and ``+0.0 != -0.0`` on the bit level even
            # though ``0.0 == -0.0`` numerically.
            return self._float_bits() == other._float_bits()
        return NotImplemented

    def __hash__(self) -> int:
        # ``Float.hashCode(value)`` in Java is the int-bits representation —
        # match that so the equals/hashCode contract holds across NaN.
        return self._float_bits()

    def _float_bits(self) -> int:
        """IEEE-754 single-precision bit pattern of ``self._value`` —
        mirrors ``Float.floatToIntBits``."""
        if math.isnan(self._value):
            # Java collapses every NaN to the canonical 0x7fc00000.
            return 0x7FC00000
        return struct.unpack(">i", struct.pack(">f", self._value))[0]

    def __repr__(self) -> str:
        if self._original is not None:
            return f"COSFloat({self._original!r})"
        return f"COSFloat({self._value})"


# Canonical singletons — built after the class is fully defined so
# constructor-time references resolve. The string forms ("0.0" / "1.0")
# match PDFBox's ``COSFloat.ZERO`` / ``COSFloat.ONE`` constants.
COSFloat.ZERO = COSFloat("0.0")
COSFloat.ONE = COSFloat("1.0")
