"""Wave 1286 tests for :class:`PredictorEncoder.prepare_predictor_pd_image`.

Pins the post-redesign behaviour: the helper now actually splices the
deflate-compressed predicted payload into a fresh COSStream with the
right ``/Filter`` / ``/DecodeParms`` block, instead of always returning
``None`` for the upstream-parity stub.
"""

from __future__ import annotations

import io
import zlib

import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.graphics.image.predictor_encoder import PredictorEncoder


def _make_encoder(mode: str, width: int = 4, height: int = 3) -> PredictorEncoder:
    document = PDDocument()
    image = Image.new(mode, (width, height))
    return PredictorEncoder(document, image)


def _make_encoded_payload(payload: bytes) -> io.BytesIO:
    return io.BytesIO(zlib.compress(payload))


def test_prepare_predictor_pd_image_rgb_round_trip() -> None:
    """RGB source → ``/DeviceRGB``, predictor block populated."""
    encoder = _make_encoder("RGB", width=4, height=3)
    buf = _make_encoded_payload(b"raw rgb payload" * 4)

    image_x_object = encoder.prepare_predictor_pd_image(buf, bits_per_component=8)

    assert isinstance(image_x_object, PDImageXObject)
    cos = image_x_object.get_cos_object()
    assert cos.get_name(COSName.get_pdf_name("Type")) == "XObject"
    assert cos.get_name(COSName.get_pdf_name("Subtype")) == "Image"
    assert cos.get_int(COSName.get_pdf_name("Width")) == 4
    assert cos.get_int(COSName.get_pdf_name("Height")) == 3
    assert cos.get_int(COSName.get_pdf_name("BitsPerComponent")) == 8
    assert cos.get_name(COSName.get_pdf_name("ColorSpace")) == "DeviceRGB"
    # /Filter is set to FlateDecode (single-name form, not array).
    assert cos.get_name(COSName.FILTER) == "FlateDecode"  # type: ignore[attr-defined]

    decode = cos.get_dictionary_object(COSName.get_pdf_name("DecodeParms"))
    assert isinstance(decode, COSDictionary)
    assert decode.get_int(COSName.get_pdf_name("Predictor")) == 15
    assert decode.get_int(COSName.get_pdf_name("Columns")) == 4
    assert decode.get_int(COSName.get_pdf_name("Colors")) == 3
    assert decode.get_int(COSName.get_pdf_name("BitsPerComponent")) == 8


def test_prepare_predictor_pd_image_gray_uses_devicegray() -> None:
    encoder = _make_encoder("L", width=2, height=2)
    buf = _make_encoded_payload(b"gray-payload")

    image_x_object = encoder.prepare_predictor_pd_image(buf, bits_per_component=8)
    assert image_x_object is not None
    cos = image_x_object.get_cos_object()
    assert cos.get_name(COSName.get_pdf_name("ColorSpace")) == "DeviceGray"
    decode = cos.get_dictionary_object(COSName.get_pdf_name("DecodeParms"))
    assert isinstance(decode, COSDictionary)
    assert decode.get_int(COSName.get_pdf_name("Colors")) == 1


def test_prepare_predictor_pd_image_cmyk_uses_devicecmyk() -> None:
    encoder = _make_encoder("CMYK", width=2, height=2)
    buf = _make_encoded_payload(b"cmyk-payload")

    image_x_object = encoder.prepare_predictor_pd_image(buf, bits_per_component=8)
    assert image_x_object is not None
    cos = image_x_object.get_cos_object()
    assert cos.get_name(COSName.get_pdf_name("ColorSpace")) == "DeviceCMYK"
    decode = cos.get_dictionary_object(COSName.get_pdf_name("DecodeParms"))
    assert isinstance(decode, COSDictionary)
    assert decode.get_int(COSName.get_pdf_name("Colors")) == 4


def test_prepare_predictor_pd_image_rgba_drops_alpha_for_color_count() -> None:
    """RGBA has an alpha channel; ``/Colors`` only counts color
    components, so ``RGBA`` still yields ``/Colors 3``."""
    encoder = _make_encoder("RGBA", width=1, height=1)
    buf = _make_encoded_payload(b"rgba-payload")

    image_x_object = encoder.prepare_predictor_pd_image(buf, bits_per_component=8)
    assert image_x_object is not None
    cos = image_x_object.get_cos_object()
    assert cos.get_name(COSName.get_pdf_name("ColorSpace")) == "DeviceRGB"
    decode = cos.get_dictionary_object(COSName.get_pdf_name("DecodeParms"))
    assert isinstance(decode, COSDictionary)
    assert decode.get_int(COSName.get_pdf_name("Colors")) == 3


def test_prepare_predictor_pd_image_empty_stream_returns_none() -> None:
    encoder = _make_encoder("RGB")
    assert encoder.prepare_predictor_pd_image(io.BytesIO(), bits_per_component=8) is None


def test_prepare_predictor_pd_image_no_scratch_file_returns_none() -> None:
    """A fake document without ``get_document().scratch_file`` falls
    back to ``None`` so the caller can use ``LosslessFactory`` instead."""

    class _FakeDoc:  # no get_document method
        pass

    encoder = PredictorEncoder(_FakeDoc(), Image.new("RGB", (2, 2)))  # type: ignore[arg-type]
    buf = _make_encoded_payload(b"x")
    assert encoder.prepare_predictor_pd_image(buf, bits_per_component=8) is None


def test_prepare_predictor_pd_image_stores_compressed_payload_verbatim() -> None:
    """The bytes the caller passes in are written verbatim — the
    predictor encoder does not re-deflate them."""
    encoder = _make_encoder("RGB", width=2, height=2)
    raw_payload = b"row-1-x0row-2-x1"
    compressed = zlib.compress(raw_payload)
    buf = io.BytesIO(compressed)

    image_x_object = encoder.prepare_predictor_pd_image(buf, bits_per_component=8)
    assert image_x_object is not None
    cos = image_x_object.get_cos_object()
    # Raw payload on disk is the compressed bytes the caller supplied.
    assert cos.get_raw_data() == compressed
    # /Length matches.
    assert cos.get_int(COSName.get_pdf_name("Length")) == len(compressed)


@pytest.mark.parametrize("bpc", [1, 2, 4, 8, 16])
def test_prepare_predictor_pd_image_propagates_bits_per_component(bpc: int) -> None:
    encoder = _make_encoder("L", width=2, height=2)
    image_x_object = encoder.prepare_predictor_pd_image(
        _make_encoded_payload(b"x"), bits_per_component=bpc
    )
    assert image_x_object is not None
    cos = image_x_object.get_cos_object()
    assert cos.get_int(COSName.get_pdf_name("BitsPerComponent")) == bpc
    decode = cos.get_dictionary_object(COSName.get_pdf_name("DecodeParms"))
    assert isinstance(decode, COSDictionary)
    assert decode.get_int(COSName.get_pdf_name("BitsPerComponent")) == bpc
