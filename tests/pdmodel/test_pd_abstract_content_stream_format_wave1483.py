"""Wave 1483 — byte-level parity for the shared ``PDAbstractContentStream``
numeric-operand formatter (``writeOperand(float)`` / ``formatDecimal``).

Closes the DEFERRED.md (wave 1480) item flagging that
``pd_abstract_content_stream._format_decimal`` still used a float64
``f"{f:.{n}f}"`` path while ``pd_page_content_stream._format_number`` had been
narrowed to Java's 32-bit ``float`` + ``NumberFormatUtil.formatFloatFast``
(truncating half-up on the narrowed fraction, trailing-zero strip, negative
zero preserved).

Two divergences are pinned here against upstream PDFBox 3.0.7:

1. **digit count.** The shared base constructor configures the formatter with
   ``setMaximumFractionDigits(4)`` (PDFBox ``PDAbstractContentStream`` Java line
   112) — note **4**, not the **5** used by the concrete ``PDPageContentStream``
   (which bumps it via ``setMaximumFractionDigits(5)``). Subclasses that do not
   override it (``PDAppearanceContentStream`` / ``PDFormContentStream`` /
   ``PDPatternContentStream``) emit at 4 fractional digits.
2. **float32 + half-up-on-narrowed-fraction.** See
   :func:`pypdfbox.pdmodel.pd_page_content_stream._format_number`. e.g.
   ``0.000005`` (float32 ``4.99999987e-06``) → ``0`` not ``0.00001``;
   ``12345.6789`` (float32 ``12345.6787109375``) → ``12345.6787`` at 4 digits.

The expected byte values below were captured from the live oracle via
``ContentStreamGenProbe numbers4`` (4-digit base) and ``numbers`` (5-digit
page); see :func:`test_format_decimal_matches_live_oracle` for the differential
form. The hand-written assertions pin those bytes so the suite passes without
Java.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.pdmodel import PDAbstractContentStream
from pypdfbox.pdmodel.pd_abstract_content_stream import _format_decimal

# (value, expected-4-digit-bytes) — the abstract base default.
_CASES_4: list[tuple[float, bytes]] = [
    (0.000005, b"0"),
    (0.123455, b"0.1235"),
    (12345.6789, b"12345.6787"),
    (-0.000005, b"-0"),
    (0.33333334, b"0.3333"),
    (3.14, b"3.14"),
    (2.5, b"2.5"),
    (0.125, b"0.125"),
    (123.456, b"123.456"),
    (78.9, b"78.9"),
    (0.75, b"0.75"),
    (0.5, b"0.5"),
]

# (value, expected-5-digit-bytes) — the digit count after
# set_maximum_fraction_digits(5), matching PDPageContentStream's default.
_CASES_5: list[tuple[float, bytes]] = [
    (0.000005, b"0"),
    (0.123455, b"0.12346"),
    (12345.6789, b"12345.67871"),
    (-0.000005, b"-0"),
    (0.33333334, b"0.33333"),
    (123.456, b"123.456"),
    (78.9, b"78.9"),
]


class _Concrete(PDAbstractContentStream):
    """Minimal concrete subclass exposing the protected operand writer."""


def _make() -> tuple[_Concrete, io.BytesIO]:
    out = io.BytesIO()
    return _Concrete(None, out, None), out


def test_default_max_fraction_digits_is_four() -> None:
    # Upstream's shared base constructor sets setMaximumFractionDigits(4),
    # NOT 5 (that is the PDPageContentStream-specific override).
    assert PDAbstractContentStream.DEFAULT_MAX_FRACTION_DIGITS == 4
    cs, _ = _make()
    assert cs.get_maximum_fraction_digits() == 4


@pytest.mark.parametrize(
    ("value", "expected"),
    _CASES_4,
    ids=[repr(v) for v, _ in _CASES_4],
)
def test_format_decimal_four_digits(value: float, expected: bytes) -> None:
    assert _format_decimal(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    _CASES_5,
    ids=[repr(v) for v, _ in _CASES_5],
)
def test_format_decimal_five_digits(value: float, expected: bytes) -> None:
    assert _format_decimal(value, 5) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    _CASES_4,
    ids=[repr(v) for v, _ in _CASES_4],
)
def test_write_operand_four_digits(value: float, expected: bytes) -> None:
    # write_operand routes through the instance's _max_fraction_digits (4 by
    # default) and appends a trailing space.
    cs, out = _make()
    cs.write_operand(value)
    assert out.getvalue() == expected + b" "


@pytest.mark.parametrize(
    ("value", "expected"),
    _CASES_5,
    ids=[repr(v) for v, _ in _CASES_5],
)
def test_write_operand_after_set_max_fraction_digits_five(
    value: float, expected: bytes
) -> None:
    cs, out = _make()
    cs.set_maximum_fraction_digits(5)
    cs.write_operand(value)
    assert out.getvalue() == expected + b" "


def test_negative_zero_preserved() -> None:
    # The float32 of -0.000005 rounds to 0 but the leading '-' survives —
    # upstream's buffer writer emits the sign before the zero integer part.
    assert _format_decimal(-0.000005) == b"-0"


def test_set_line_width_emits_four_digit_operand() -> None:
    # End-to-end through an emit method that routes a float operand: the
    # appearance/form-stream style writers inherit this default-4 formatting.
    cs, out = _make()
    cs.set_line_width(12345.6789)
    assert out.getvalue() == b"12345.6787 w\n"


def test_integers_keep_exact_spelling() -> None:
    # Python int operands take the integer path (no float narrowing).
    assert _format_decimal(42) == b"42"
    assert _format_decimal(2.0) == b"2"


def test_rejects_non_finite() -> None:
    with pytest.raises(ValueError, match="not a finite number"):
        _format_decimal(float("inf"))
    with pytest.raises(ValueError, match="not a finite number"):
        _format_decimal(float("nan"))


# --------------------------------------------------------------------------
# Optional live differential — skipped when the Java oracle is unavailable.
# --------------------------------------------------------------------------

try:
    from tests.oracle.harness import requires_oracle, run_probe_text
except Exception:  # pragma: no cover - harness import guard
    requires_oracle = pytest.mark.skip(reason="oracle harness unavailable")

    def run_probe_text(*_a: str, **_k: str) -> str:  # type: ignore[misc]
        raise RuntimeError


@requires_oracle
def test_format_decimal_matches_live_oracle() -> None:
    values = [v for v, _ in _CASES_4]
    args = [repr(float(v)) for v in values]
    oracle = run_probe_text(
        "AbstractContentStreamFormatProbe", "abstract", *args
    )
    expected = [line for line in oracle.splitlines() if line != ""]
    actual = [_format_decimal(v).decode("ascii") for v in values]
    assert actual == expected


@requires_oracle
def test_format_decimal_five_digit_matches_live_oracle() -> None:
    values = [v for v, _ in _CASES_5]
    args = [repr(float(v)) for v in values]
    oracle = run_probe_text("AbstractContentStreamFormatProbe", "page", *args)
    expected = [line for line in oracle.splitlines() if line != ""]
    actual = [_format_decimal(v, 5).decode("ascii") for v in values]
    assert actual == expected
