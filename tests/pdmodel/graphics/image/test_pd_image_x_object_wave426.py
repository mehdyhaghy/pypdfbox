from __future__ import annotations

import io

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.graphics.color import PDDeviceRGB
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
    PDImageXObject,
    _clamp01,
    _decode_devicen_to_rgb,
    _luminance_fallback,
)


def _image() -> PDImageXObject:
    return PDImageXObject(COSStream())


def test_wave426_color_space_setter_accepts_pdcolorspace_name_and_none() -> None:
    image = _image()

    image.set_color_space(PDDeviceRGB.INSTANCE)
    assert image.get_color_space_cos_object() == PDDeviceRGB.INSTANCE.get_cos_object()
    assert image.get_color_space().get_name() == "DeviceRGB"

    image.get_cos_object().set_item(
        COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceGray")
    )
    image.set_color_space(None)
    assert image.get_color_space_cos_object() is None
    assert image.has_color_space() is False


def test_wave426_get_filter_ignores_invalid_filter_object() -> None:
    image = _image()
    image.get_cos_object().set_item(COSName.FILTER, COSDictionary())  # type: ignore[attr-defined]

    assert image.get_filter() is None


def test_wave426_decode_and_matte_reject_non_numeric_arrays() -> None:
    image = _image()
    decode = COSArray()
    decode.add(COSFloat(0.0))
    decode.add(COSName.get_pdf_name("NotNumber"))
    image.set_decode_array(decode)

    matte = COSArray()
    matte.add(COSInteger.get(1))
    matte.add(COSName.get_pdf_name("NotNumber"))
    image.get_cos_object().set_item(COSName.get_pdf_name("Matte"), matte)

    assert image.get_decode() is None
    assert image.has_decode() is False
    assert image.get_decode_array() is decode
    assert image.get_matte() is None
    assert image.has_matte() is False
    assert image.get_matte_array() is matte


def test_wave426_smask_in_data_defaults_round_trips_and_rejects_invalid_values() -> None:
    image = _image()

    assert image.get_smask_in_data() == 0
    for value in (0, 1, 2):
        image.set_smask_in_data(value)
        assert image.get_smask_in_data() == value

    with pytest.raises(ValueError, match="/SMaskInData must be 0, 1, or 2"):
        image.set_smask_in_data(3)


def test_wave426_clear_aliases_remove_entries() -> None:
    image = _image()
    image.set_mask(_image())
    image.set_soft_mask(_image())
    image.set_decode([0.0, 1.0])
    image.set_matte([0.5])

    image.clear_mask()
    image.clear_soft_mask()
    image.clear_decode()
    image.clear_matte()

    assert image.has_mask() is False
    assert image.has_soft_mask() is False
    assert image.has_decode() is False
    assert image.has_matte() is False


def test_wave426_to_pil_image_rejects_bad_dimensions_and_bpc() -> None:
    image = _image()
    assert image.to_pil_image() is None

    image.set_width(1)
    image.set_height(1)
    image.set_bits_per_component(4)
    image.get_cos_object().set_raw_data(b"\x00")
    image.set_color_space("DeviceGray")
    assert image.to_pil_image() is None


def test_wave426_to_pil_image_decodes_raw_rgb_gray_and_short_data() -> None:
    rgb = _image()
    rgb.set_width(2)
    rgb.set_height(1)
    rgb.set_bits_per_component(8)
    rgb.set_color_space("DeviceRGB")
    rgb.get_cos_object().set_raw_data(bytes([255, 0, 0, 0, 128, 255]))
    rendered_rgb = rgb.to_pil_image()
    assert rendered_rgb is not None
    assert rendered_rgb.mode == "RGB"
    assert list(rendered_rgb.getdata()) == [(255, 0, 0), (0, 128, 255)]

    gray = _image()
    gray.set_width(2)
    gray.set_height(1)
    gray.set_bits_per_component(8)
    gray.set_color_space("DeviceGray")
    gray.get_cos_object().set_raw_data(bytes([0, 200]))
    rendered_gray = gray.to_pil_image()
    assert rendered_gray is not None
    assert rendered_gray.mode == "RGB"
    assert list(rendered_gray.getdata()) == [(0, 0, 0), (200, 200, 200)]

    short = _image()
    short.set_width(2)
    short.set_height(1)
    short.set_bits_per_component(8)
    short.set_color_space("DeviceRGB")
    short.get_cos_object().set_raw_data(b"\x00")
    assert short.to_pil_image() is None


def test_wave426_to_pil_image_decodes_jpx_alias_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    image = _image()
    image.set_width(1)
    image.set_height(1)
    image.set_bits_per_component(8)
    image.get_cos_object().set_raw_data(b"encoded-jpx")
    image.get_cos_object().set_item(COSName.FILTER, COSName.get_pdf_name("JPX"))  # type: ignore[attr-defined]

    opened_payloads: list[bytes] = []

    def fake_open(stream: io.BytesIO) -> Image.Image:
        opened_payloads.append(stream.read())
        return Image.new("RGB", (1, 1), (10, 20, 30))

    monkeypatch.setattr(Image, "open", fake_open)

    rendered = image.to_pil_image()

    assert rendered is not None
    assert rendered.getpixel((0, 0)) == (10, 20, 30)
    assert opened_payloads == [b"encoded-jpx"]


class _DeviceNColorSpace:
    def __init__(self, components: int, fail: bool = False) -> None:
        self._components = components
        self._fail = fail

    def get_number_of_components(self) -> int:
        return self._components

    def get_name(self) -> str:
        return "DeviceN"

    def to_rgb(self, components: list[float]) -> tuple[float, float, float]:
        if self._fail:
            raise ValueError("bad tint")
        return (components[0] * 2.0, -1.0, 0.5)


def test_wave426_decode_devicen_to_rgb_clamps_and_caches_samples() -> None:
    color_space = _DeviceNColorSpace(1)

    rendered = _decode_devicen_to_rgb(color_space, bytes([200, 200]), 2, 1)

    assert rendered is not None
    assert list(rendered.getdata()) == [(255, 0, 128), (255, 0, 128)]


def test_wave426_decode_devicen_to_rgb_handles_short_zero_and_failing_transforms() -> None:
    assert _decode_devicen_to_rgb(_DeviceNColorSpace(2), b"\x00", 1, 1) is None

    zero_component = _decode_devicen_to_rgb(_DeviceNColorSpace(0), b"\x44", 1, 1)
    assert zero_component is not None
    assert list(zero_component.getdata()) == [(68, 68, 68)]

    failing = _decode_devicen_to_rgb(
        _DeviceNColorSpace(2, fail=True),
        bytes([10, 30]),
        1,
        1,
    )
    assert failing is not None
    assert list(failing.getdata()) == [(20, 20, 20)]


def test_wave426_luminance_fallback_and_clamp_helpers() -> None:
    assert _luminance_fallback(b"\x10", 2, 1, 1) is None

    one_component = _luminance_fallback(bytes([10, 20]), 2, 1, 1)
    assert one_component is not None
    assert list(one_component.getdata()) == [(10, 10, 10), (20, 20, 20)]

    two_component = _luminance_fallback(bytes([10, 30, 80, 100]), 2, 1, 2)
    assert two_component is not None
    assert list(two_component.getdata()) == [(20, 20, 20), (90, 90, 90)]

    assert _clamp01(-0.5) == 0.0
    assert _clamp01(0.25) == 0.25
    assert _clamp01(2.0) == 1.0
