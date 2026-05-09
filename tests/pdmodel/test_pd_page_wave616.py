from __future__ import annotations

import math

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSObject,
    COSStream,
)
from pypdfbox.pdmodel import PDPage, PDRectangle, PDResources
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationText
from pypdfbox.pdmodel.interactive.measurement import PDViewportDictionary
from pypdfbox.pdmodel.interactive.pagenavigation import PDTransition


def test_wave616_constructor_inheritance_parent_alias_and_resources() -> None:
    with pytest.raises(TypeError, match="PDPage requires"):
        PDPage(object())  # type: ignore[arg-type]

    parent = COSDictionary()
    resources_dict = COSDictionary()
    parent.set_item(COSName.RESOURCES, resources_dict)  # type: ignore[attr-defined]
    parent.set_item(COSName.get_pdf_name("Rotate"), COSInteger.get(-90))
    child = COSDictionary()
    child.set_item(COSName.get_pdf_name("P"), parent)
    page = PDPage(child)
    cache = object()
    page.set_resource_cache(cache)

    assert page.get_cos_parent() is parent
    assert page.get_inherited_cos_object("Rotate").int_value() == -90
    assert page.get_inheritable_attribute(COSName.RESOURCES) is resources_dict  # type: ignore[attr-defined]
    resources = page.get_resources()
    assert resources.get_cos_object() is resources_dict
    assert resources._resource_cache is cache  # noqa: SLF001

    page.set_resources(PDResources())
    assert isinstance(page.get_cos_object().get_dictionary_object("Resources"), COSDictionary)
    page.set_resources(None)
    assert page.get_cos_object().get_dictionary_object("Resources") is None


def test_wave616_bbox_content_random_access_and_matrix_helpers() -> None:
    page = PDPage(PDRectangle(0, 0, 100, 100))
    stream_one = COSStream()
    stream_one.set_raw_data(b"q")
    stream_two = COSStream()
    stream_two.set_raw_data(b"Q")
    page.set_contents(COSArray([stream_one, stream_two]))
    page.set_crop_box(PDRectangle(-10, -10, 80, 90))

    assert page.get_b_box().lower_left_x == 0
    assert page.get_bbox().upper_right_y == 90
    assert page.get_content_streams()[0].get_cos_object() is stream_one
    random_access = page.get_contents_for_random_access()
    random_access_bytes = bytearray(random_access.length())
    assert random_access.read_into(random_access_bytes) == 3
    assert bytes(random_access_bytes) == b"q\nQ"
    parsing_access = page.get_contents_for_stream_parsing()
    parsing_access_bytes = bytearray(parsing_access.length())
    assert parsing_access.read_into(parsing_access_bytes) == 3
    assert bytes(parsing_access_bytes) == b"q\nQ"
    assert page.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_wave616_rotation_normalization_and_radians() -> None:
    page = PDPage()
    assert page.is_rotated() is False

    page.set_rotation(450)
    assert page.get_rotation() == 90
    assert page.is_rotated() is True
    assert math.isclose(page.get_rotation_in_radians(), math.pi / 2)

    page.get_cos_object().set_item("Rotate", COSFloat(-180.9))
    assert page.get_rotation() == 180
    page.get_cos_object().set_item("Rotate", COSInteger.get(45))
    assert page.get_rotation() == 0
    page.get_cos_object().set_name("Rotate", "North")
    assert page.get_rotation() == 0


def test_wave616_annotations_filter_and_thumb_transition_actions() -> None:
    page = PDPage()
    text = PDAnnotationText()
    page.set_annotations([text])

    assert page.get_annotations(lambda annotation: False) == []
    [resolved_text] = page.get_annotations(
        lambda annotation: annotation.get_subtype() == "Text"
    )
    assert resolved_text.get_cos_object() is text.get_cos_object()

    thumb = COSStream()
    thumb.set_raw_data(b"img")
    page.get_cos_object().set_item("Thumb", thumb)
    assert page.get_thumb().get_cos_object() is thumb
    page.set_thumb(None)
    assert page.get_thumb() is None

    transition = PDTransition()
    page.set_transition(transition, duration=2.5)
    assert page.get_transition().get_cos_object() is transition.get_cos_object()
    assert page.get_transition_effect().get_cos_object() is transition.get_cos_object()
    assert page.get_duration() == 2.5
    page.set_transition_effect(transition)
    page.set_transition(None, duration=1.0)
    assert page.get_transition() is None
    assert page.get_duration() == 1.0

    assert page.has_actions() is False
    actions = page.get_actions()
    assert page.has_actions() is True
    page.set_actions(actions)
    page.set_actions(None)
    assert page.has_actions() is False


def test_wave616_struct_parent_metadata_group_viewport_and_presence_helpers() -> None:
    page = PDPage()
    page.set_struct_parents(7)
    assert page.get_struct_parents() == 7

    metadata = COSStream()
    metadata.set_raw_data(b"xmp")
    page.set_metadata(metadata)
    group = COSDictionary()
    page.set_group(group)

    viewport_dict = COSDictionary()
    viewport = PDViewportDictionary(viewport_dict)
    wrapped_viewport = type(
        "WrappedViewport",
        (),
        {"get_cos_object": lambda self: COSDictionary()},
    )()
    page.set_viewports([viewport, COSDictionary(), wrapped_viewport])

    assert page.has_metadata() is True
    assert page.has_group() is True
    assert page.has_viewports() is True
    assert page.get_metadata().get_cos_object() is metadata
    assert page.get_group() is group
    assert len(page.get_viewports()) == 3

    with pytest.raises(TypeError, match="set_viewports entries"):
        page.set_viewports([object()])  # type: ignore[list-item]

    page.set_viewports(None)
    page.set_duration(None)
    page.set_tab_order(None)

    assert page.get_viewports() is None
    assert page.has_viewports() is False
    assert page.has_duration() is False
    assert page.has_tab_order() is False


def test_wave616_remove_page_resource_from_cache_removes_only_indirect_entries() -> None:
    page = PDPage()
    cache_calls: list[tuple[str, COSObject]] = []

    class Cache:
        def remove_color_space(self, obj: COSObject) -> None:
            cache_calls.append(("ColorSpace", obj))

        def remove_font(self, obj: COSObject) -> None:
            cache_calls.append(("Font", obj))

    page.remove_page_resource_from_cache()
    page.set_resource_cache(Cache())
    page.remove_page_resource_from_cache()

    resources = COSDictionary()
    color_spaces = COSDictionary()
    color_ref = COSObject(1, resolved=COSDictionary())
    color_spaces.set_item(COSName.get_pdf_name("CS1"), color_ref)
    color_spaces.set_item(COSName.get_pdf_name("Direct"), COSDictionary())
    fonts = COSDictionary()
    font_ref = COSObject(2, resolved=COSDictionary())
    fonts.set_item(COSName.get_pdf_name("F1"), font_ref)
    xobjects = COSDictionary()
    xobjects.set_item(COSName.get_pdf_name("X1"), COSObject(3, resolved=COSDictionary()))
    resources.set_item(COSName.get_pdf_name("ColorSpace"), color_spaces)
    resources.set_item(COSName.get_pdf_name("Font"), fonts)
    resources.set_item(COSName.get_pdf_name("XObject"), xobjects)
    page.set_resources(resources)

    page.remove_page_resource_from_cache()

    assert cache_calls == [("ColorSpace", color_ref), ("Font", font_ref)]
