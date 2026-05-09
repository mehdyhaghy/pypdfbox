from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_lab import PDLab


class _NoCountColorSpace:
    def get_name(self) -> str:
        return "NoCount"


class _NegativeCountColorSpace:
    def get_name(self) -> str:
        return "NegativeCount"

    def get_number_of_components(self) -> int:
        return -1


class _UnderlyingRaisesColorSpace:
    def get_name(self) -> str:
        return "Pattern"

    def get_underlying_color_space(self) -> object:
        raise TypeError("bad underlying")


class _BadUnderlyingCount:
    def get_number_of_components(self) -> int:
        raise ValueError("bad count")


class _BadUnderlyingCountColorSpace:
    def get_name(self) -> str:
        return "Pattern"

    def get_underlying_color_space(self) -> _BadUnderlyingCount:
        return _BadUnderlyingCount()


class _CalGrayWithoutToRgb:
    def get_name(self) -> str:
        return "CalGray"

    def get_number_of_components(self) -> int:
        return 1


class _CalRgbWithoutToRgb:
    def get_name(self) -> str:
        return "CalRGB"

    def get_number_of_components(self) -> int:
        return 3


class _IndexedWithoutBase:
    def __init__(self, lookup: bytes, base: object | None = None) -> None:
        self._lookup = lookup
        self._base = base

    def get_name(self) -> str:
        return "Indexed"

    def get_number_of_components(self) -> int:
        return 1

    def get_lookup_data(self) -> bytes:
        return self._lookup

    def get_base_color_space(self) -> object | None:
        return self._base


class _UnknownColorSpace:
    def get_name(self) -> str:
        return "Unknown"

    def get_number_of_components(self) -> int:
        return 1


def test_wave468_cos_array_constructor_rejects_cos_name_color_space() -> None:
    array = COSArray()
    array.add(COSFloat(0.25))

    with pytest.raises(TypeError, match="second argument must be a PDColorSpace"):
        PDColor(array, COSName.get_pdf_name("DeviceGray"))


def test_wave468_null_color_space_paths_return_raw_values() -> None:
    color = PDColor([0.25, 0.5], None)  # type: ignore[arg-type]

    assert color.get_components() == [0.25, 0.5]
    assert color.get_color_space_name() is None
    assert color.is_separation() is False
    assert color.is_device_n() is False


def test_wave468_get_components_tolerates_missing_and_negative_counts() -> None:
    no_count = PDColor([0.25, 0.5], _NoCountColorSpace())  # type: ignore[arg-type]
    negative_count = PDColor([0.25, 0.5], _NegativeCountColorSpace())  # type: ignore[arg-type]

    assert no_count.get_components() == [0.25, 0.5]
    assert negative_count.get_components() == [0.25, 0.5]


def test_wave468_pattern_arity_check_tolerates_bad_underlying_accessors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pattern_name = COSName.get_pdf_name("P1")

    with caplog.at_level(
        logging.WARNING,
        logger="pypdfbox.pdmodel.graphics.color.pd_color",
    ):
        PDColor([0.25], _UnderlyingRaisesColorSpace(), pattern_name)  # type: ignore[arg-type]
        PDColor([0.25], _BadUnderlyingCountColorSpace(), pattern_name)  # type: ignore[arg-type]

    assert caplog.records == []


def test_wave468_predicates_return_false_when_color_space_lacks_hooks() -> None:
    color = PDColor([0.25], _NoCountColorSpace())  # type: ignore[arg-type]

    assert color.is_separation() is False
    assert color.is_device_n() is False


def test_wave468_cal_gray_without_delegate_falls_back_to_gray() -> None:
    color = PDColor([1.25], _CalGrayWithoutToRgb())  # type: ignore[arg-type]

    assert color.to_rgb() == (1.0, 1.0, 1.0)


def test_wave468_cal_rgb_without_delegate_falls_back_to_rgb() -> None:
    color = PDColor([1.25, 0.5, -0.25], _CalRgbWithoutToRgb())  # type: ignore[arg-type]

    assert color.to_rgb() == (1.0, 0.5, 0.0)


def test_wave468_indexed_without_base_accepts_one_byte_lookup_as_gray() -> None:
    color = PDColor([0], _IndexedWithoutBase(bytes([128])))  # type: ignore[arg-type]

    assert color.to_rgb() == pytest.approx((128 / 255.0, 128 / 255.0, 128 / 255.0))


def test_wave468_indexed_without_base_returns_black_for_two_byte_lookup() -> None:
    color = PDColor([0], _IndexedWithoutBase(bytes([32, 64])))  # type: ignore[arg-type]

    assert color.to_rgb() == (0.0, 0.0, 0.0)


def test_wave468_indexed_with_base_pads_short_lookup_components() -> None:
    color = PDColor(
        [0],
        _IndexedWithoutBase(bytes([255, 128]), PDDeviceRGB.INSTANCE),
    )  # type: ignore[arg-type]

    assert color.to_rgb() == pytest.approx((1.0, 128 / 255.0, 0.0))


def test_wave468_unknown_color_space_raises_not_implemented() -> None:
    color = PDColor([0.25], _UnknownColorSpace())  # type: ignore[arg-type]

    with pytest.raises(NotImplementedError, match="Unknown"):
        color.to_rgb()


def test_wave468_lab_black_exercises_low_xyz_and_srgb_branches() -> None:
    rgb = PDColor([0.0, 0.0, 0.0], PDLab()).to_rgb()

    assert rgb == pytest.approx((0.0, 0.0, 0.0), abs=1e-6)


def test_wave468_raw_rgb_image_uses_native_rgb_components() -> None:
    image = PDColor([0.0, 0.5, 1.0], PDDeviceRGB.INSTANCE).to_raw_image(2, 3)

    assert image.mode == "RGB"
    assert image.size == (2, 3)
    assert image.getpixel((1, 2)) == (0, 128, 255)
