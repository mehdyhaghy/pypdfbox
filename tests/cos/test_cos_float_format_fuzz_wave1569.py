"""Wave 1569 — COSFloat numeric-string formatting parity fuzz.

Hammers the float -> PDF real-literal serialization done by
``COSFloat.format_string`` / ``COSFloat.write_pdf`` (the port of upstream
``COSFloat.formatString`` / ``writePDF``, PDFBox 3.0.7). Every expectation in
:data:`_FLOAT_CASES` and :data:`_STRING_CASES` was captured byte-for-byte from
the live ``CosFloatFormatProbe`` driving real Apache PDFBox 3.0.7
(``new COSFloat((float) v).writePDF`` and ``new COSFloat(String).writePDF``)
on OpenJDK 21, so the hardcoded half of this suite enforces parity even on a
machine without the oracle jar. The ``requires_oracle`` test re-derives the
same expectations live and asserts pypdfbox matches.

Upstream pipeline (verbatim, ``COSFloat.formatString``)::

    String s = String.valueOf(value);            // Float.toString(value)
    valueAsString = s.indexOf('E') < 0
        ? s
        : new BigDecimal(s).stripTrailingZeros().toPlainString();

The ``COSFloat(String)`` ctor caches the original lexeme verbatim when the
parsed float round-trips equal to ``coerce(parsed)``; otherwise it reformats
from the float (overflow / subnormal-flush / repair paths).

ONE documented divergence (see CHANGES.md, wave 1569): the *direct-float*
``COSFloat(1e40f)`` overflows to ``+Infinity`` in Java (its ``float`` ctor does
no coercion) and serialises ``"Infinity"``; pypdfbox clamps to
``±Float.MAX_VALUE`` on construction so the value never holds an infinity (the
``int_value`` / ``long_value`` narrowing casts rely on that invariant) and
serialises the MAX_VALUE digit string instead. The *string* path
``COSFloat("1e40")`` matches Java exactly (both emit the MAX_VALUE digits).
"""

from __future__ import annotations

import io
import math

import pytest

from pypdfbox.cos.cos_float import COSFloat

try:
    from tests.oracle.harness import requires_oracle, run_probe_text
except ImportError:  # pragma: no cover - oracle harness optional
    requires_oracle = pytest.mark.skip(reason="oracle harness unavailable")

    def run_probe_text(*_args: str, **_kwargs: object) -> str:  # type: ignore[misc]
        raise RuntimeError("oracle harness unavailable")


def _write(f: COSFloat) -> str:
    buf = io.BytesIO()
    f.write_pdf(buf)
    return buf.getvalue().decode("iso-8859-1")


# (double-arg-string, expected writePDF output) for the COSFloat((float) v)
# ctor. Captured live from real PDFBox 3.0.7 COSFloat.writePDF.
_FLOAT_CASES: list[tuple[str, str]] = [
    # Integers-as-floats keep Float.toString's mandatory ".0" below 1e7.
    ("2.0", "2.0"),
    ("100.0", "100.0"),
    ("1000000.0", "1000000.0"),
    # Trailing-zero stripping happens only via BigDecimal on the E-form;
    # inside the plain window Float.toString already yields the short form.
    ("1.5", "1.5"),
    ("1.50", "1.5"),
    ("2.500", "2.5"),
    ("0.5", "0.5"),
    ("-0.5", "-0.5"),
    ("-3.14", "-3.14"),
    ("3.14159265", "3.1415927"),  # float32 rounding
    # Signed zero — sign bit preserved (Float.toString -> "0.0" / "-0.0").
    ("0.0", "0.0"),
    ("-0.0", "-0.0"),
    # Tiny magnitudes: Java's Float.toString uses E notation < 1e-3, but
    # COSFloat strips it to plain decimal via BigDecimal.toPlainString.
    ("0.001", "0.001"),
    ("0.0001", "0.0001"),
    ("-0.0001", "-0.0001"),
    ("1e-5", "0.00001"),
    ("1e-6", "0.000001"),
    ("1e-7", "0.0000001"),
    ("1e-10", "0.0000000001"),
    ("0.00000001", "0.00000001"),  # the PDFBOX bug-compat 1e-8 case
    ("0.1", "0.1"),
    # Large magnitudes: >= 1e7 -> Float.toString E-form -> plain decimal.
    ("9999999.0", "9999999.0"),
    ("10000000.0", "10000000"),
    ("10000001.0", "10000001"),
    ("100000000.0", "100000000"),
    ("123456789.0", "123456790"),  # float32 rounding then plain expansion
    # Float.MIN_VALUE (smallest positive subnormal) -> full plain decimal.
    ("1.4e-45", "0.0000000000000000000000000000000000000000000014"),
    # Float.MAX_VALUE -> 39-digit plain decimal.
    ("3.4028235e38", "340282350000000000000000000000000000000"),
    # Underflow below Float.MIN_VALUE flushes to 0.0f (IEEE rounding).
    ("1e-50", "0.0"),
]


