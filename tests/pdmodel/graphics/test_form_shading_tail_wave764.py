from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType2
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.form.pd_transparency_group_attributes import (
    PDTransparencyGroupAttributes,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.shading import PDShading, PDShadingType2, PDShadingType3


class _ArraylessColorSpace(PDColorSpace):
    def __init__(self) -> None:
        super().__init__()

    def get_name(self) -> str:
        return "DeviceRGB"

    def get_number_of_components(self) -> int:
        return 3

    def get_initial_color(self) -> object:
        return object()


def _function_type2_dict() -> COSDictionary:
    function = COSDictionary()
    function.set_int("FunctionType", 2)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    function.set_item("Domain", domain)
    c0 = COSArray()
    c0.add(COSFloat(0.0))
    function.set_item("C0", c0)
    c1 = COSArray()
    c1.add(COSFloat(1.0))
    function.set_item("C1", c1)
    function.set_int("N", 1)
    return function


def test_form_content_stream_and_decoded_contents_tail() -> None:
    form = PDFormXObject(COSStream())
    stream = form.get_content_stream()
    with stream.create_output_stream() as out:
        out.write(b"q 1 0 0 1 0 0 cm Q")

    assert stream is form.get_stream()
    with form.get_contents() as contents:
        assert contents.read() == b"q 1 0 0 1 0 0 cm Q"


def test_form_optional_content_aliases_delegate_to_oc_accessors() -> None:
    form = PDFormXObject(COSStream())
    group = PDOptionalContentGroup("Layer")

    form.set_optional_content(group)

    assert form.get_optional_content() is not None
    assert form.get_optional_content().get_cos_object() is group.get_cos_object()


def test_form_optional_content_alias_clears_entry() -> None:
    form = PDFormXObject(COSStream())
    form.set_optional_content(PDOptionalContentGroup("Layer"))

    form.set_optional_content(None)

    assert form.get_optional_content() is None
    assert form.has_optional_content() is False


def test_transparency_group_arrayless_color_space_stores_name() -> None:
    attrs = PDTransparencyGroupAttributes()

    attrs.set_color_space(_ArraylessColorSpace())

    value = attrs.get_cos_object().get_dictionary_object(COSName.get_pdf_name("CS"))
    assert isinstance(value, COSName)
    assert value.name == "DeviceRGB"


def test_shading_arrayless_color_space_clears_existing_entry() -> None:
    shading = PDShadingType2()
    shading.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    assert shading.has_color_space() is True

    shading.set_color_space_object(_ArraylessColorSpace())

    assert shading.has_color_space() is False


def test_base_shading_get_function_wraps_single_function_dictionary() -> None:
    shading = PDShading(COSDictionary())
    raw = _function_type2_dict()
    shading.set_function(raw)

    function = shading.get_function()

    assert isinstance(function, PDFunctionType2)
    assert function.get_cos_object() is raw


def test_type2_set_function_iterable_accepts_raw_cos_entries() -> None:
    shading = PDShadingType2()
    raw = _function_type2_dict()

    shading.set_function([raw])

    stored = shading.get_cos_object().get_dictionary_object("Function")
    assert isinstance(stored, COSArray)
    assert stored.get_object(0) is raw


def test_type2_set_function_iterable_rejects_bad_entries() -> None:
    shading = PDShadingType2()

    with pytest.raises(TypeError, match="iterable entries"):
        shading.set_function([object()])


def test_type3_set_function_iterable_accepts_raw_cos_entries() -> None:
    shading = PDShadingType3()
    raw = _function_type2_dict()

    shading.set_function([raw])

    stored = shading.get_cos_object().get_dictionary_object("Function")
    assert isinstance(stored, COSArray)
    assert stored.get_object(0) is raw

