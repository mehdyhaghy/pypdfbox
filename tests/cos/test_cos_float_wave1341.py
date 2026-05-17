"""Wave 1341 coverage boost for ``pypdfbox.cos.cos_float``.

Targets the public ``coerce`` / ``equals`` / ``hash_code`` / ``to_string``
aliases, the NaN-canonicalization branch of ``_float_bits``, the
``__repr__`` no-original-form fallback, and ``_coerce``'s ±inf and
subnormal-flush edges. Pre-wave the module sat at 90.8 %; this lifts it
above 98 %.
"""

from __future__ import annotations

import math

from pypdfbox.cos import COSFloat
from pypdfbox.cos.cos_float import _coerce


# ---------------------------------------------------------------------------
# ``_coerce`` edge cases (module-level helper)
# ---------------------------------------------------------------------------
def test_coerce_passes_nan_through_unchanged() -> None:
    out = _coerce(float("nan"))
    assert math.isnan(out)


def test_coerce_clamps_positive_infinity() -> None:
    assert _coerce(math.inf) == 3.4028234663852886e38


def test_coerce_clamps_negative_infinity() -> None:
    assert _coerce(-math.inf) == -3.4028234663852886e38


def test_coerce_flushes_subnormal_to_zero() -> None:
    # ``5e-40`` is smaller than Float.MIN_NORMAL (1.175e-38), so coerce
    # rounds it down to 0.0 — mirrors upstream PDF spec Appendix C.
    assert _coerce(5e-40) == 0.0


def test_coerce_preserves_normal_value() -> None:
    assert _coerce(1.5) == 1.5


# ---------------------------------------------------------------------------
# Public ``coerce`` instance method
# ---------------------------------------------------------------------------
def test_instance_coerce_clamps_infinity() -> None:
    f = COSFloat(0.0)
    assert f.coerce(math.inf) == 3.4028234663852886e38
    assert f.coerce(-math.inf) == -3.4028234663852886e38


# ---------------------------------------------------------------------------
# ``equals`` upstream alias
# ---------------------------------------------------------------------------
def test_equals_returns_true_for_matching_cosfloat() -> None:
    a = COSFloat(1.5)
    b = COSFloat(1.5)
    assert a.equals(b) is True


def test_equals_returns_false_for_non_cosfloat() -> None:
    a = COSFloat(1.5)
    # ``__eq__`` returns ``NotImplemented`` for non-COSFloat; ``equals``
    # collapses that to ``False`` instead of leaking the sentinel.
    assert a.equals("not a cosfloat") is False
    assert a.equals(1.5) is False
    assert a.equals(None) is False


# ---------------------------------------------------------------------------
# ``hash_code`` upstream alias
# ---------------------------------------------------------------------------
def test_hash_code_matches_dunder_hash() -> None:
    f = COSFloat(2.25)
    assert f.hash_code() == hash(f)


def test_hash_code_for_nan_uses_canonical_bits() -> None:
    f = COSFloat(float("nan"))
    assert f.hash_code() == 0x7FC00000


# ---------------------------------------------------------------------------
# ``to_string`` upstream alias
# ---------------------------------------------------------------------------
def test_to_string_wraps_format_string() -> None:
    f = COSFloat("1.250")
    assert f.to_string() == "COSFloat{1.250}"


def test_to_string_for_float_constructed() -> None:
    f = COSFloat(3.5)
    assert f.to_string() == "COSFloat{3.5}"


# ---------------------------------------------------------------------------
# ``_float_bits`` NaN canonicalisation branch
# ---------------------------------------------------------------------------
def test_float_bits_collapses_nan_to_canonical() -> None:
    f = COSFloat(float("nan"))
    # 0x7FC00000 is Java's ``Float.NaN`` canonical bit pattern.
    assert f._float_bits() == 0x7FC00000


def test_two_nan_cosfloats_compare_equal() -> None:
    a = COSFloat(float("nan"))
    b = COSFloat(float("nan"))
    # Python's ``==`` says ``nan != nan``; our ``__eq__`` follows Java
    # ``Float.floatToIntBits`` and treats them as equal.
    assert a == b
    assert a.equals(b) is True


# ---------------------------------------------------------------------------
# ``__repr__`` no-original-form fallback
# ---------------------------------------------------------------------------
def test_repr_no_original_form_uses_value() -> None:
    f = COSFloat(2.5)
    # No original parsed string → fallback to ``COSFloat(<value>)``.
    assert repr(f) == "COSFloat(2.5)"


def test_repr_with_original_form_quotes_string() -> None:
    f = COSFloat("1.000")
    assert repr(f) == "COSFloat('1.000')"
