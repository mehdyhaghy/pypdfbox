"""PDFBOX-6265 — cap the predictor row length computed from ``/DecodeParms``.

``PredictorOutputStream`` allocates *two* row buffers of
``(columns * colors * bits_per_component + 7) // 8`` bytes before a single
encoded byte is inspected, so a crafted ``/Colors`` / ``/BitsPerComponent``
/ ``/Columns`` triple is a cheap OOM. Upstream 3.0.9 rejects a row length
above 10,000,000 bytes and exposes
``Filter.SYSPROP_PREDICTOR_MAX_ROW_LENGTH`` to raise the cap for genuinely
high-resolution documents.
"""

import io

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.filter.filter import Filter
from pypdfbox.filter.predictor import Predictor
from pypdfbox.filter.predictor_output_stream import (
    _DEFAULT_MAX_ROW_LENGTH,
    PredictorOutputStream,
)

SYSPROP = Filter.SYSPROP_PREDICTOR_MAX_ROW_LENGTH


def _decode_parms(
    predictor: int, colors: int, bits_per_component: int, columns: int
) -> COSDictionary:
    parms = COSDictionary()
    parms.set_item(COSName.get_pdf_name("Predictor"), COSInteger.get(predictor))
    parms.set_item(COSName.get_pdf_name("Colors"), COSInteger.get(colors))
    parms.set_item(
        COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(bits_per_component)
    )
    parms.set_item(COSName.get_pdf_name("Columns"), COSInteger.get(columns))
    return parms


# ---------------------------------------------------------------------------
# the cap itself
# ---------------------------------------------------------------------------


def test_extreme_columns_rejected() -> None:
    with pytest.raises(OSError, match="Calculated row length is too high"):
        PredictorOutputStream(io.BytesIO(), 12, 1, 8, 100_000_000)


def test_error_message_names_every_decode_parm() -> None:
    with pytest.raises(OSError) as exc:
        PredictorOutputStream(io.BytesIO(), 12, 3, 16, 40_000_000)
    row_length = Predictor.calculate_row_length(3, 16, 40_000_000)
    assert str(exc.value) == (
        f"Calculated row length is too high: {row_length} "
        f"(colors: 3, bitsPerComponent: 16, columns: 40000000)"
    )


def test_extreme_bits_per_component_rejected() -> None:
    with pytest.raises(OSError, match="Calculated row length is too high"):
        PredictorOutputStream(io.BytesIO(), 12, 1, 1000, 2_000_000)


def test_wrap_predictor_rejects_extreme_decode_parms() -> None:
    """The cap has to fire through the real ``/DecodeParms`` entry point,
    not just the constructor."""
    parms = _decode_parms(12, 32, 8, 8_000_000)
    with pytest.raises(OSError, match="Calculated row length is too high"):
        Predictor.wrap_predictor(io.BytesIO(), parms)


def test_reasonable_row_length_is_accepted() -> None:
    out = io.BytesIO()
    stream = Predictor.wrap_predictor(out, _decode_parms(12, 3, 8, 4))
    try:
        assert isinstance(stream, PredictorOutputStream)
    finally:
        stream.close()


def test_boundary_row_length_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """``rowLength > maxRowLength`` — exactly at the cap must pass."""
    monkeypatch.setenv(SYSPROP, "100")
    # 1 colour x 8 bpc x 100 columns = exactly 100 bytes.
    stream = PredictorOutputStream(io.BytesIO(), 12, 1, 8, 100)
    stream.close()
    with pytest.raises(OSError, match="Calculated row length is too high"):
        PredictorOutputStream(io.BytesIO(), 12, 1, 8, 101)


# ---------------------------------------------------------------------------
# SYSPROP_PREDICTOR_MAX_ROW_LENGTH
# ---------------------------------------------------------------------------


def test_sysprop_constant_matches_upstream() -> None:
    assert SYSPROP == "org.apache.pdfbox.filter.predictormaxrowlength"


def test_sysprop_raises_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    columns = _DEFAULT_MAX_ROW_LENGTH + 1000
    with pytest.raises(OSError, match="Calculated row length is too high"):
        PredictorOutputStream(io.BytesIO(), 12, 1, 8, columns)

    monkeypatch.setenv(SYSPROP, str(columns + 1))
    stream = PredictorOutputStream(io.BytesIO(), 12, 1, 8, columns)
    stream.close()


@pytest.mark.parametrize("value", ["0", "-1", "not-a-number", ""])
def test_invalid_sysprop_values_keep_the_default(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(SYSPROP, value)
    # Default still enforced …
    with pytest.raises(OSError, match="Calculated row length is too high"):
        PredictorOutputStream(io.BytesIO(), 12, 1, 8, _DEFAULT_MAX_ROW_LENGTH + 1)
    # … and not tightened either.
    stream = PredictorOutputStream(io.BytesIO(), 12, 1, 8, 16)
    stream.close()


def test_negative_row_length_check_still_fires_first() -> None:
    """A negative ``/Columns`` keeps the pre-existing upstream message."""
    with pytest.raises(OSError, match="Calculated row length is negative"):
        PredictorOutputStream(io.BytesIO(), 12, 1, 8, -8)
