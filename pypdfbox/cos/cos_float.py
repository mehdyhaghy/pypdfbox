from __future__ import annotations

import math
import re
import struct
from decimal import Decimal
from typing import IO, Any, ClassVar

from .cos_number import COSNumber
from .i_cos_visitor import ICOSVisitor

_FLOAT_MAX = 3.4028234663852886e38  # Float.MAX_VALUE
_FLOAT_MIN_NORMAL = 1.1754943508222875e-38  # Float.MIN_NORMAL (2**-126)

# Signed 32/64-bit bounds for the ``f2i`` / ``f2l`` saturating narrowing casts.
_INT_MIN = -(2**31)
_INT_MAX = 2**31 - 1
_LONG_MIN = -(2**63)
_LONG_MAX = 2**63 - 1


def _narrow_to_long(value: float, low: int, high: int) -> int:
    """Reproduce the JVM ``f2i`` / ``f2l`` narrowing-conversion contract.

    Rounds toward zero, maps ``NaN`` to ``0``, and saturates (clamps) to the
    inclusive ``[low, high]`` bound instead of overflowing the way Python's
    unbounded ``int(float)`` would. ``COSFloat`` never holds an infinity (the
    value is float32-clamped on construction), so only finite out-of-range
    magnitudes need clamping."""
    if math.isnan(value):
        return 0
    truncated = math.trunc(value)
    if truncated < low:
        return low
    if truncated > high:
        return high
    return truncated


def _float32_or_inf(value: float) -> float:
    """Round a Python ``float`` (double) to IEEE-754 single precision the way
    Java's ``Float.parseFloat`` does — *allowing* the result to overflow to
    ``±inf``. Unlike :func:`_to_float32` this does NOT clamp to ``±MAX_VALUE``,
    so the constructor's ``parsed == coerce(parsed)`` test can detect that a
    literal like ``1e40`` overflowed (Java sees ``Infinity`` there, which
    ``coerce`` then maps to ``MAX_VALUE`` — making the two unequal and
    discarding the verbatim string)."""
    if math.isnan(value) or math.isinf(value):
        return value
    try:
        return float(struct.unpack(">f", struct.pack(">f", value))[0])
    except OverflowError:
        # A finite double whose magnitude rounds past Float.MAX_VALUE becomes
        # ±Infinity in IEEE-754 single precision (Java ``Float.parseFloat``);
        # ``struct.pack`` refuses to encode it, so synthesise the infinity.
        return math.inf if value > 0 else -math.inf


def _parse_float(text: str) -> float:
    """Parse ``text`` exactly like Java ``Float.parseFloat`` so the
    malformed-number dispatch (and the ``COSFloat(String)`` accept set) matches
    upstream byte-for-byte.

    Java's ``Float.parseFloat`` is *case-sensitive* about its special spellings
    and *stricter* about hex floats than Python's bare ``float()``:

    * ``NaN`` and ``Infinity`` (each with an optional leading ``+``/``-`` and
      surrounding whitespace) are accepted — ``Float.parseFloat("NaN")`` →
      ``NaN``, ``Float.parseFloat("Infinity")`` → ``+Inf``. The lowercase /
      mixed-case spellings Python tolerates (``nan``, ``inf``, ``NAN``,
      ``INFINITY``) are **rejected** by Java, so we reject them too.
    * A hexadecimal float requires a binary exponent: ``0x1p4`` is accepted (=
      16.0) but ``0x10`` is **not** (Python's ``float("0x10")`` already raises,
      but ``float`` accepts neither form, so we route the ``p``-bearing case
      through ``float.fromhex``).

    Anything else falls through to Python ``float()`` which covers the decimal
    grammar Java shares. A spelling Java would reject raises ``ValueError`` so
    the caller's repair path engages exactly when upstream's
    ``catch (NumberFormatException)`` would.
    """
    stripped = text.strip()
    if not stripped:
        raise ValueError(f"not a Java float: {text!r}")
    signless = stripped.lstrip("+-")
    # Special values are case-sensitive in Java (only "NaN" / "Infinity").
    if signless == "NaN":
        return math.nan
    if signless == "Infinity":
        return -math.inf if stripped[0] == "-" else math.inf
    lowered = signless.lower()
    if lowered.startswith("0x"):
        # Java accepts hex floats only with a binary exponent ('p'/'P').
        if "p" in lowered:
            return float.fromhex(stripped)
        raise ValueError(f"not a Java float: {text!r}")
    # Reject the lenient inf/nan spellings Python's float() would otherwise eat.
    if lowered.startswith(("inf", "nan")):
        raise ValueError(f"not a Java float: {text!r}")
    return float(stripped)


