import io
import zlib

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import FlateDecode, LZWDecode
from pypdfbox.filter._predictor import decode_predictor_row, predict, unpredict


def _flate_params(**values: int) -> COSDictionary:
    params = COSDictionary()
    for key, value in values.items():
        params.set_int(key, value)
    return params


def _lzw_params(**values: int) -> COSDictionary:
    inner = _flate_params(**values)
    outer = COSDictionary()
    outer.set_item("DecodeParms", inner)
    return outer


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("Columns", 0),
        ("Colors", 0),
        ("BitsPerComponent", 0),
    ],
)
def test_predictor_rejects_non_positive_geometry(field: str, value: int) -> None:
    params = {"Predictor": 12, "Columns": 4, "Colors": 1, "BitsPerComponent": 8}
    params[field] = value

    with pytest.raises(OSError, match=field):
        predict(
            b"\x00\x01\x02\x03",
            params["Predictor"],
            params["Columns"],
            params["Colors"],
            params["BitsPerComponent"],
        )
    with pytest.raises(OSError, match=field):
        unpredict(
            b"\x00\x01\x02\x03\x04",
            params["Predictor"],
            params["Columns"],
            params["Colors"],
            params["BitsPerComponent"],
        )


def test_decode_predictor_row_rejects_short_previous_row() -> None:
    row = bytearray(b"\x01\x02\x03\x04")

    with pytest.raises(OSError, match="previous predictor row too short"):
        decode_predictor_row(
            12,
            colors=1,
            bits_per_component=8,
            columns=4,
            actline=row,
            lastline=b"\x00\x00",
        )


def test_flate_decode_zero_color_predictor_params_raises() -> None:
    # /Colors 0 makes calculateRowLength == 0; PDFBox 3.0.9's
    # PredictorOutputStream rejects a non-positive row length (PDFBOX-6304)
    # instead of consuming the bytes as zero-length rows.
    params = _flate_params(Predictor=12, Columns=4, Colors=0, BitsPerComponent=8)
    encoded = zlib.compress(b"\x00\x01\x02\x03\x04")

    out = io.BytesIO()
    with pytest.raises(OSError, match="Calculated row length is not positive"):
        FlateDecode().decode(io.BytesIO(encoded), out, params)


def test_lzw_encode_rejects_zero_column_predictor_params() -> None:
    params = _lzw_params(Predictor=12, Columns=0, Colors=1, BitsPerComponent=8)

    with pytest.raises(OSError, match="invalid /Columns 0"):
        LZWDecode().encode(io.BytesIO(b"\x00\x01\x02\x03"), io.BytesIO(), params)
