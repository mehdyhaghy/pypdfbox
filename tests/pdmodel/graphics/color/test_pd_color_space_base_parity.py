from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation

# ---------- get_name ----------


def test_device_rgb_get_name() -> None:
    assert PDDeviceRGB.INSTANCE.get_name() == "DeviceRGB"


def test_device_gray_get_name() -> None:
    assert PDDeviceGray.INSTANCE.get_name() == "DeviceGray"


def test_device_cmyk_get_name() -> None:
    assert PDDeviceCMYK.INSTANCE.get_name() == "DeviceCMYK"


# ---------- is_pattern ----------


def test_device_rgb_is_pattern_false() -> None:
    assert PDDeviceRGB.INSTANCE.is_pattern() is False


def test_pattern_is_pattern_true() -> None:
    assert PDPattern().is_pattern() is True


# ---------- is_indexed ----------


def test_device_rgb_is_indexed_false() -> None:
    assert PDDeviceRGB.INSTANCE.is_indexed() is False


def test_indexed_is_indexed_true() -> None:
    assert PDIndexed().is_indexed() is True


# ---------- is_separation ----------


def test_device_rgb_is_separation_false() -> None:
    assert PDDeviceRGB.INSTANCE.is_separation() is False


def test_separation_is_separation_true() -> None:
    assert PDSeparation().is_separation() is True


# ---------- is_device_n ----------


def test_device_rgb_is_device_n_false() -> None:
    assert PDDeviceRGB.INSTANCE.is_device_n() is False


def test_device_n_is_device_n_true() -> None:
    assert PDDeviceN().is_device_n() is True


# ---------- get_java_color_space ----------


def test_get_java_color_space_returns_none() -> None:
    # Java-AWT-specific upstream API; no Python equivalent.
    assert PDDeviceRGB.INSTANCE.get_java_color_space() is None
    assert PDDeviceGray.INSTANCE.get_java_color_space() is None
    assert PDIndexed().get_java_color_space() is None


# ---------- to_rgb_image / to_raw_image ----------


def test_to_rgb_image_returns_pillow_image() -> None:
    from PIL import Image

    raster = bytes([255, 0, 0, 0, 255, 0])  # 2 RGB pixels
    img = PDDeviceRGB.INSTANCE.to_rgb_image(raster, 2, 1)
    assert isinstance(img, Image.Image)
    assert img.mode == "RGB"
    assert img.size == (2, 1)


def test_to_raw_image_uses_pillow_native_mode_for_device_rgb() -> None:
    from PIL import Image

    raster = bytes([10, 20, 30])
    img = PDDeviceRGB.INSTANCE.to_raw_image(raster, 1, 1)
    assert isinstance(img, Image.Image)
    assert img.mode == "RGB"
    assert img.getpixel((0, 0)) == (10, 20, 30)


# ---------- get_array ----------


def test_device_rgb_get_array_is_none() -> None:
    # Name-only device color spaces have no backing array.
    assert PDDeviceRGB.INSTANCE.get_array() is None


def test_indexed_get_array_returns_cos_array() -> None:
    indexed = PDIndexed()
    arr = indexed.get_array()
    assert isinstance(arr, COSArray)
    # Same object as get_cos_object for array-form color spaces.
    assert arr is indexed.get_cos_object()


# ---------- to_rgb(value) on the device color spaces ----------


def test_device_rgb_to_rgb_is_identity() -> None:
    # Upstream PDDeviceRGB.toRGB(float[]) returns the input unchanged.
    value = [0.1, 0.5, 0.9]
    result = PDDeviceRGB.INSTANCE.to_rgb(value)
    assert result == value


def test_device_rgb_to_rgb_returns_same_object() -> None:
    # Upstream returns the array argument directly — preserve that.
    value = [0.0, 0.0, 0.0]
    assert PDDeviceRGB.INSTANCE.to_rgb(value) is value


def test_device_gray_to_rgb_replicates_component() -> None:
    # Upstream PDDeviceGray.toRGB(float[]) -> {v[0], v[0], v[0]}.
    assert PDDeviceGray.INSTANCE.to_rgb([0.0]) == [0.0, 0.0, 0.0]
    assert PDDeviceGray.INSTANCE.to_rgb([0.42]) == [0.42, 0.42, 0.42]
    assert PDDeviceGray.INSTANCE.to_rgb([1.0]) == [1.0, 1.0, 1.0]


def test_device_cmyk_to_rgb_white_is_white() -> None:
    # CMYK (0, 0, 0, 0) -> white in the simple subtractive model.
    assert PDDeviceCMYK.INSTANCE.to_rgb([0.0, 0.0, 0.0, 0.0]) == [1.0, 1.0, 1.0]


def test_device_cmyk_to_rgb_black_is_black() -> None:
    # K=1 forces black regardless of the other components.
    assert PDDeviceCMYK.INSTANCE.to_rgb([0.0, 0.0, 0.0, 1.0]) == [0.0, 0.0, 0.0]
    assert PDDeviceCMYK.INSTANCE.to_rgb([0.5, 0.7, 0.2, 1.0]) == [0.0, 0.0, 0.0]


def test_device_cmyk_to_rgb_pure_cyan() -> None:
    # C=1 => no red; M=0,Y=0,K=0 => full green and blue.
    assert PDDeviceCMYK.INSTANCE.to_rgb([1.0, 0.0, 0.0, 0.0]) == [0.0, 1.0, 1.0]


# ---------- COSDictionary with /ColorSpace (PDFBOX-4833) ----------


def test_create_unwraps_dictionary_with_colorspace_entry() -> None:
    # A dict that wraps /ColorSpace -> /DeviceRGB should resolve to the
    # device singleton, mirroring upstream PDFBOX-4833 handling.
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace

    wrapper = COSDictionary()
    wrapper.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    assert PDColorSpace.create(wrapper) is PDDeviceRGB.INSTANCE


def test_create_dictionary_self_reference_raises() -> None:
    # PDFBOX-5315: a /ColorSpace entry pointing at its own dictionary
    # would loop forever — upstream throws IOException, pypdfbox raises
    # OSError per the test-porting guide.
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace

    wrapper = COSDictionary()
    wrapper.set_item(COSName.get_pdf_name("ColorSpace"), wrapper)
    with pytest.raises(OSError, match="Recursion in colorspace"):
        PDColorSpace.create(wrapper)


def test_create_dictionary_color_space_cycle_raises() -> None:
    # PDFBOX-5315 also applies when wrapper dictionaries recurse through
    # each other instead of pointing directly at themselves.
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace

    first = COSDictionary()
    second = COSDictionary()
    first.set_item(COSName.get_pdf_name("ColorSpace"), second)
    second.set_item(COSName.get_pdf_name("ColorSpace"), first)

    with pytest.raises(OSError, match="Recursion in colorspace"):
        PDColorSpace.create(first)


# ---------- was_default flag plumbing ----------


def test_create_accepts_was_default_flag() -> None:
    # The third positional argument mirrors upstream's internal-use
    # `create(COSBase, PDResources, boolean)` overload. With no resources
    # supplied it should be a structural no-op for device names.
    from pypdfbox.cos import COSName
    from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace

    assert (
        PDColorSpace.create(
            COSName.get_pdf_name("DeviceRGB"), None, True
        )
        is PDDeviceRGB.INSTANCE
    )
