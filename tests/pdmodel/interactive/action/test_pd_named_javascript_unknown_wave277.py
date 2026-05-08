"""Wave 277 coverage for Named, JavaScript, and unknown action edges."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream, COSString
from pypdfbox.pdmodel.interactive.action import (
    PDAction,
    PDActionJavaScript,
    PDActionNamed,
    PDActionUnknown,
)

_N: COSName = COSName.get_pdf_name("N")
_JS: COSName = COSName.get_pdf_name("JS")
_S: COSName = COSName.get_pdf_name("S")
_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]


def test_named_default_type_and_subtype_without_name_payload() -> None:
    action = PDActionNamed()

    assert action.get_type() == "Action"
    assert action.get_sub_type() == "Named"
    assert action.get_n() is None
    assert action.is_standard_named_action() is False


@pytest.mark.parametrize(
    ("name", "predicate"),
    [
        (PDActionNamed.NAMED_ACTION_NEXT_PAGE, "is_next_page"),
        (PDActionNamed.NAMED_ACTION_PREV_PAGE, "is_prev_page"),
        (PDActionNamed.NAMED_ACTION_FIRST_PAGE, "is_first_page"),
        (PDActionNamed.NAMED_ACTION_LAST_PAGE, "is_last_page"),
    ],
)
def test_named_name_accessor_drives_standard_predicates(
    name: str, predicate: str
) -> None:
    action = PDActionNamed()
    action.set_n(name)

    assert action.get_n() == name
    assert getattr(action, predicate)() is True
    assert action.is_standard_named_action() is True


def test_named_allows_extension_name_then_clears_back_to_absent() -> None:
    action = PDActionNamed()
    action.set_n("GoBack")

    assert action.get_n() == "GoBack"
    assert action.is_standard_named_action() is False
    assert action.get_cos_object().contains_key(_N)

    action.set_n(None)

    assert action.get_n() is None
    assert not action.get_cos_object().contains_key(_N)


def test_named_factory_round_trips_existing_cos_dictionary() -> None:
    raw = COSDictionary()
    raw.set_name(_S, PDActionNamed.SUB_TYPE)
    raw.set_name(_N, PDActionNamed.NAMED_ACTION_LAST_PAGE)

    action = PDAction.create(raw)

    assert isinstance(action, PDActionNamed)
    assert action.get_cos_object() is raw
    assert action.get_n() == "LastPage"
    assert action.is_last_page() is True


def test_named_malformed_name_shape_is_treated_as_missing() -> None:
    raw = COSDictionary()
    raw.set_name(_S, PDActionNamed.SUB_TYPE)
    raw.set_item(_N, COSString("NextPage"))
    action = PDActionNamed(raw)

    assert action.get_n() is None
    assert action.is_next_page() is False
    assert action.is_standard_named_action() is False

    action.set_n(None)
    assert not raw.contains_key(_N)


def test_javascript_string_constructor_sets_type_subtype_and_script() -> None:
    action = PDActionJavaScript("app.alert('wave277');")

    assert action.get_type() == "Action"
    assert action.get_sub_type() == "JavaScript"
    assert action.get_action() == "app.alert('wave277');"
    assert action.is_string_payload() is True
    assert action.is_stream_payload() is False


def test_javascript_set_action_round_trips_and_clear_removes_js() -> None:
    action = PDActionJavaScript()
    action.set_action("console.println('first');")
    action.set_action("console.println('second');")

    raw = action.get_cos_object().get_dictionary_object(_JS)
    assert isinstance(raw, COSString)
    assert action.get_action() == "console.println('second');"
    assert action.has_action() is True
    assert action.is_empty() is False

    action.clear_action()

    assert action.get_action() is None
    assert action.has_action() is False
    assert action.is_empty() is True
    assert not action.get_cos_object().contains_key(_JS)


def test_javascript_set_action_none_clears_stream_payload() -> None:
    action = PDActionJavaScript()
    stream = COSStream()
    stream.set_raw_data(b"doWork();")
    action.get_cos_object().set_item(_JS, stream)

    assert action.is_stream_payload() is True

    action.set_action(None)

    assert action.get_action() is None
    assert action.is_stream_payload() is False
    assert not action.get_cos_object().contains_key(_JS)


def test_javascript_reads_filtered_cos_stream_payload() -> None:
    source = "var n = 277;\nconsole.println(n);"
    stream = COSStream()
    stream.set_data(source.encode("utf-8"), filters=COSName.FLATE_DECODE)  # type: ignore[attr-defined]
    action = PDActionJavaScript()
    action.get_cos_object().set_item(_JS, stream)

    assert action.get_action() == source
    assert action.is_stream_payload() is True
    assert action.is_string_payload() is False
    assert action.is_empty() is False


def test_javascript_empty_cos_stream_is_supported_as_empty_script() -> None:
    action = PDActionJavaScript()
    action.get_cos_object().set_item(_JS, COSStream())

    assert action.has_action() is True
    assert action.get_action() == ""
    assert action.is_empty() is True


def test_javascript_factory_round_trips_existing_cos_dictionary() -> None:
    raw = COSDictionary()
    raw.set_name(_S, PDActionJavaScript.SUB_TYPE)
    raw.set_string(_JS, "trustedFunction();")

    action = PDAction.create(raw)

    assert isinstance(action, PDActionJavaScript)
    assert action.get_cos_object() is raw
    assert action.get_action() == "trustedFunction();"
    assert action.is_valid() is True


def test_javascript_malformed_script_shape_is_present_but_not_usable() -> None:
    action = PDActionJavaScript()
    action.get_cos_object().set_item(_JS, COSArray([COSString("not valid here")]))

    assert action.has_action() is True
    assert action.get_action() is None
    assert action.is_empty() is True
    assert action.is_string_payload() is False
    assert action.is_stream_payload() is False


def test_unknown_action_preserves_unrecognized_action_type() -> None:
    raw = COSDictionary()
    raw.set_name(_S, "VendorSpecificAction")
    raw.set_string("VendorPayload", "opaque")

    action = PDAction.create(raw)

    assert isinstance(action, PDActionUnknown)
    assert action.get_cos_object() is raw
    assert action.get_type() == "Action"
    assert action.get_sub_type() == "VendorSpecificAction"
    assert raw.get_string("VendorPayload") == "opaque"


def test_unknown_default_has_action_type_but_no_subtype_default() -> None:
    action = PDActionUnknown()

    assert action.get_type() == "Action"
    assert action.get_sub_type() is None
    assert action.get_cos_object().get_name(_TYPE) == "Action"
    assert not action.get_cos_object().contains_key(_S)


def test_unknown_existing_type_is_not_overwritten() -> None:
    raw = COSDictionary()
    raw.set_name(_TYPE, "NotAction")
    raw.set_name(_S, "StillUnknown")

    action = PDActionUnknown(raw)

    assert action.get_type() == "NotAction"
    assert action.get_sub_type() == "StillUnknown"
    assert action.get_cos_object() is raw
