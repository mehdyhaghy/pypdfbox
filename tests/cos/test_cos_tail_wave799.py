from __future__ import annotations

import pytest

from pypdfbox.cos import COSFloat


def test_wave799_cos_float_clean_literal_keeps_original_form() -> None:
    # A literal that parses straight through Float.parseFloat keeps its raw
    # bytes (valueAsString == the original string) so the writer round-trips.
    value = COSFloat("1.25")

    assert value.float_value() == pytest.approx(1.25)
    assert value.get_original_form() == "1.25"


def test_wave799_cos_float_rejects_unrepairable_misplaced_minus() -> None:
    # ``1-2-3`` matches none of the three malformed-number repair patterns
    # (``--`` prefix / ``^0\.0*-\d+`` / ``^-\d+\.-\d+``), so upstream
    # COSFloat(String) raises IOException "Error expected floating point
    # number actual='1-2-3'".
    with pytest.raises(OSError, match="Error expected floating point number"):
        COSFloat("1-2-3")
