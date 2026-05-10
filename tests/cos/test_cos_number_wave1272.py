"""Wave 1272: parity coverage for ``COSNumber.is_float`` (promoted from
upstream's ``private static`` ``isFloat`` helper)."""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_number import COSNumber


def test_is_float_with_decimal_point() -> None:
    assert COSNumber.is_float("1.5") is True


def test_is_float_with_exponent_lowercase() -> None:
    assert COSNumber.is_float("1e3") is True


def test_is_float_with_uppercase_exponent_returns_false() -> None:
    # Upstream only checks for lowercase 'e' — we mirror that surface area.
    assert COSNumber.is_float("1E3") is False


def test_is_float_integer_literal() -> None:
    assert COSNumber.is_float("42") is False
    assert COSNumber.is_float("-7") is False


def test_is_float_empty() -> None:
    assert COSNumber.is_float("") is False


def test_is_float_none_raises() -> None:
    with pytest.raises(TypeError):
        COSNumber.is_float(None)  # type: ignore[arg-type]
