from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSString
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    USAGE_STATE_OFF,
    USAGE_STATE_ON,
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group_usage import (
    PDOptionalContentGroupUsage,
    PDUsageCreatorInfo,
    PDUsageExport,
    PDUsageLanguage,
    PDUsagePageElement,
    PDUsagePrint,
    PDUsageUser,
    PDUsageView,
    PDUsageZoom,
)

_USAGE = COSName.get_pdf_name("Usage")
_VIEW = COSName.get_pdf_name("View")
_VIEW_STATE = COSName.get_pdf_name("ViewState")
_PRINT = COSName.get_pdf_name("Print")
_PRINT_STATE = COSName.get_pdf_name("PrintState")
_EXPORT = COSName.get_pdf_name("Export")
_EXPORT_STATE = COSName.get_pdf_name("ExportState")
_CREATOR_INFO = COSName.get_pdf_name("CreatorInfo")
_CREATOR = COSName.get_pdf_name("Creator")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_LANGUAGE = COSName.get_pdf_name("Language")
_LANG = COSName.get_pdf_name("Lang")
_PREFERRED = COSName.get_pdf_name("Preferred")
_ZOOM = COSName.get_pdf_name("Zoom")
_MIN = COSName.get_pdf_name("min")
_MAX = COSName.get_pdf_name("max")
_USER = COSName.get_pdf_name("User")
_TYPE = COSName.get_pdf_name("Type")
_NAME = COSName.get_pdf_name("Name")
_PAGE_ELEMENT = COSName.get_pdf_name("PageElement")
_ON = COSName.get_pdf_name("ON")
_OFF = COSName.get_pdf_name("OFF")


def test_usage_accessors_default_to_none() -> None:
    group = PDOptionalContentGroup("Layer")
    assert group.get_usage_view_state() is None
    assert group.get_usage_print_state() is None
    assert group.get_usage_export_state() is None
    assert group.get_usage_creator() is None
    assert group.get_usage_language() is None
    # /Usage must not be auto-materialised by reads.
    assert group.get_cos_object().get_dictionary_object(_USAGE) is None


def test_round_trip_usage_state_accessors() -> None:
    group = PDOptionalContentGroup("Layer")

    group.set_usage_view_state(USAGE_STATE_ON)
    group.set_usage_print_state(USAGE_STATE_OFF)
    group.set_usage_export_state(USAGE_STATE_ON)

    assert group.get_usage_view_state() == "ON"
    assert group.get_usage_print_state() == "OFF"
    assert group.get_usage_export_state() == "ON"


def test_round_trip_usage_string_accessors() -> None:
    group = PDOptionalContentGroup("Layer")

    group.set_usage_creator("Acme Author 1.0")
    group.set_usage_language("en-US")

    assert group.get_usage_creator() == "Acme Author 1.0"
    assert group.get_usage_language() == "en-US"


def test_set_view_state_writes_cos_name_under_correct_path() -> None:
    group = PDOptionalContentGroup("Layer")
    group.set_usage_view_state(USAGE_STATE_ON)

    usage = group.get_cos_object().get_dictionary_object(_USAGE)
    assert isinstance(usage, COSDictionary)
    view = usage.get_dictionary_object(_VIEW)
    assert isinstance(view, COSDictionary)
    state = view.get_dictionary_object(_VIEW_STATE)
    assert isinstance(state, COSName)
    assert state == _ON


def test_setting_none_removes_entry_but_leaves_siblings() -> None:
    group = PDOptionalContentGroup("Layer")
    group.set_usage_view_state(USAGE_STATE_ON)
    group.set_usage_print_state(USAGE_STATE_OFF)
    group.set_usage_creator("Acme")

    group.set_usage_view_state(None)

    # View entry pruned, siblings intact.
    assert group.get_usage_view_state() is None
    assert group.get_usage_print_state() == "OFF"
    assert group.get_usage_creator() == "Acme"

    usage = group.get_cos_object().get_dictionary_object(_USAGE)
    assert isinstance(usage, COSDictionary)
    assert usage.get_dictionary_object(_VIEW) is None
    assert usage.get_dictionary_object(_PRINT) is not None
    assert usage.get_dictionary_object(_CREATOR_INFO) is not None


def test_clearing_all_usage_entries_removes_usage_dict() -> None:
    group = PDOptionalContentGroup("Layer")
    group.set_usage_view_state(USAGE_STATE_ON)
    group.set_usage_print_state(USAGE_STATE_OFF)
    group.set_usage_export_state(USAGE_STATE_ON)
    group.set_usage_creator("Acme")
    group.set_usage_language("en-US")

    group.set_usage_view_state(None)
    group.set_usage_print_state(None)
    group.set_usage_export_state(None)
    group.set_usage_creator(None)
    group.set_usage_language(None)

    # Entire /Usage chain pruned when no entries remain.
    assert group.get_cos_object().get_dictionary_object(_USAGE) is None


def test_setting_none_when_usage_absent_is_a_noop() -> None:
    group = PDOptionalContentGroup("Layer")
    group.set_usage_view_state(None)
    group.set_usage_creator(None)
    # Must not have created an empty /Usage dict.
    assert group.get_cos_object().get_dictionary_object(_USAGE) is None


