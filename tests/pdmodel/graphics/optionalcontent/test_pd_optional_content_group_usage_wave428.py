from __future__ import annotations

from collections.abc import Callable

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSString
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group_usage import (
    PDOptionalContentGroupUsage,
)

_CREATOR_INFO = COSName.get_pdf_name("CreatorInfo")
_CREATOR = COSName.get_pdf_name("Creator")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_LANGUAGE = COSName.get_pdf_name("Language")
_LANG = COSName.get_pdf_name("Lang")
_PREFERRED = COSName.get_pdf_name("Preferred")
_EXPORT = COSName.get_pdf_name("Export")
_EXPORT_STATE = COSName.get_pdf_name("ExportState")
_ZOOM = COSName.get_pdf_name("Zoom")
_MIN = COSName.get_pdf_name("min")
_MAX = COSName.get_pdf_name("max")
_PRINT = COSName.get_pdf_name("Print")
_PRINT_STATE = COSName.get_pdf_name("PrintState")
_VIEW = COSName.get_pdf_name("View")
_VIEW_STATE = COSName.get_pdf_name("ViewState")
_USER = COSName.get_pdf_name("User")
_TYPE = COSName.get_pdf_name("Type")
_NAME = COSName.get_pdf_name("Name")
_PAGE_ELEMENT = COSName.get_pdf_name("PageElement")


@pytest.mark.parametrize(
    ("key", "has_name", "get_name", "create_name", "clear_name"),
    [
        (
            _CREATOR_INFO,
            "has_creator_info",
            "get_creator_info",
            "get_or_create_creator_info",
            "clear_creator_info",
        ),
        (_LANGUAGE, "has_language", "get_language", "get_or_create_language", "clear_language"),
        (_EXPORT, "has_export", "get_export", "get_or_create_export", "clear_export"),
        (_ZOOM, "has_zoom", "get_zoom", "get_or_create_zoom", "clear_zoom"),
        (_PRINT, "has_print", "get_print", "get_or_create_print", "clear_print"),
        (_VIEW, "has_view", "get_view", "get_or_create_view", "clear_view"),
        (_USER, "has_user", "get_user", "get_or_create_user", "clear_user"),
        (
            _PAGE_ELEMENT,
            "has_page_element",
            "get_page_element",
            "get_or_create_page_element",
            "clear_page_element",
        ),
    ],
)
def test_has_create_and_clear_subdictionaries(
    key: COSName,
    has_name: str,
    get_name: str,
    create_name: str,
    clear_name: str,
) -> None:
    usage = PDOptionalContentGroupUsage()
    has_sub = getattr(usage, has_name)
    get_sub = getattr(usage, get_name)
    create_sub = getattr(usage, create_name)
    clear_sub = getattr(usage, clear_name)

    assert has_sub() is False
    assert get_sub() is None

    created = create_sub()
    assert isinstance(created.get_cos_object(), COSDictionary)
    assert usage.get_cos_object().get_dictionary_object(key) is created.get_cos_object()
    assert has_sub() is True

    clear_sub()
    assert has_sub() is False
    assert get_sub() is None


@pytest.mark.parametrize(
    ("key", "get_name", "has_name"),
    [
        (_CREATOR_INFO, "get_creator_info", "has_creator_info"),
        (_LANGUAGE, "get_language", "has_language"),
        (_EXPORT, "get_export", "has_export"),
        (_ZOOM, "get_zoom", "has_zoom"),
        (_PRINT, "get_print", "has_print"),
        (_VIEW, "get_view", "has_view"),
        (_USER, "get_user", "has_user"),
        (_PAGE_ELEMENT, "get_page_element", "has_page_element"),
    ],
)
def test_non_dictionary_subentries_are_ignored(
    key: COSName, get_name: str, has_name: str
) -> None:
    raw = COSDictionary()
    raw.set_item(key, COSString("not a dictionary"))
    usage = PDOptionalContentGroupUsage(raw)

    assert getattr(usage, get_name)() is None
    assert getattr(usage, has_name)() is False


