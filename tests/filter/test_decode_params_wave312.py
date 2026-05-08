from __future__ import annotations

import io
from typing import Any, cast

from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSObject
from pypdfbox.filter import CCITTFaxDecode, LZWDecode


def _indexed_decode_params(params: COSDictionary, index: int = 1) -> COSDictionary:
    array = COSArray()
    for _ in range(index):
        array.add(COSDictionary())
    array.add(COSObject(312, 0, resolved=params))

    stream_params = COSDictionary()
    stream_params.set_item("DecodeParms", array)
    return stream_params


def _png_up_encode(data: bytes, columns: int) -> bytes:
    rows = [data[i : i + columns] for i in range(0, len(data), columns)]
    out = bytearray()
    previous = bytes(columns)
    for row in rows:
        out.append(2)
        out.extend((value - prior) & 0xFF for value, prior in zip(row, previous, strict=True))
        previous = row
    return bytes(out)


def test_wave312_lzw_decode_uses_indirect_indexed_decode_params() -> None:
    raw = bytes([10, 20, 30, 40, 11, 22, 33, 44])
    predictor_encoded = _png_up_encode(raw, columns=4)

    encoded = io.BytesIO()
    LZWDecode().encode(io.BytesIO(predictor_encoded), encoded)

    lzw_params = COSDictionary()
    lzw_params.set_int("Predictor", 12)
    lzw_params.set_int("Columns", 4)

    decoded = io.BytesIO()
    LZWDecode().decode(
        io.BytesIO(encoded.getvalue()),
        decoded,
        _indexed_decode_params(lzw_params),
        index=1,
    )

    assert decoded.getvalue() == raw


def _g4_strip(image: Image.Image) -> bytes:
    tiff = io.BytesIO()
    image.save(tiff, format="TIFF", compression="group4")

    with Image.open(io.BytesIO(tiff.getvalue())) as parsed:
        tag_v2 = cast(Any, parsed).tag_v2
        offsets = tag_v2[273]
        counts = tag_v2[279]

    offset = offsets[0] if isinstance(offsets, tuple) else offsets
    count = counts[0] if isinstance(counts, tuple) else counts
    return tiff.getvalue()[offset : offset + count]


def test_wave312_ccitt_decode_uses_indirect_indexed_decode_params() -> None:
    image = Image.new("1", (8, 2), 0)
    for x in range(0, 8, 2):
        for y in range(2):
            image.putpixel((x, y), 255)

    ccitt_params = COSDictionary()
    ccitt_params.set_int("K", -1)
    ccitt_params.set_int("Columns", 8)
    ccitt_params.set_int("Rows", 2)

    decoded = io.BytesIO()
    CCITTFaxDecode().decode(
        io.BytesIO(_g4_strip(image)),
        decoded,
        _indexed_decode_params(ccitt_params),
        index=1,
    )

    assert decoded.getvalue() == image.tobytes()
