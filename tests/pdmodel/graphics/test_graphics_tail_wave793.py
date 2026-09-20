from __future__ import annotations

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.graphics.color.pd_cal_gray import PDCalGray
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)


def _default_indexed() -> PDIndexed:
    """Build ``[/Indexed /DeviceRGB 255 null]`` — the array that PDFBox
    3.x's no-arg ``PDIndexed()`` constructed. PDFBox 4.0 made that
    constructor private (adopted in pypdfbox 2.0.0), so the array is
    spelled out here instead."""
    from pypdfbox.cos import COSArray, COSInteger, COSName, COSNull
    from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
    from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed

    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(255))
    arr.add(COSNull.NULL)
    return PDIndexed(arr)


class _ArraylessColorSpace(PDColorSpace):
    def get_name(self) -> str:
        return "Arrayless"

    def get_number_of_components(self) -> int:
        return 1

    def get_initial_color(self) -> object:
        return object()


class _ShortWhitePointCalGray(PDCalGray):
    def get_white_point(self) -> list[float]:
        return [1.0]


class _NoCosObject:
    def get_cos_object(self) -> None:
        return None


def test_cal_gray_short_white_point_is_not_unit_white_point() -> None:
    assert _ShortWhitePointCalGray().is_white_point() is False


def test_color_space_string_uses_subclass_name() -> None:
    assert str(_ArraylessColorSpace()) == "Arrayless"


def test_indexed_and_separation_reject_arrayless_color_spaces() -> None:
    separation = PDSeparation()

    # PDFBox 4.0 removed ``setBaseColorSpace`` (adopted in pypdfbox
    # 2.0.0), so the "base CS with no COS form" rejection is reached
    # through the ``create`` factory instead.
    assert not hasattr(PDIndexed, "set_base_color_space")
    with pytest.raises(ValueError, match="base color space has no COS form"):
        PDIndexed.create(_ArraylessColorSpace(), 0, b"\x00")
    with pytest.raises(TypeError, match="alternate_color_space"):
        separation.set_alternate_color_space(_ArraylessColorSpace())
    with pytest.raises(TypeError, match="COS form"):
        separation.set_tint_transform(_NoCosObject())


def test_form_content_stream_aliases_and_optional_content_round_trip() -> None:
    form = PDFormXObject(COSStream())
    stream = form.get_content_stream()
    with stream.create_output_stream() as out:
        out.write(b"q 2 w Q")

    assert stream is form.get_stream()
    with form.get_contents() as contents:
        assert contents.read() == b"q 2 w Q"

    random_access = form.get_contents_for_stream_parsing()
    try:
        assert random_access.read() == ord("q")
    finally:
        random_access.close()

    group = PDOptionalContentGroup("Tail Layer")
    form.set_optional_content(group)
    assert form.get_optional_content() is not None
    assert form.has_optional_content() is True

    form.set_optional_content(None)
    assert form.get_optional_content() is None
    assert form.has_optional_content() is False