def test_invalid_usage_state_raises() -> None:
    group = PDOptionalContentGroup("Layer")
    with pytest.raises(ValueError):
        group.set_usage_view_state("Maybe")


def test_creator_and_language_share_usage_dict() -> None:
    group = PDOptionalContentGroup("Layer")
    group.set_usage_creator("Acme")
    group.set_usage_language("fr")

    usage = group.get_cos_object().get_dictionary_object(_USAGE)
    assert isinstance(usage, COSDictionary)

    creator_info = usage.get_dictionary_object(_CREATOR_INFO)
    assert isinstance(creator_info, COSDictionary)
    assert creator_info.get_string(_CREATOR) == "Acme"

    language = usage.get_dictionary_object(_LANGUAGE)
    assert isinstance(language, COSDictionary)
    assert language.get_string(_LANG) == "fr"


# ---------------------------------------------------------------------------
# Typed PDOptionalContentGroupUsage wrapper tests
# ---------------------------------------------------------------------------


def _build_usage_dict() -> COSDictionary:
    """Build a synthetic /Usage dict containing every Table 102 sub-dict."""
    usage = COSDictionary()

    creator_info = COSDictionary()
    creator_info.set_string(_CREATOR, "Acme Author 1.0")
    creator_info.set_item(_SUBTYPE, COSName.get_pdf_name("Technical"))
    usage.set_item(_CREATOR_INFO, creator_info)

    language = COSDictionary()
    language.set_string(_LANG, "en-US")
    language.set_item(_PREFERRED, COSName.get_pdf_name("ON"))
    usage.set_item(_LANGUAGE, language)

    export = COSDictionary()
    export.set_item(_EXPORT_STATE, COSName.get_pdf_name("OFF"))
    usage.set_item(_EXPORT, export)

    zoom = COSDictionary()
    zoom.set_item(_MIN, COSFloat(0.5))
    zoom.set_item(_MAX, COSFloat(2.0))
    usage.set_item(_ZOOM, zoom)

    print_dict = COSDictionary()
    print_dict.set_item(_SUBTYPE, COSName.get_pdf_name("Watermark"))
    print_dict.set_item(_PRINT_STATE, COSName.get_pdf_name("ON"))
    usage.set_item(_PRINT, print_dict)

    view = COSDictionary()
    view.set_item(_VIEW_STATE, COSName.get_pdf_name("ON"))
    usage.set_item(_VIEW, view)

    user = COSDictionary()
    user.set_item(_TYPE, COSName.get_pdf_name("Ind"))
    user.set_string(_NAME, "Alice")
    usage.set_item(_USER, user)

    page_element = COSDictionary()
    page_element.set_item(_SUBTYPE, COSName.get_pdf_name("HF"))
    usage.set_item(_PAGE_ELEMENT, page_element)

    return usage


def test_typed_wrapper_returns_none_when_subdicts_absent() -> None:
    wrapper = PDOptionalContentGroupUsage()
    assert wrapper.get_creator_info() is None
    assert wrapper.get_language() is None
    assert wrapper.get_export() is None
    assert wrapper.get_zoom() is None
    assert wrapper.get_print() is None
    assert wrapper.get_view() is None
    assert wrapper.get_user() is None
    assert wrapper.get_page_element() is None


def test_typed_wrapper_reads_all_subdicts() -> None:
    wrapper = PDOptionalContentGroupUsage(_build_usage_dict())

    creator_info = wrapper.get_creator_info()
    assert isinstance(creator_info, PDUsageCreatorInfo)
    assert creator_info.creator == "Acme Author 1.0"
    assert creator_info.subtype == "Technical"

    language = wrapper.get_language()
    assert isinstance(language, PDUsageLanguage)
    assert language.lang == "en-US"
    assert language.preferred == "ON"

    export = wrapper.get_export()
    assert isinstance(export, PDUsageExport)
    assert export.export_state == "OFF"

    zoom = wrapper.get_zoom()
    assert isinstance(zoom, PDUsageZoom)
    assert zoom.min == pytest.approx(0.5)
    assert zoom.max == pytest.approx(2.0)

    print_dict = wrapper.get_print()
    assert isinstance(print_dict, PDUsagePrint)
    assert print_dict.subtype == "Watermark"
    assert print_dict.print_state == "ON"

    view = wrapper.get_view()
    assert isinstance(view, PDUsageView)
    assert view.view_state == "ON"

    user = wrapper.get_user()
    assert isinstance(user, PDUsageUser)
    assert user.type == "Ind"
    assert user.name == "Alice"

    page_element = wrapper.get_page_element()
    assert isinstance(page_element, PDUsagePageElement)
    assert page_element.subtype == "HF"


