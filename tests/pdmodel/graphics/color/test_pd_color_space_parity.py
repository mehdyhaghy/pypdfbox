from __future__ import annotations

from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB

_BASE_DECODE_STUB_CLASS: type[PDColorSpace] | None = None


# ---------- DeviceGray ----------


def test_device_gray_get_initial_color() -> None:
    cs = PDDeviceGray.INSTANCE
    color = cs.get_initial_color()
    assert isinstance(color, PDColor)
    assert color.get_components() == [0.0]
    assert color.get_color_space() is cs


def test_device_gray_get_default_decode() -> None:
    assert PDDeviceGray.INSTANCE.get_default_decode(8) == [0.0, 1.0]


def test_device_gray_get_default_decode_other_bpc() -> None:
    # Default decode does not depend on bpc for DeviceGray.
    assert PDDeviceGray.INSTANCE.get_default_decode(1) == [0.0, 1.0]
    assert PDDeviceGray.INSTANCE.get_default_decode(16) == [0.0, 1.0]


# ---------- DeviceRGB ----------


def test_device_rgb_get_initial_color() -> None:
    cs = PDDeviceRGB.INSTANCE
    color = cs.get_initial_color()
    assert isinstance(color, PDColor)
    assert color.get_components() == [0.0, 0.0, 0.0]
    assert color.get_color_space() is cs


def test_device_rgb_get_default_decode() -> None:
    assert PDDeviceRGB.INSTANCE.get_default_decode(8) == [
        0.0,
        1.0,
        0.0,
        1.0,
        0.0,
        1.0,
    ]


# ---------- DeviceCMYK ----------


def test_device_cmyk_get_initial_color() -> None:
    cs = PDDeviceCMYK.INSTANCE
    color = cs.get_initial_color()
    assert isinstance(color, PDColor)
    assert color.get_components() == [0.0, 0.0, 0.0, 1.0]
    assert color.get_color_space() is cs


def test_device_cmyk_get_default_decode() -> None:
    assert PDDeviceCMYK.INSTANCE.get_default_decode(8) == [0.0, 1.0] * 4


# ---------- base abstract behaviour ----------


def test_base_get_default_decode_returns_zero_one_per_component() -> None:
    global _BASE_DECODE_STUB_CLASS

    # Default behaviour matches PDF spec's general rule: ``[0, 1]``
    # repeated per component. Concrete subclasses override for
    # CMYK/Indexed/Lab where the spec declares a different default.
    class _Stub(PDColorSpace):
        def get_name(self) -> str:
            return "Stub"

        def get_number_of_components(self) -> int:
            return 2

        def get_initial_color(self) -> PDColor:
            return PDColor([0.0, 0.0], self)

    _BASE_DECODE_STUB_CLASS = _Stub
    stub = _Stub()
    assert stub.get_default_decode(8) == [0.0, 1.0, 0.0, 1.0]


# ---------- Indexed / Lab default decode (specialised) ----------


def test_indexed_default_decode_is_zero_to_two_pow_bits_minus_one() -> None:
    from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed

    indexed = PDIndexed()
    assert indexed.get_default_decode(8) == [0.0, 255.0]
    assert indexed.get_default_decode(4) == [0.0, 15.0]
    assert indexed.get_default_decode(1) == [0.0, 1.0]


def test_lab_default_decode_uses_l_zero_to_hundred_and_range() -> None:
    from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab

    lab = PDLab()
    decoded = lab.get_default_decode(8)
    # L spans [0, 100]; a/b come from /Range default [-100, 100, -100, 100].
    assert decoded == [0.0, 100.0, -100.0, 100.0, -100.0, 100.0]


# ---------- to_rgb_image / to_raw_image (Pillow-backed) ----------


def test_pd_color_space_to_rgb_image_converts_lab_raster() -> None:
    from PIL import Image

    from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab

    # 1×1 raster encoded as raw bytes; values land in any L*a*b region
    # and the converter just has to produce a usable RGB image.
    lab = PDLab()
    raster = bytes([255, 128, 128])
    img = lab.to_rgb_image(raster, 1, 1)
    assert isinstance(img, Image.Image)
    assert img.mode == "RGB"
    assert img.size == (1, 1)


def test_pd_color_space_to_raw_image_for_device_gray_uses_l_mode() -> None:
    raster = bytes([0, 128, 255])
    img = PDDeviceGray.INSTANCE.to_raw_image(raster, 3, 1)
    assert img.mode == "L"
    assert img.size == (3, 1)
    assert img.tobytes() == raster


def test_pd_color_space_to_raw_image_for_indexed_falls_through_to_rgb() -> None:
    from pypdfbox.cos import COSArray, COSInteger, COSString
    from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed

    arr = COSArray()
    arr.add(__import__("pypdfbox.cos", fromlist=["COSName"]).COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(1))
    arr.add(COSString(bytes([255, 0, 0, 0, 255, 0])))
    indexed = PDIndexed(arr)
    img = indexed.to_raw_image(bytes([0, 1]), 2, 1)
    # Indexed has no Pillow native; falls through to to_rgb_image.
    assert img.mode == "RGB"
    assert img.getpixel((0, 0)) == (255, 0, 0)
    assert img.getpixel((1, 0)) == (0, 255, 0)
