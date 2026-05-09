from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB


class _FakeColorSpace:
    def __init__(self, name: str, components: int = 0) -> None:
        self._name = name
        self._components = components

    def get_name(self) -> str:
        return self._name

    def get_number_of_components(self) -> int:
        return self._components


class _DelegateColorSpace(_FakeColorSpace):
    def __init__(self, name: str, result: tuple[float, float, float] | None) -> None:
        super().__init__(name)
        self.result = result
        self.seen_components: list[float] | None = None

    def to_rgb(self, components: list[float]) -> tuple[float, float, float] | None:
        self.seen_components = list(components)
        return self.result


class _IndexedColorSpace(_FakeColorSpace):
    def __init__(
        self,
        *,
        lookup: bytes | None,
        hival: int | object | None = None,
        base: object | None = None,
    ) -> None:
        super().__init__("Indexed", 1)
        self._lookup = lookup
        self._hival = hival
        self._base = base

    def get_hival(self) -> int:
        if isinstance(self._hival, Exception):
            raise self._hival
        return 255 if self._hival is None else int(self._hival)

    def get_lookup_data(self) -> bytes | None:
        return self._lookup

    def get_base_color_space(self) -> object | None:
        if isinstance(self._base, Exception):
            raise self._base
        return self._base


def test_wave420_cos_name_constructor_rejects_third_argument_and_pattern_keyword() -> None:
    pattern = COSName.get_pdf_name("P1")

    with pytest.raises(TypeError, match="no third positional"):
        PDColor(pattern, PDDeviceRGB.INSTANCE, COSName.get_pdf_name("P2"))

    with pytest.raises(TypeError, match="pattern="):
        PDColor(pattern, PDDeviceRGB.INSTANCE, pattern=pattern)


def test_wave420_cos_array_constructor_rejects_extra_pattern_arguments() -> None:
    array = COSArray()
    array.add(COSFloat(0.25))

    with pytest.raises(TypeError, match="no third positional"):
        PDColor(array, PDDeviceGray.INSTANCE, COSName.get_pdf_name("P1"))

    with pytest.raises(TypeError, match="pattern="):
        PDColor(array, PDDeviceGray.INSTANCE, pattern=COSName.get_pdf_name("P1"))


def test_wave420_component_constructor_rejects_invalid_color_space_and_pattern_shapes() -> None:
    with pytest.raises(TypeError, match="color_space argument is required"):
        PDColor([0.25], COSName.get_pdf_name("P1"))

    with pytest.raises(TypeError, match="third argument must be a COSName"):
        PDColor([0.25], PDDeviceGray.INSTANCE, PDDeviceRGB.INSTANCE)

    with pytest.raises(TypeError, match="passed both positionally"):
        PDColor(
            [0.25],
            PDDeviceGray.INSTANCE,
            COSName.get_pdf_name("P1"),
            pattern=COSName.get_pdf_name("P2"),
        )


def test_wave420_components_are_defensively_copied_by_constructor_and_setter() -> None:
    components = [0.1, 0.2, 0.3]
    color = PDColor(components, PDDeviceRGB.INSTANCE)
    components[0] = 0.9

    assert color.get_components() == [0.1, 0.2, 0.3]

    new_components = [0.4, 0.5, 0.6]
    color.set_components(new_components)
    new_components[0] = 0.0

    assert color.get_components() == [0.4, 0.5, 0.6]


def test_wave420_is_pattern_true_for_pattern_named_color_space_without_pattern_name() -> None:
    color = PDColor([], _FakeColorSpace("Pattern"))  # type: ignore[arg-type]

    assert color.is_pattern() is True


def test_wave420_indexed_without_lookup_accessor_returns_black() -> None:
    color = PDColor([3], _FakeColorSpace("Indexed", 1))  # type: ignore[arg-type]

    assert color.to_rgb() == (0.0, 0.0, 0.0)


def test_wave420_indexed_empty_lookup_returns_black() -> None:
    color = PDColor([3], _IndexedColorSpace(lookup=b""))  # type: ignore[arg-type]

    assert color.to_rgb() == (0.0, 0.0, 0.0)


def test_wave420_indexed_clamps_negative_index_and_uses_rgb_fallback() -> None:
    color = PDColor([-5], _IndexedColorSpace(lookup=bytes([10, 20, 30])))  # type: ignore[arg-type]

    assert color.to_rgb() == pytest.approx((10 / 255.0, 20 / 255.0, 30 / 255.0))


def test_wave420_indexed_clamps_to_hival_and_last_complete_palette_entry() -> None:
    color = PDColor(
        [99],
        _IndexedColorSpace(lookup=bytes([0, 0, 0, 25, 50, 75]), hival=10),
    )  # type: ignore[arg-type]

    assert color.to_rgb() == pytest.approx((25 / 255.0, 50 / 255.0, 75 / 255.0))


def test_wave420_indexed_ignores_bad_hival_and_bad_base_accessor() -> None:
    color = PDColor(
        [1],
        _IndexedColorSpace(
            lookup=bytes([0, 0, 0, 100, 125, 150]),
            hival=ValueError("bad hival"),
            base=TypeError("bad base"),
        ),
    )  # type: ignore[arg-type]

    assert color.to_rgb() == pytest.approx((100 / 255.0, 125 / 255.0, 150 / 255.0))


def test_wave420_indexed_delegates_to_base_color_space() -> None:
    color = PDColor(
        [0],
        _IndexedColorSpace(lookup=bytes([0, 128, 255, 30]), base=PDDeviceCMYK.INSTANCE),
    )  # type: ignore[arg-type]

    assert color.to_rgb() == pytest.approx(
        (225 / 255.0, (127 / 255.0) * (225 / 255.0), 0.0)
    )


def test_wave420_delegate_color_space_result_is_clamped() -> None:
    cs = _DelegateColorSpace("Separation", (-1.0, 0.5, 2.0))
    color = PDColor([0.25], cs)  # type: ignore[arg-type]

    assert color.to_rgb() == (0.0, 0.5, 1.0)
    assert cs.seen_components == [0.25]


def test_wave420_delegate_color_space_without_to_rgb_raises_not_implemented() -> None:
    color = PDColor([0.25], _FakeColorSpace("DeviceN"))  # type: ignore[arg-type]

    with pytest.raises(NotImplementedError, match="DeviceN"):
        color.to_rgb()


def test_wave420_delegate_color_space_none_result_raises_for_pattern() -> None:
    color = PDColor([], _DelegateColorSpace("Pattern", None))  # type: ignore[arg-type]

    with pytest.raises(NotImplementedError, match="underlying color space"):
        color.to_rgb()
