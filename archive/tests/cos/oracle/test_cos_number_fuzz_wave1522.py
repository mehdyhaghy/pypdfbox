"""Live PDFBox differential parse-fuzz for the ``COSNumber.get(String)`` factory
and the ``COSInteger`` / ``COSFloat`` leaf accessors (pypdfbox parity wave 1522).

This is a *deeper* angle than ``test_cos_number_oracle.py`` (which pins dispatch
+ ``isValid`` + the raw accessor decimals): the ``CosNumberFuzzProbe`` oracle
additionally pins

* ``intValue()`` AS THE JVM ``(int)`` NARROWING CAST TRUNCATES IT — a
  ``COSInteger`` whose value exceeds signed-32-bit range wraps modulo ``2**32``.
  Python ints are unbounded, so before wave 1522 ``COSInteger.int_value()``
  returned the full value (e.g. ``2147483648`` instead of Java's wrapped
  ``-2147483648``; the ``OUT_OF_RANGE_MAX`` sentinel returned
  ``9223372036854775807`` instead of Java's ``Long.MAX_VALUE``-as-int ``-1``).
  ``int_value`` now truncates to int32 so the accessor matches upstream
  byte-for-byte. **REAL BUG FIXED THIS WAVE.**
* the small-value **caching identity** of ``COSInteger.get(long)`` — the
  inclusive ``-100..256`` window returns the *same* interned instance.
* the ``equals`` / ``hashCode`` contract via the per-instance ``hash``.

PINNED DIVERGENCE (unalignable): Java ``Long.parseLong`` accepts non-ASCII
Unicode decimal digits (``Character.digit``), so PDFBox parses ``"١٢٣"``
(Arabic-Indic) / ``"１２３"`` (fullwidth) as ``123``. pypdfbox restricts numeric
tokens to ASCII ``0``-``9`` (PDF number tokens are ASCII by spec; Java's
``Character.digit`` set is idiosyncratic — it rejects U+06F5 EXTENDED
ARABIC-INDIC FIVE even though it is a "digit"). Both sides are asserted on these
cases so the divergence is documented, not silently drifting.
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_number import COSNumber
from tests.oracle.harness import requires_oracle, run_probe_text


def _fbits_hex(value: float) -> str:
    """IEEE-754 single-precision bit pattern, lowercase hex, no leading zeros —
    matches Java ``Integer.toHexString(Float.floatToIntBits(f))``."""
    bits = struct.unpack(">I", struct.pack(">f", value))[0]
    return f"{bits:x}"


def _py_record(lit: str) -> str:
    """Render the same pipe-delimited record the ``CosNumberFuzzProbe`` emits."""
    try:
        n = COSNumber.get(lit)
    except (OSError, TypeError):
        return "error"
    if isinstance(n, COSInteger):
        again = COSInteger.get(n.long_value())
        first = COSInteger.get(n.long_value())
        cache = "true" if again is first else "false"
        return (
            f"int|valid={'true' if n.is_valid() else 'false'}"
            f"|int={n.int_value()}"
            f"|long={n.long_value()}"
            f"|fbits={_fbits_hex(n.float_value())}"
            f"|str={n.to_string()}"
            f"|cache={cache}"
            f"|hash={n.hash_code()}"
        )
    if isinstance(n, COSFloat):
        return (
            f"float"
            f"|int={n.int_value()}"
            f"|long={n.long_value()}"
            f"|fbits={_fbits_hex(n.float_value())}"
            f"|str={n.to_string()}"
            f"|hash={n.hash_code()}"
        )
    return "other"


# --------------------------------------------------------------------------- #
# Corpus. Each entry is (short_id, literal). Literals are passed to the probe as
# hex of their UTF-8 bytes so control bytes / whitespace / signs / non-ASCII
# digits survive the shell. IDs stay short (Windows 32 KB env-var cap on test
# IDs — see CLAUDE.md cross-platform notes).
# --------------------------------------------------------------------------- #
_CASES: tuple[tuple[str, str], ...] = (
    # ---- plain integers + sign / leading-zero forms ----
    ("int_plain", "10"),
    ("int_neg", "-5"),
    ("int_pos", "+3"),
    ("int_lead_zero", "007"),
    ("int_zero", "0"),
    ("int_neg_zero", "-0"),
    ("int_pos_zero", "+0"),
    ("int_many_zero", "0000000000000000000000000"),
    # ---- single-character fast path ----
    ("one_digit", "1"),
    ("one_dash", "-"),
    ("one_dot", "."),
    # ---- caching identity boundaries (-100..256 interned) ----
    ("cache_lo_edge", "-100"),
    ("cache_lo_out", "-101"),
    ("cache_hi_edge", "256"),
    ("cache_hi_out", "257"),
    ("cache_mid", "42"),
    # ---- int32 narrowing of intValue (the wave-1522 fix) ----
    ("int32_max", "2147483647"),
    ("int32_max_p1", "2147483648"),
    ("int32_wrap_4g", "4294967296"),
    ("int32_5g", "5000000000"),
    ("int32_min", "-2147483648"),
    ("int32_min_m1", "-2147483649"),
    # ---- Long boundary + overflow sentinels (PDFBOX-5176) ----
    ("long_max", "9223372036854775807"),
    ("long_max_p1", "9223372036854775808"),
    ("long_min", "-9223372036854775808"),
    ("long_min_m1", "-9223372036854775809"),
    ("huge_pos", "100000000000000000000"),
    ("huge_pos_signed", "+100000000000000000000"),
    ("huge_neg", "-100000000000000000000"),
    ("huge40", "9999999999999999999999999999999999999999"),
    ("huge40_neg", "-9999999999999999999999999999999999999999"),
    # ---- empty string -> OUT_OF_RANGE_MAX (NOT zero) ----
    ("empty", ""),
    # ---- floats: leading/trailing dot, signs ----
    ("flt_simple", "1.5"),
    ("flt_lead_dot", ".5"),
    ("flt_trail_dot", "5."),
    ("flt_neg_lead_dot", "-.5"),
    ("flt_pos_lead_dot", "+.5"),
    ("flt_int_dot", "12."),
    ("flt_neg_zero", "-0.0"),
    ("flt_zero", "0.0"),
    ("flt_dot_zero", ".0"),
    ("flt_zero_dot", "0."),
    ("flt_lead_zero_frac", "00.5"),
    # ---- exponent forms (lowercase e only routes to float) ----
    ("exp_e3", "1.0e3"),
    ("exp_e2", "1.5e2"),
    ("exp_big", "1e10"),
    ("exp_dot_e", "1.e5"),
    ("exp_zero", "0e0"),
    ("exp_zero_dot", "0.0e0"),
    ("upper_E", "1E2"),
    ("upper_E_neg", "1E-5"),
    # ---- float32 saturation / subnormal flush / tiny underflow ----
    ("flt_max", "3.4028235e38"),
    ("flt_over", "1e40"),
    ("flt_over_neg", "-1e40"),
    ("flt_min_subn", "1.4e-45"),
    ("flt_underflow", "1e-45"),
    ("tiny_frac", "0.0000000000000000000000000077"),
    ("big_real", "340282350000000000000000000000000000000.0"),
    # ---- malformed-real recovery (PDFBOX-2990 / -3500) ----
    ("rep_dbl_dash", "--16.33"),
    ("rep_zero_dash", "0.-262"),
    # ---- error / non-number inputs ----
    ("err_plus", "+"),
    ("err_abc", "abc"),
    ("err_dbl_dash", "--"),
    ("err_two_dots", "1.2.3"),
    ("err_hex", "0x10"),
    ("err_dot_e3", ".e3"),
    ("err_pp5", "++5"),
    ("err_pm5", "+-5"),
    ("err_mp5", "-+5"),
    ("err_pos_dot", "+."),
    ("err_neg_dot", "-."),
    ("err_embedded_alpha", "12a3"),
    ("err_e_bare", "1e"),
    ("err_e_plus", "1e+"),
    ("err_e_minus", "1e-"),
    ("err_two_e", "1e1e2"),
    ("err_nan", "NaN"),
    ("err_inf", "Infinity"),
    ("err_underscore", "1_000"),
    ("err_lead_ws", " 5"),
    ("err_trail_ws", "5 "),
    ("err_tab", "\t5"),
    ("err_four_dots", "...."),
    ("err_dot_dash_dot", "-.-"),
    # ---- non-ASCII digits: PINNED DIVERGENCE (Java parses, pypdfbox errors) ----
    ("uni_arabic", "١٢٣"),
    ("uni_fullwidth", "１２３"),
    ("uni_ext_arabic", "۵"),
)

_IDS = [c[0] for c in _CASES]
_LITS = [c[1] for c in _CASES]

# Literals whose Java/pypdfbox records intentionally differ (non-ASCII digit
# leniency). Asserted both-sides below so the divergence is pinned, not drifting.
_PINNED_DIVERGENT = {"uni_arabic", "uni_fullwidth"}


@requires_oracle
@pytest.mark.parametrize(("cid", "lit"), zip(_IDS, _LITS, strict=True), ids=_IDS)
def test_cos_number_get_matches_pdfbox(cid: str, lit: str) -> None:
    java = run_probe_text("CosNumberFuzzProbe", lit.encode("utf-8").hex()).strip()
    py = _py_record(lit)
    if cid in _PINNED_DIVERGENT:
        # Java accepts Unicode decimal digits; pypdfbox restricts to ASCII.
        assert java != "error"
        assert py == "error"
    else:
        assert py == java


# --------------------------------------------------------------------------- #
# Oracle-independent regression pins for the wave-1522 int32-narrowing fix.
# These document the fixed behaviour on a machine without the live oracle.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("value", "expected_int"),
    [
        (2147483647, 2147483647),
        (2147483648, -2147483648),
        (4294967296, 0),
        (5000000000, 705032704),
        (-2147483648, -2147483648),
        (-2147483649, 2147483647),
        (2**63 - 1, -1),
        (-(2**63), 0),
        (100, 100),
        (-100, -100),
    ],
    ids=[
        "i32max",
        "i32max_p1",
        "wrap4g",
        "five_g",
        "i32min",
        "i32min_m1",
        "long_max",
        "long_min",
        "small_pos",
        "small_neg",
    ],
)
def test_int_value_truncates_to_int32(value: int, expected_int: int) -> None:
    assert COSInteger.get(value).int_value() == expected_int
    # long_value() keeps the full (Java would store this as a 64-bit long).
    assert COSInteger.get(value).long_value() == value


def test_out_of_range_sentinels_int_value() -> None:
    """The OUT_OF_RANGE_* sentinels expose Long.MAX/MIN truncated to int32."""
    assert COSInteger.OUT_OF_RANGE_MAX.int_value() == -1
    assert COSInteger.OUT_OF_RANGE_MIN.int_value() == 0
    assert COSInteger.OUT_OF_RANGE_MAX.long_value() == 2**63 - 1
    assert COSInteger.OUT_OF_RANGE_MIN.long_value() == -(2**63)
    assert not COSInteger.OUT_OF_RANGE_MAX.is_valid()
    assert not COSInteger.OUT_OF_RANGE_MIN.is_valid()


def test_small_int_caching_identity() -> None:
    """COSInteger.get caches the inclusive -100..256 window (same instance)."""
    for v in (-100, -1, 0, 1, 256):
        assert COSInteger.get(v) is COSInteger.get(v)
    for v in (-101, 257, 1000):
        assert COSInteger.get(v) is not COSInteger.get(v)
