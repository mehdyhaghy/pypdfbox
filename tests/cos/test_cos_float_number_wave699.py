from __future__ import annotations

import math

import pytest

from pypdfbox.cos.cos_float import COSFloat
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_number import COSNumber


def test_wave699_cos_float_nan_preserved_through_float32_helper() -> None:
    value = COSFloat(math.nan)

    assert math.isnan(value.value)


def test_wave699_cos_float_rejects_bad_decimal_literal() -> None:
    with pytest.raises(OSError, match="not a number"):
        COSFloat("1.2.3")


def test_wave699_cos_float_format_plain_number_without_original() -> None:
    value = COSFloat(2.5)

    assert value.format_string() == repr(value.value)


def test_wave699_cos_float_not_equal_to_unrelated_object() -> None:
    assert (COSFloat(1.0) == object()) is False


def test_wave699_cos_float_repr_uses_original_literal_when_present() -> None:
    assert repr(COSFloat("2.500")) == "COSFloat('2.500')"


def test_wave699_cos_number_abstract_methods_raise() -> None:
    class _Number(COSNumber):
        def accept(self, visitor: object) -> object:
            return visitor

    number = _Number()

    with pytest.raises(NotImplementedError):
        number.float_value()
    with pytest.raises(NotImplementedError):
        number.int_value()
    with pytest.raises(NotImplementedError):
        number.long_value()


def test_wave699_cos_number_get_rejects_none() -> None:
    with pytest.raises(TypeError, match="value is None"):
        COSNumber.get(None)  # type: ignore[arg-type]


def test_wave699_cos_number_get_wraps_float_parse_errors() -> None:
    with pytest.raises(OSError, match="not a number"):
        COSNumber.get("1.2.3")


def test_wave699_cos_number_get_out_of_range_min_sentinel() -> None:
    assert COSNumber.get(str(-(2**63) - 1)) is COSInteger.OUT_OF_RANGE_MIN
