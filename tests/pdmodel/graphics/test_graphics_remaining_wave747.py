from __future__ import annotations

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSNull
from pypdfbox.pdmodel.graphics.color.pd_device_n import (
    PDDeviceN,
    PDDeviceNAttributes,
    PDDeviceNProcess,
)
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab
from pypdfbox.pdmodel.graphics.image import jpeg_factory
from pypdfbox.pdmodel.graphics.image.jpeg_factory import JPEGFactory


class _NoCosObject:
    def get_cos_object(self) -> None:
        return None


class _ProbeWithUnknownMode:
    format = "JPEG"
    mode = "I"
    size = (7, 9)

    def __enter__(self) -> _ProbeWithUnknownMode:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def getbands(self) -> tuple[str, str]:
        return ("I", "Q")


def _lab_array(params: object) -> COSArray:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Lab"))
    arr.add(params)
    return arr


def test_jpeg_factory_rejects_unsupported_component_count_and_falls_back_to_bands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert jpeg_factory._pil_mode_to_components("I") == 0
    with pytest.raises(ValueError, match="number of data elements"):
        jpeg_factory._color_space_for_components(2)

    monkeypatch.setattr(
        jpeg_factory.Image,
        "open",
        lambda _stream: _ProbeWithUnknownMode(),
    )

    assert jpeg_factory._retrieve_dimensions(b"fake jpeg header") == (7, 9, 2)


@pytest.mark.parametrize(
    ("mode", "color"),
    [
        ("P", 1),
        ("1", 1),
        ("I", 12),
    ],
)
def test_jpeg_factory_create_from_image_converts_palette_bitmap_and_other_modes(
    mode: str,
    color: int,
) -> None:
    image = Image.new(mode, (3, 2), color)

    xobject = JPEGFactory.create_from_image(None, image)

    assert xobject.get_width() == 3
    assert xobject.get_height() == 2
    assert xobject.get_bits_per_component() == 8


def test_device_n_rejects_objects_without_cos_form_and_skips_null_colorants() -> None:
    process = PDDeviceNProcess()
    attrs = PDDeviceNAttributes()
    device_n = PDDeviceN()

    with pytest.raises(TypeError, match="color space with a COS form"):
        process.set_color_space(_NoCosObject())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="color spaces with COS forms"):
        attrs.set_colorants({"Broken": _NoCosObject()})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="alternate_color_space"):
        device_n.set_alternate_color_space(_NoCosObject())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="object with a COS form"):
        device_n.set_tint_transform(_NoCosObject())

    colorants = COSDictionary()
    colorants.set_item("NullSpot", COSNull.NULL)
    colorants.set_item("RGB", COSName.get_pdf_name("DeviceRGB"))
    colorants.set_item("Gray", COSName.get_pdf_name("DeviceGray"))
    attrs_dict = COSDictionary()
    attrs_dict.set_item("Colorants", colorants)

    rendered = str(PDDeviceNAttributes(attrs_dict))

    assert list(PDDeviceNAttributes(attrs_dict).get_colorants()) == ["RGB", "Gray"]
    assert rendered == '{Colorants{"RGB": DeviceRGB "Gray": DeviceGray}}'


def test_lab_predicates_invalid_slot_and_short_ranges() -> None:
    lab = PDLab()
    assert lab.has_white_point() is False
    assert lab.has_black_point() is False

    lab.set_white_point([1.0, 1.0, 1.0])
    lab.set_black_point([0.2, 0.3, 0.4])
    assert lab.has_white_point() is True
    assert lab.has_black_point() is True

    lab.clear_black_point()
    assert lab.has_black_point() is False

    params = lab.get_cos_object().get_object(1)
    assert isinstance(params, COSDictionary)
    params.set_item(COSName.get_pdf_name("WhitePoint"), COSArray.of_cos_floats([1.0]))
    params.set_item(COSName.get_pdf_name("Range"), COSArray([COSFloat(-5.0)]))

    assert lab.is_white_point() is False
    assert lab.get_default_decode(8) == [
        0.0,
        100.0,
        -100.0,
        100.0,
        -100.0,
        100.0,
    ]

    with pytest.raises(TypeError, match="Lab array index 1"):
        PDLab(_lab_array(COSName.get_pdf_name("Bad"))).get_range()