def test_creator_language_user_and_page_element_none_setters_remove_keys() -> None:
    usage = PDOptionalContentGroupUsage()

    creator = usage.get_or_create_creator_info()
    creator.creator = "Acme"
    creator.subtype = "Artwork"
    creator.creator = None
    creator.subtype = None
    assert creator.get_cos_object().get_dictionary_object(_CREATOR) is None
    assert creator.get_cos_object().get_dictionary_object(_SUBTYPE) is None

    language = usage.get_or_create_language()
    language.lang = "en-US"
    language.preferred = "ON"
    language.lang = None
    language.preferred = None
    assert language.get_cos_object().get_dictionary_object(_LANG) is None
    assert language.get_cos_object().get_dictionary_object(_PREFERRED) is None

    user = usage.get_or_create_user()
    user.type = "Org"
    user.name = "Engineering"
    user.type = None
    user.name = None
    assert user.get_cos_object().get_dictionary_object(_TYPE) is None
    assert user.get_cos_object().get_dictionary_object(_NAME) is None

    page_element = usage.get_or_create_page_element()
    page_element.subtype = "L"
    page_element.subtype = None
    assert page_element.get_cos_object().get_dictionary_object(_SUBTYPE) is None


@pytest.mark.parametrize(
    ("create", "key", "attribute", "valid_value"),
    [
        (PDOptionalContentGroupUsage.get_or_create_export, _EXPORT_STATE, "export_state", "off"),
        (PDOptionalContentGroupUsage.get_or_create_print, _PRINT_STATE, "print_state", "on"),
        (PDOptionalContentGroupUsage.get_or_create_view, _VIEW_STATE, "view_state", "off"),
    ],
)
def test_state_setters_normalize_and_remove_none(
    create: Callable[[PDOptionalContentGroupUsage], object],
    key: COSName,
    attribute: str,
    valid_value: str,
) -> None:
    usage = PDOptionalContentGroupUsage()
    state_wrapper = create(usage)

    setattr(state_wrapper, attribute, valid_value)
    assert getattr(state_wrapper, attribute) == valid_value.upper()

    setattr(state_wrapper, attribute, None)
    assert state_wrapper.get_cos_object().get_dictionary_object(key) is None


def test_zoom_numeric_values_remove_and_ignore_non_numbers() -> None:
    zoom_dict = COSDictionary()
    zoom_dict.set_item(_MIN, COSString("small"))
    zoom_dict.set_item(_MAX, COSName.get_pdf_name("large"))
    raw = COSDictionary()
    raw.set_item(_ZOOM, zoom_dict)
    zoom = PDOptionalContentGroupUsage(raw).get_zoom()
    assert zoom is not None
    assert zoom.min is None
    assert zoom.max is None

    zoom.min = 0
    zoom.max = 3.5
    assert zoom.min == pytest.approx(0.0)
    assert zoom.max == pytest.approx(3.5)
    assert isinstance(zoom.get_cos_object().get_dictionary_object(_MIN), COSFloat)

    zoom.min = None
    zoom.max = None
    assert zoom.get_cos_object().get_dictionary_object(_MIN) is None
    assert zoom.get_cos_object().get_dictionary_object(_MAX) is None


def test_name_readers_ignore_non_name_values_and_user_name_array_without_strings() -> None:
    raw = COSDictionary()

    export = COSDictionary()
    export.set_string(_EXPORT_STATE, "ON")
    raw.set_item(_EXPORT, export)

    view = COSDictionary()
    view.set_string(_VIEW_STATE, "OFF")
    raw.set_item(_VIEW, view)

    user = COSDictionary()
    user.set_string(_TYPE, "Ind")
    names = COSArray()
    names.add(COSName.get_pdf_name("NotText"))
    user.set_item(_NAME, names)
    raw.set_item(_USER, user)

    usage = PDOptionalContentGroupUsage(raw)
    assert usage.get_export() is not None
    assert usage.get_export().export_state is None
    assert usage.get_view() is not None
    assert usage.get_view().view_state is None
    assert usage.get_user() is not None
    assert usage.get_user().type is None
    assert usage.get_user().name is None
