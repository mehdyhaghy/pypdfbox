"""Hand-written tests for :class:`CCITTFactory`.

Covers the 1-bit ``create_from_image`` path: G4 filter wiring,
``/DecodeParms`` carrying ``K=-1`` plus real columns/rows, raw-bytes
round-trip through :class:`CCITTFaxDecode`, and the input-validation
guards (non-image / non-1-bit-image rejection).
"""
from __future__ import annotations

import io

import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.filter import CCITTFaxDecode
from pypdfbox.pdmodel.graphics.image import CCITTFactory, PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument


# ---------------------------------------------------------------------------
# create_from_image
# ---------------------------------------------------------------------------


def test_create_from_image_returns_pd_image_x_object() -> None:
    document = PDDocument()
    src = Image.new("1", (32, 16), color=1)

    image_x = CCITTFactory.create_from_image(document, src)
    assert isinstance(image_x, PDImageXObject)
    assert image_x.get_width() == 32
    assert image_x.get_height() == 16
    assert image_x.get_bits_per_component() == 1


def test_create_from_image_uses_ccitt_fax_decode_filter() -> None:
    """``/Filter`` must be ``/CCITTFaxDecode`` (Group 4 via ``K=-1``)."""
    document = PDDocument()
    src = Image.new("1", (24, 8), color=0)

    image_x = CCITTFactory.create_from_image(document, src)
    filt = image_x.get_filter()
    assert isinstance(filt, COSName)
    assert filt.name == "CCITTFaxDecode"


def test_create_from_image_color_space_is_device_gray() -> None:
    document = PDDocument()
    src = Image.new("1", (8, 8), color=1)

    image_x = CCITTFactory.create_from_image(document, src)
    cs = image_x.get_color_space_cos_object()
    assert isinstance(cs, COSName)
    assert cs.name == "DeviceGray"


def test_create_from_image_decode_parms_match_dimensions() -> None:
    """``/DecodeParms`` must carry ``K=-1`` plus the real columns/rows."""
    document = PDDocument()
    src = Image.new("1", (40, 24), color=1)

    image_x = CCITTFactory.create_from_image(document, src)
    cos = image_x.get_cos_object()
    assert isinstance(cos, COSStream)

    decode_parms = cos.get_dictionary_object("DecodeParms")
    assert isinstance(decode_parms, COSDictionary)
    assert decode_parms.get_int("K", 0) == -1
    assert decode_parms.get_int("Columns", 0) == 40
    assert decode_parms.get_int("Rows", 0) == 24


def test_create_from_image_round_trips_through_decoder() -> None:
    """Encoded body must decode back to the original packed bitstream."""
    document = PDDocument()
    src = Image.new("1", (64, 32), color=1)
    # Sparse pattern: black pixels along the diagonal.
    for x in range(32):
        src.putpixel((x, x), 0)

    image_x = CCITTFactory.create_from_image(document, src)
    cos = image_x.get_cos_object()
    assert isinstance(cos, COSStream)

    raw = cos.get_raw_data()
    out = io.BytesIO()
    CCITTFaxDecode().decode(io.BytesIO(raw), out, cos)
    assert out.getvalue() == src.tobytes()


def test_create_from_image_rejects_non_one_bit() -> None:
    """Upstream raises ``IllegalArgumentException`` for non-1-bit input."""
    document = PDDocument()
    src = Image.new("L", (8, 8), color=128)
    with pytest.raises(ValueError):
        CCITTFactory.create_from_image(document, src)


def test_create_from_image_rejects_non_image() -> None:
    document = PDDocument()
    with pytest.raises(TypeError):
        CCITTFactory.create_from_image(document, b"not an image")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# class shape
# ---------------------------------------------------------------------------


def test_ccitt_factory_is_static_only() -> None:
    """Upstream marks CCITTFactory ``final`` with a private constructor —
    instantiation is forbidden. The Python port enforces the same by
    raising in ``__init__``."""
    with pytest.raises(TypeError):
        CCITTFactory()
