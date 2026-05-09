from __future__ import annotations

import io
from typing import BinaryIO

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.filter.decode_result import DecodeResult
from pypdfbox.pdmodel.graphics.color import PDDeviceRGB
from pypdfbox.pdmodel.graphics.image import PDInlineImage
from pypdfbox.pdmodel.graphics.image import pd_inline_image as inline_mod


def _params(width: int = 1, height: int = 1, bpc: int = 8) -> COSDictionary:
    params = COSDictionary()
    params.set_int("W", width)
    params.set_int("H", height)
    params.set_int("BPC", bpc)
    return params


def _metadata_only_image(params: COSDictionary, raw_data: bytes = b"") -> PDInlineImage:
    image = PDInlineImage.__new__(PDInlineImage)
    image._parameters = params
    image._resources = None
    image._raw_data = raw_data
    image._decoded_data = b""
    return image


def test_wave719_decode_result_parameters_are_merged(monkeypatch: pytest.MonkeyPatch) -> None:
    class RepairingFilter:
        def decode(
            self,
            encoded: BinaryIO,
            decoded: BinaryIO,
            parameters: COSDictionary | None = None,
            index: int = 0,
        ) -> DecodeResult:
            assert encoded.read() == b"encoded"
            assert index == 0
            decoded.write(b"decoded")
            repaired = COSDictionary()
            repaired.set_int("Columns", 17)
            return DecodeResult(parameters=repaired, bytes_written=7)

    monkeypatch.setattr(
        inline_mod.FilterFactory,
        "get_filter",
        classmethod(lambda cls, name: RepairingFilter()),
    )
    params = _params(width=7)
    params.set_item("F", COSName.get_pdf_name("SyntheticDecode"))

    image = PDInlineImage(params, b"encoded", None)

    assert image.get_data() == b"decoded"
    assert params.get_int("Columns") == 17


def test_wave719_indexed_color_space_reports_unresolved_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        inline_mod.PDColorSpace,
        "create",
        staticmethod(lambda base, resources=None: None),
    )
    indexed = COSArray()
    indexed.add(COSName.get_pdf_name("I"))
    indexed.add(COSName.get_pdf_name("RGB"))
    indexed.add(COSInteger.ZERO)
    indexed.add(COSString(b"\x00\x00\x00"))
    params = _params()
    params.set_item("CS", indexed)

    with pytest.raises(OSError, match="unsupported indexed color space"):
        PDInlineImage(params, b"\x00", None).get_color_space()


def test_wave719_named_array_color_space_reports_unresolved_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        inline_mod.PDColorSpace,
        "create",
        staticmethod(lambda base, resources=None: None),
    )
    cal_gray = COSArray()
    cal_gray.add(COSName.get_pdf_name("CalGray"))
    cal_gray.add(COSDictionary())
    params = _params()
    params.set_item("CS", cal_gray)

    with pytest.raises(OSError, match="unsupported inline image color space"):
        PDInlineImage(params, b"\x00", None).get_color_space()


def test_wave719_device_color_space_setter_uses_name_when_cos_object_absent() -> None:
    image = PDInlineImage(_params(), b"\x00\x00\x00", None)

    image.set_color_space(PDDeviceRGB.INSTANCE)

    assert image.get_cos_object().get_name("CS") == "DeviceRGB"


def test_wave719_color_key_mask_is_none_for_non_array_mask() -> None:
    params = _params()
    params.set_item("Mask", COSName.get_pdf_name("NotAnArray"))

    assert PDInlineImage(params, b"\x00", None).get_color_key_mask() is None


def test_wave719_to_pil_image_reads_jpx_stop_filter_payload() -> None:
    payload = io.BytesIO()
    Image.new("RGB", (1, 1), (9, 20, 31)).save(payload, format="PNG")
    params = _params()
    params.set_item("F", COSName.get_pdf_name("JPXDecode"))
    image = _metadata_only_image(params, payload.getvalue())

    out = image.to_pil_image()

    assert out is not None
    assert out.mode == "RGB"
    assert out.getpixel((0, 0)) == (9, 20, 31)


def test_wave719_to_pil_image_returns_none_for_unrendered_color_space() -> None:
    cal_gray = COSArray()
    cal_gray.add(COSName.get_pdf_name("CalGray"))
    cal_gray.add(COSDictionary())
    params = _params()
    params.set_item("CS", cal_gray)

    assert PDInlineImage(params, b"\x80", None).to_pil_image() is None
