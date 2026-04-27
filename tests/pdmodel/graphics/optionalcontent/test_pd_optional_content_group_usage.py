from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    USAGE_STATE_OFF,
    USAGE_STATE_ON,
    PDOptionalContentGroup,
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
_LANGUAGE = COSName.get_pdf_name("Language")
_LANG = COSName.get_pdf_name("Lang")
_ON = COSName.get_pdf_name("ON")


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