# (lexeme, expected writePDF output) for the COSFloat(String) ctor. The lexeme
# is preserved verbatim when parsed == coerce(parsed). Captured live.
_STRING_CASES: list[tuple[str, str]] = [
    # Verbatim lexeme preservation (round-trip fidelity).
    ("2.0", "2.0"),
    ("1.50", "1.50"),
    ("2.000", "2.000"),
    ("0.0000001", "0.0000001"),
    ("1.0E-7", "1.0E-7"),
    ("1.0E7", "1.0E7"),
    ("1E7", "1E7"),  # uppercase E lexeme kept verbatim
    ("1.0E-3", "1.0E-3"),
    ("123.456", "123.456"),
    ("0.5", "0.5"),
    ("-0.0", "-0.0"),
    ("100", "100"),
    ("+1.5", "+1.5"),
    (".5", ".5"),
    ("5.", "5."),
    ("0.001", "0.001"),
    ("0.00000001", "0.00000001"),
    # Repair paths (PDFBOX-2990 / -3500): lexeme discarded, reformat from float.
    ("--16.33", "-16.33"),
    ("--1.5", "-1.5"),
    ("0.-262", "-0.262"),
    ("-16.-33", "-16.33"),
    # Overflow on the string path: Java coerces +Inf -> MAX_VALUE, lexeme
    # discarded (parsed != coerced), reformats from MAX_VALUE. pypdfbox matches.
    ("1e40", "340282350000000000000000000000000000000"),
    # NaN lexeme: Float.parseFloat("NaN") == coerce(NaN) (NaN != NaN is false
    # in the != test? Java fcmpl: NaN != NaN is *true*, so lexeme is discarded
    # and Float.toString(NaN) == "NaN" is emitted).
    ("NaN", "NaN"),
]


@pytest.mark.parametrize(
    ("arg", "expected"),
    _FLOAT_CASES,
    ids=[c[0] for c in _FLOAT_CASES],
)
def test_float_ctor_format(arg: str, expected: str) -> None:
    f = COSFloat(float(arg))
    assert _write(f) == expected
    # format_string and write_pdf must agree byte-for-byte.
    assert f.format_string() == expected


@pytest.mark.parametrize(
    ("lexeme", "expected"),
    _STRING_CASES,
    ids=[c[0].replace(".", "d").replace("-", "m").replace("+", "p") for c in _STRING_CASES],
)
def test_string_ctor_format(lexeme: str, expected: str) -> None:
    f = COSFloat(lexeme)
    assert _write(f) == expected
    assert f.format_string() == expected


def test_verbatim_lexeme_round_trips() -> None:
    """A clean lexeme is cached verbatim and survives write unchanged."""
    for lexeme in ("1.50", "2.000", "123.456", "0.0000001", "1.0E-7", ".5", "5."):
        f = COSFloat(lexeme)
        assert f.get_original_form() == lexeme
        assert _write(f) == lexeme


def test_repair_path_drops_lexeme() -> None:
    """Repaired malformed reals reformat from the float (no cached lexeme)."""
    for lexeme in ("--16.33", "0.-262", "-16.-33"):
        f = COSFloat(lexeme)
        assert f.get_original_form() is None


def test_overflow_lexeme_dropped_string_path() -> None:
    """An overflowing string literal discards its lexeme and reformats from
    MAX_VALUE (Java coerce: +Inf -> MAX_VALUE, parsed != coerced)."""
    f = COSFloat("1e40")
    assert f.get_original_form() is None
    assert _write(f) == "340282350000000000000000000000000000000"


def test_nan_string_serialises_token() -> None:
    """NaN never round-trips its lexeme; Float.toString(NaN) -> "NaN"."""
    f = COSFloat("NaN")
    assert _write(f) == "NaN"
    assert math.isnan(f.value)


def test_signed_zero_bits_preserved() -> None:
    """+0.0 and -0.0 keep their sign bit on the float ctor path."""
    assert _write(COSFloat(0.0)) == "0.0"
    assert _write(COSFloat(-0.0)) == "-0.0"


def test_no_scientific_notation_in_pdf_output() -> None:
    """The PDF real serializer never emits an 'E'/'e' for the float ctor path —
    BigDecimal.toPlainString flattens Float.toString's exponent form."""
    for arg in ("1e-7", "1e-10", "1e7", "1e8", "1.4e-45", "3.4028235e38"):
        out = _write(COSFloat(float(arg)))
        assert "E" not in out and "e" not in out, (arg, out)


def test_documented_float_ctor_overflow_divergence() -> None:
    """DELIBERATE divergence (CHANGES.md wave 1569): the *direct-float* ctor
    clamps an overflowing magnitude to MAX_VALUE rather than letting it become
    +Infinity (Java's float ctor does no coercion and would emit "Infinity").
    pypdfbox keeps the value finite so int_value/long_value narrowing stays
    well-defined."""
    out = _write(COSFloat(1e40))
    assert out == "340282350000000000000000000000000000000"
    assert not math.isinf(COSFloat(1e40).value)
    assert _write(COSFloat(-1e40)) == "-340282350000000000000000000000000000000"


@requires_oracle
def test_oracle_differential_float_and_string_paths() -> None:
    """Re-derive every expectation live from real PDFBox 3.0.7 and assert
    pypdfbox matches byte-for-byte — except the one documented float-ctor
    overflow divergence, which is asserted to differ exactly as documented."""
    float_args = [c[0] for c in _FLOAT_CASES]
    string_args = ["s:" + c[0] for c in _STRING_CASES]
    args = [*float_args, *string_args]
    raw = run_probe_text("CosFloatFormatProbe", *args)
    oracle: dict[str, str] = {}
    for line in raw.splitlines():
        if not line:
            continue
        arg, _, value = line.partition("\t")
        oracle[arg] = value

    for arg in float_args:
        ours = _write(COSFloat(float(arg)))
        theirs = oracle[arg]
        if arg in ("1e40", "-1e40"):
            # Documented divergence: Java -> Infinity, pypdfbox -> MAX_VALUE.
            assert "Infinity" in theirs
            assert "Infinity" not in ours
        else:
            assert ours == theirs, (arg, ours, theirs)

    for lexeme, _expected in _STRING_CASES:
        ours = _write(COSFloat(lexeme))
        theirs = oracle["s:" + lexeme]
        assert ours == theirs, (lexeme, ours, theirs)
