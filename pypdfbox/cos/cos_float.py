from __future__ import annotations

import math
import struct
from decimal import Decimal
from typing import IO, Any, ClassVar

from .cos_number import COSNumber
from .i_cos_visitor import ICOSVisitor

_FLOAT_MAX = 3.4028234663852886e38  # Float.MAX_VALUE
_FLOAT_MIN_NORMAL = 1.1754943508222875e-38  # Float.MIN_NORMAL (2**-126)


def _shortest_float32_decimal(value: float) -> str:
    """Shortest decimal ``%g`` string that round-trips to the same IEEE-754
    single-precision value as ``value`` — the Python equivalent of Java's
    ``Float.toString`` digit-selection step.

    ``value`` is a non-negative Python ``float`` (double) already holding a
    float32-representable magnitude (``COSFloat`` coerces on construction). We
    search upward in significant-digit precision and stop at the first that
    round-trips through ``float32`` exactly, which yields the minimal digit
    string. Candidates whose ``float64`` value overflows the single-precision
    range (only possible right at ``Float.MAX_VALUE``) cannot equal a finite
    target, so they are skipped rather than allowed to raise."""
    target = struct.unpack("f", struct.pack("f", value))[0]
    for precision in range(1, 18):
        candidate = f"{target:.{precision}g}"
        try:
            round_tripped = struct.unpack("f", struct.pack("f", float(candidate)))[0]
        except OverflowError:
            # ``candidate`` rounded above Float.MAX_VALUE as a double — it can
            # never equal a finite float32 target, so try more digits.
            continue
        if round_tripped == target:
            return candidate
    return repr(target)


def format_float32(value: float) -> str:
    """Canonical PDF real-number serialization, byte-for-byte matching Apache
    PDFBox ``COSFloat.formatString`` (PDFBox 3.0.7) for finite values.

    Upstream (PDFBox 3.0.7)::

        String s = String.valueOf(value);            // Float.toString(value)
        valueAsString = s.indexOf('E') < 0
            ? s
            : new BigDecimal(s).stripTrailingZeros().toPlainString();

    The ``Float.toString`` contract uses exponent notation only when the
    magnitude is ``< 1e-3`` or ``>= 1e7``; inside that window the decimal form
    always carries at least one fractional digit (whole numbers keep a trailing
    ``.0``). Outside it, PDFBox strips trailing zeros via ``BigDecimal``. Both
    branches are reproduced here so a freshly-constructed ``COSFloat``
    serialises identically to upstream regardless of whether the self-write
    (``write_pdf``) path or ``COSWriter`` drives it.

    This is the single source of truth: ``COSFloat.format_string`` and the
    writer's ``COSWriter.format_float`` both delegate here, so there is exactly
    one float-formatting implementation in the codebase.

    Note: for the smallest subnormals (e.g. ``Float.MIN_VALUE`` = ``1.4e-45``)
    Java's legacy ``FloatingDecimal`` can emit a *non-minimal* digit string
    (``1.4E-45`` where ``1E-45`` also round-trips); we emit the truly-shortest
    round-tripping form, which is a valid PDF number but may differ in
    non-significant trailing digits. See CHANGES.md."""
    # NaN cannot be encoded as a PDF number, but match Java's ``Float.toString``
    # token ("NaN") rather than emitting "nan"/"NaN.0"; the writer raises on
    # NaN before it ever reaches a serialised PDF.
    if math.isnan(value):
        return "NaN"
    # ±0.0 — preserve the sign bit (Float.toString yields "0.0" / "-0.0").
    if value == 0.0:
        return "-0.0" if struct.pack("f", value)[3] & 0x80 else "0.0"
    negative = value < 0
    magnitude = -value if negative else value
    digits = _shortest_float32_decimal(magnitude)
    decimal_value = Decimal(digits)
    if magnitude < 1e-3 or magnitude >= 1e7:
        # Exponent branch: BigDecimal.stripTrailingZeros().toPlainString().
        text = format(decimal_value.normalize(), "f")
    else:
        # Decimal branch: Float.toString keeps it verbatim, always with a
        # fractional part (e.g. "1000000.0", "100.0").
        text = format(decimal_value, "f")
        if "." not in text:
            text += ".0"
    return ("-" + text) if negative else text


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

    def format_string(self) -> str:
        """Textual form used by ``write_pdf`` — mirrors PDFBox's private
        ``formatString``. If the original parsed text is available, that
        wins (preserves round-trip). Otherwise delegate to the shared
        :func:`format_float32` (the same float32 shortest-digit logic the
        writer uses), so the self-write byte stream matches ``COSWriter``.
        """
        if self._original is not None:
            return self._original
        return format_float32(self._value)

    def write_pdf(self, output: IO[bytes]) -> None:
        """Write the formatted real-number literal to *output* as ISO-8859-1.

        Mirrors PDFBox's ``COSFloat.writePDF(OutputStream)``.
        """
        output.write(self.format_string().encode("iso-8859-1"))

    def accept(self, visitor: ICOSVisitor) -> Any:
        return visitor.visit_from_float(self)

    def coerce(self, value: float) -> float:
        """Public alias for the module-level ``_coerce`` helper. Mirrors
        upstream ``COSFloat.coerce`` (Java line 120) — clamps ``±INF`` to
        ``±MAX_VALUE`` and flushes subnormals to ``0``."""
        return _coerce(value)

    def equals(self, other: object) -> bool:
        """Mirrors upstream ``COSFloat.equals`` (Java line 176). Delegates
        to ``__eq__``; returns ``False`` for incomparable types instead of
        ``NotImplemented``."""
        result = self.__eq__(other)
        if result is NotImplemented:
            return False
        return result

    def hash_code(self) -> int:
        """Mirrors upstream ``COSFloat.hashCode`` (Java line 186) — IEEE-754
        single-precision bit pattern."""
        return self.__hash__()

    def to_string(self) -> str:
        """Mirrors upstream ``COSFloat.toString`` (Java line 195) —
        ``"COSFloat{<formatted-value>}"``."""
        return f"COSFloat{{{self.format_string()}}}"

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
