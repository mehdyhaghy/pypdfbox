"""
Hand-written tests for the upstream-named :class:`CCITTFaxFilter` alias.

The full codec is exercised by ``test_ccitt_fax_decode.py``; this
module verifies wiring and cross-instance interoperability.
"""

from __future__ import annotations

import io

from PIL import Image

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.filter import CCITTFaxDecode, CCITTFaxFilter, FilterFactory
from pypdfbox.filter.ccitt_fax_filter import (
    CCITTFaxFilter as DirectCCITTFaxFilter,
)


def _g4_strip(image: Image.Image) -> bytes:
    """Encode a 1-bit Pillow image as a Group 4 TIFF and return the
    encoded strip bytes (i.e. just the CCITT payload)."""
    buf = io.BytesIO()
    image.save(buf, format="TIFF", compression="group4")
    raw = buf.getvalue()
    parsed = Image.open(io.BytesIO(raw))
    offsets = parsed.tag_v2[273]
    counts = parsed.tag_v2[279]
    offset = offsets[0] if isinstance(offsets, tuple) else offsets
    count = counts[0] if isinstance(counts, tuple) else counts
    return raw[offset : offset + count]


def _decode_params(**kwargs: object) -> COSDictionary:
    params = COSDictionary()
    for key, value in kwargs.items():
        if isinstance(value, bool):
            params.set_boolean(key, value)
        elif isinstance(value, int):
            params.set_int(key, value)
        else:  # pragma: no cover — defensive
            raise TypeError(f"unsupported type for {key}: {type(value).__name__}")
    return params


def test_ccitt_fax_filter_is_ccitt_fax_decode_subclass() -> None:
    assert issubclass(CCITTFaxFilter, CCITTFaxDecode)


def test_ccitt_fax_filter_imports_from_package() -> None:
    assert CCITTFaxFilter is DirectCCITTFaxFilter


def test_factory_resolves_ccitt_fax_filter_long_name() -> None:
    inst = FilterFactory.get("CCITTFaxFilter")
    assert isinstance(inst, CCITTFaxFilter)


def test_factory_resolves_ccitt_fax_filter_via_cosname() -> None:
    inst = FilterFactory.get(COSName.get_pdf_name("CCITTFaxFilter"))
    assert isinstance(inst, CCITTFaxFilter)


def test_factory_ccitt_fax_decode_unchanged() -> None:
    long_filter = FilterFactory.get("CCITTFaxDecode")
    short_filter = FilterFactory.get("CCF")
    assert isinstance(long_filter, CCITTFaxDecode)
    assert long_filter is short_filter


def test_factory_is_registered_ccitt_fax_filter() -> None:
    assert FilterFactory.is_registered("CCITTFaxFilter")


def test_cross_class_round_trip_filter_decodes_decode_encoded() -> None:
    """Bytes encoded by ``CCITTFaxDecode`` must decode losslessly when
    fed back through the upstream-named ``CCITTFaxFilter`` subclass."""
    img = Image.new("1", (8, 4), 0)
    for x in range(0, 8, 2):
        for y in range(4):
            img.putpixel((x, y), 255)
    encoded = _g4_strip(img)

    params = _decode_params(K=-1, Columns=8, Rows=4)
    out = io.BytesIO()
    CCITTFaxFilter().decode(io.BytesIO(encoded), out, params)
    assert out.getvalue() == b"\xaa\xaa\xaa\xaa"