def test_typed_wrapper_round_trip_writes_back_to_cos_dict() -> None:
    wrapper = PDOptionalContentGroupUsage()

    creator_info = wrapper.get_or_create_creator_info()
    creator_info.creator = "Foo"
    creator_info.subtype = "Bar"

    zoom = wrapper.get_or_create_zoom()
    zoom.min = 1.0
    zoom.max = 4.0

    view = wrapper.get_or_create_view()
    view.view_state = "OFF"

    underlying = wrapper.get_cos_object()
    ci = underlying.get_dictionary_object(_CREATOR_INFO)
    assert isinstance(ci, COSDictionary)
    assert ci.get_string(_CREATOR) == "Foo"
    assert ci.get_dictionary_object(_SUBTYPE) == COSName.get_pdf_name("Bar")

    z = underlying.get_dictionary_object(_ZOOM)
    assert isinstance(z, COSDictionary)
    assert z.get_float(_MIN) == pytest.approx(1.0)
    assert z.get_float(_MAX) == pytest.approx(4.0)

    v = underlying.get_dictionary_object(_VIEW)
    assert isinstance(v, COSDictionary)
    assert v.get_dictionary_object(_VIEW_STATE) == _OFF


def test_typed_wrapper_setter_none_removes_entry() -> None:
    wrapper = PDOptionalContentGroupUsage(_build_usage_dict())

    creator_info = wrapper.get_creator_info()
    assert creator_info is not None
    creator_info.creator = None
    creator_info.subtype = None

    underlying = wrapper.get_cos_object().get_dictionary_object(_CREATOR_INFO)
    assert isinstance(underlying, COSDictionary)
    assert underlying.get_string(_CREATOR) is None
    assert underlying.get_dictionary_object(_SUBTYPE) is None


def test_export_state_validates() -> None:
    wrapper = PDOptionalContentGroupUsage()
    export = wrapper.get_or_create_export()
    with pytest.raises(ValueError):
        export.export_state = "Maybe"


def test_view_state_validates() -> None:
    wrapper = PDOptionalContentGroupUsage()
    view = wrapper.get_or_create_view()
    with pytest.raises(ValueError):
        view.view_state = "Maybe"


def test_print_state_validates() -> None:
    wrapper = PDOptionalContentGroupUsage()
    print_dict = wrapper.get_or_create_print()
    with pytest.raises(ValueError):
        print_dict.print_state = "Maybe"


def test_state_setter_lowercase_is_normalized_to_upper() -> None:
    wrapper = PDOptionalContentGroupUsage()
    view = wrapper.get_or_create_view()
    view.view_state = "on"
    assert view.view_state == "ON"


def test_user_name_array_returns_first_text_string() -> None:
    user = COSDictionary()
    arr = COSArray()
    arr.add(COSString("Alice"))
    arr.add(COSString("Bob"))
    user.set_item(_NAME, arr)

    usage = COSDictionary()
    usage.set_item(_USER, user)

    wrapper = PDOptionalContentGroupUsage(usage)
    user_wrapper = wrapper.get_user()
    assert user_wrapper is not None
    assert user_wrapper.name == "Alice"


def test_get_or_create_returns_same_underlying_dict_on_repeated_calls() -> None:
    wrapper = PDOptionalContentGroupUsage()
    first = wrapper.get_or_create_creator_info()
    second = wrapper.get_or_create_creator_info()
    assert first.get_cos_object() is second.get_cos_object()


def test_pd_optional_content_group_get_usage_returns_wrapper() -> None:
    group = PDOptionalContentGroup("Layer")
    # No /Usage yet → None.
    assert group.get_usage() is None
    assert group.get_usage_dict() is None

    group.set_usage_view_state(USAGE_STATE_ON)
    usage = group.get_usage()
    assert isinstance(usage, PDOptionalContentGroupUsage)
    view = usage.get_view()
    assert isinstance(view, PDUsageView)
    assert view.view_state == "ON"

    raw = group.get_usage_dict()
    assert isinstance(raw, COSDictionary)
    assert raw is usage.get_cos_object()


def test_pd_optional_content_group_get_or_create_usage() -> None:
    group = PDOptionalContentGroup("Layer")
    usage = group.get_or_create_usage()
    assert isinstance(usage, PDOptionalContentGroupUsage)
    # /Usage now materialised in the OCG dict.
    assert group.get_cos_object().get_dictionary_object(_USAGE) is usage.get_cos_object()

    creator_info = usage.get_or_create_creator_info()
    creator_info.creator = "PyPDFBox"
    assert group.get_usage_creator() == "PyPDFBox"


def test_typed_wrapper_writes_observed_by_legacy_helpers() -> None:
    """Wrappers and the existing PDOCG.set_usage_* helpers share state."""
    group = PDOptionalContentGroup("Layer")
    usage = group.get_or_create_usage()

    view = usage.get_or_create_view()
    view.view_state = "ON"

    # Legacy state accessor sees the new write.
    assert group.get_usage_view_state() == "ON"

    # And vice-versa: legacy setter is observed by the typed wrapper.
    group.set_usage_view_state(USAGE_STATE_OFF)
    refreshed = group.get_usage()
    assert refreshed is not None
    refreshed_view = refreshed.get_view()
    assert refreshed_view is not None
    assert refreshed_view.view_state == "OFF"