_RE_LEADING_ZERO_DASH = re.compile(r"^0\.0*-\d+$")
_RE_DASH_FRAC_DASH = re.compile(r"^-\d+\.-\d+$")


def _repair_malformed_real(text: str) -> str:
    r"""Reproduce upstream ``COSFloat(String)``'s ``catch`` block byte-for-byte
    (PDFBOX-2990 / -3500): three regex-guided repairs, else raise.

    1. a leading double minus ``--16.33`` → drop the first char → ``-16.33``;
    2. ``^0\.0*-\d+`` (e.g. ``0.-262``) → prepend ``-`` and delete the first
       interior ``-`` → ``-0.262``;
    3. ``^-\d+\.-\d+`` (e.g. ``-16.-33``) → prepend ``-`` and delete *all*
       ``-`` → ``-16.33``.

    Anything else is unrecoverable — raise ``OSError`` (upstream
    ``IOException``)."""
    if text.startswith("--"):
        return text[1:]
    if _RE_LEADING_ZERO_DASH.match(text):
        return "-" + text.replace("-", "", 1)
    if _RE_DASH_FRAC_DASH.match(text):
        return "-" + text.replace("-", "")
    raise OSError(f"Error expected floating point number actual='{text}'")


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


def _scientific_float32(magnitude: float) -> tuple[str, str]:
    """Render a positive float32-representable ``magnitude`` as Java's
    ``Float.toString`` scientific regime would, returning ``(mantissa, exponent)``
    where ``mantissa`` is ``d.ddd`` (single leading digit, >=1 fractional digit)
    and ``exponent`` is a plain signed decimal integer string.

    Java's ``FloatingDecimal`` always emits a mantissa of **at least two**
    significant digits in scientific form, then the shortest beyond that which
    round-trips to the same float32. The two-significant-digit floor is what
    makes the smallest subnormal render ``1.4E-45`` (the correctly-rounded
    second digit) rather than the globally-shortest ``1E-45`` a naive
    shortest-round-trip search picks. Verified byte-exact against the live
    ``FloatToStringProbe`` oracle (Apache PDFBox 3.0.7 / OpenJDK 21) across the
    1e7 / 1e-3 boundaries, exact powers of ten, full-mantissa values,
    subnormals down to ``Float.MIN_VALUE``, and ``Float.MAX_VALUE``.
    """
    target = struct.unpack("f", struct.pack("f", magnitude))[0]
    for precision in range(2, 20):
        # ``"%.{p-1}e"`` emits ``p`` significant digits in ``d.ddde±NN`` form.
        candidate = f"{target:.{precision - 1}e}"
        mantissa, _, exponent = candidate.partition("e")
        try:
            round_tripped = struct.unpack("f", struct.pack("f", float(candidate)))[0]
        except OverflowError:
            continue
        if round_tripped != target:
            continue
        # Strip non-significant trailing zeros but keep one fractional digit:
        # Java never emits a bare ``d`` mantissa in scientific form.
        if "." in mantissa:
            mantissa = mantissa.rstrip("0")
            if mantissa.endswith("."):
                mantissa += "0"
        return mantissa, str(int(exponent))
    # Unreachable for finite float32 magnitudes; degrade to a plain repr split.
    return repr(target), "0"


