from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
    PDImageXObject,
    _decode_devicen_to_rgb,
)


def _image() -> PDImageXObject:
    return PDImageXObject(COSStream())


def test_wave667_absent_color_space_returns_none_for_non_stencil() -> None:
    image = _image()

    assert image.get_color_space() is None


def test_wave667_clear_oc_alias_removes_optional_content_dictionary() -> None:
    image = _image()
    image.get_cos_object().set_item(COSName.get_pdf_name("OC"), COSDictionary())

    assert image.has_optional_content() is True
    image.clear_oc()
    assert image.has_optional_content() is False


def test_wave667_non_stream_cos_object_paths_return_false_or_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = _image()
    monkeypatch.setattr(image, "get_cos_object", lambda: COSDictionary())

    assert image.get_suffix() is None
    assert image.is_jbig2() is False
    assert image.is_jpeg() is False
    assert image.is_jpx() is False
    assert image.is_ccittfax() is False
    assert image.to_pil_image() is None


def test_wave667_to_pil_image_rejects_short_gray_and_unknown_raw_data() -> None:
    gray = _image()
    gray.set_width(2)
    gray.set_height(1)
    gray.set_bits_per_component(8)
    gray.set_color_space("DeviceGray")
    gray.get_cos_object().set_raw_data(b"\x7f")

    assert gray.to_pil_image() is None

    unknown = _image()
    unknown.set_width(1)
    unknown.set_height(1)
    unknown.set_bits_per_component(8)
    unknown.get_cos_object().set_raw_data(b"")

    assert unknown.to_pil_image() is None


class _DeviceNWithoutToRGB:
    def get_number_of_components(self) -> int:
        return 2

    def get_name(self) -> str:
        return "DeviceN"


def test_wave667_devicen_without_to_rgb_uses_luminance_fallback() -> None:
    rendered = _decode_devicen_to_rgb(
        _DeviceNWithoutToRGB(), bytes([10, 30, 100, 140]), 2, 1
    )

    assert rendered is not None
    assert [rendered.getpixel((x, 0)) for x in range(2)] == [
        (20, 20, 20),
        (120, 120, 120),
    ]
