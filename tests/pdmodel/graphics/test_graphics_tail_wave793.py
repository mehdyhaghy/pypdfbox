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
    indexed = PDIndexed()
    separation = PDSeparation()

    with pytest.raises(TypeError, match="base_color_space"):
        indexed.set_base_color_space(_ArraylessColorSpace())
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