def float_to_string(value: float) -> str:
    """Byte-for-byte port of Java ``Float.toString(float)`` for a value already
    holding a float32-representable magnitude.

    This is the *raw* single-precision rendering — exponent notation when the
    magnitude is ``< 1e-3`` or ``>= 1e7``, plain decimal (with a mandatory
    ``.0`` on whole numbers) otherwise — used directly by
    :meth:`pypdfbox.util.Matrix.__str__` / :meth:`pypdfbox.util.Vector.__str__`
    (upstream ``Matrix.toString`` / ``Vector.toString`` concatenate
    ``Float.toString`` of each cell, keeping the ``E`` form).

    :func:`format_float32` (the PDF real-number serializer) builds on this and
    then strips the ``E`` form to plain decimal the way ``COSFloat.formatString``
    does via ``BigDecimal.toPlainString``.
    """
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    if value == 0.0:
        return "-0.0" if struct.pack("f", value)[3] & 0x80 else "0.0"
    negative = value < 0
    magnitude = -value if negative else value
    if magnitude < 1e-3 or magnitude >= 1e7:
        mantissa, exponent = _scientific_float32(magnitude)
        text = f"{mantissa}E{exponent}"
    else:
        # Inside the window Float.toString is always plain decimal. The shortest
        # ``%g`` digit string can itself be in ``e`` form for whole magnitudes
        # near 1e7 (e.g. "1e+06"); expand it to plain text and ensure the
        # mandatory fractional part (whole numbers keep a trailing ".0").
        text = format(Decimal(_shortest_float32_decimal(magnitude)), "f")
        if "." not in text:
            text += ".0"
    return ("-" + text) if negative else text


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

    The raw ``Float.toString`` rendering — including the scientific-notation
    regime and its two-significant-digit subnormal floor (so ``Float.MIN_VALUE``
    is ``1.4E-45``, matching Java byte-for-byte) — lives in
    :func:`float_to_string`; this function applies the ``BigDecimal`` plain-text
    step on top of it."""
    # NaN cannot be encoded as a PDF number, but match Java's ``Float.toString``
    # token ("NaN") rather than emitting "nan"/"NaN.0"; the writer raises on
    # NaN before it ever reaches a serialised PDF.
    if math.isnan(value):
        return "NaN"
    # ±0.0 — preserve the sign bit (Float.toString yields "0.0" / "-0.0").
    if value == 0.0:
        return "-0.0" if struct.pack("f", value)[3] & 0x80 else "0.0"
    raw = float_to_string(value)
    if "E" not in raw:
        # ``s.indexOf('E') < 0`` — Float.toString already plain; keep verbatim
        # (always carries a fractional part, e.g. "1000000.0", "100.0").
        return raw
    # Exponent branch: ``new BigDecimal(s).stripTrailingZeros().toPlainString()``.
    negative = raw.startswith("-")
    decimal_value = Decimal(raw[1:] if negative else raw)
    text = format(decimal_value.normalize(), "f")
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
    # Upstream is ``Math.abs(value) < Float.MIN_NORMAL`` — and ``abs(-0.0)`` is
    # ``+0.0``, so negative zero flushes to *positive* zero (bits 0x00000000),
    # not ``-0.0`` (mirrors PDFBox coerce's ``fconst_0``). Returning ``+0.0`` for
    # any sub-normal-or-zero magnitude reproduces that exactly.
    if abs(value) < _FLOAT_MIN_NORMAL:
        return 0.0
    return value


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
            # Mirror upstream ``COSFloat(String)`` branch-for-branch: parse the
            # ORIGINAL string first. Only if that throws do we apply the
            # malformed-number regex repairs — and in that repair path the
            # cached ``valueAsString`` stays ``None``, so the value reformats
            # from the float on output (``--16.33`` round-trips as ``-16.33``,
            # not the raw bytes). Reproduces PDFBOX-2990 / -3500.
            try:
                # ``Float.parseFloat`` rounds straight to single precision and
                # may overflow to ±inf; do NOT clamp here so the equality test
                # below detects an overflowing literal like ``1e40``.
                parsed = _float32_or_inf(_parse_float(value))
                coerced = _coerce(parsed)
                # ``valueAsString = (f == parsedValue) ? aFloat : null``.
                self._original = value if parsed == coerced else None
                self._value = coerced
            except ValueError:
                repaired = _repair_malformed_real(value)
                try:
                    parsed = _float32_or_inf(_parse_float(repaired))
                except ValueError as exc:
                    raise OSError(
                        f"Error expected floating point number actual='{value}'"
                    ) from exc
                # Repair path: upstream leaves valueAsString null (reformats).
                self._original = None
                self._value = _coerce(parsed)
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
        """Mirror Java's ``f2i`` narrowing cast (``COSFloat.intValue``):
        round toward zero, ``NaN`` → 0, and saturate at the signed 32-bit
        bounds rather than overflowing (a large ``COSFloat`` like ``1e40``
        yields ``Integer.MAX_VALUE``, not its exact 39-digit truncation)."""
        return _narrow_to_long(self._value, _INT_MIN, _INT_MAX)

    def long_value(self) -> int:
        """Mirror Java's ``f2l`` narrowing cast (``COSFloat.longValue``):
        round toward zero, ``NaN`` → 0, saturate at the signed 64-bit bounds."""
        return _narrow_to_long(self._value, _LONG_MIN, _LONG_MAX)

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
