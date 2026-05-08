from __future__ import annotations

import io
import zlib

from pypdfbox.cos import COSArray, COSDictionary
from pypdfbox.filter import FlateDecode


def test_wave300_flate_decode_uses_indexed_decode_parms_array() -> None:
    encoded_rows = bytearray()
    encoded_rows.append(2)
    encoded_rows.extend(bytes([10, 20, 30, 40]))
    encoded_rows.append(2)
    encoded_rows.extend(bytes([1, 2, 3, 4]))

    decode_params = COSDictionary()
    decode_params.set_int("Predictor", 12)
    decode_params.set_int("Columns", 4)
    decode_params.set_int("Colors", 1)
    decode_params.set_int("BitsPerComponent", 8)

    all_decode_params = COSArray()
    all_decode_params.add(COSDictionary())
    all_decode_params.add(decode_params)

    stream_params = COSDictionary()
    stream_params.set_item("DecodeParms", all_decode_params)

    out = io.BytesIO()
    result = FlateDecode().decode(
        io.BytesIO(zlib.compress(bytes(encoded_rows))),
        out,
        stream_params,
        index=1,
    )

    assert out.getvalue() == bytes([10, 20, 30, 40, 11, 22, 33, 44])
    assert result.parameters is stream_params
