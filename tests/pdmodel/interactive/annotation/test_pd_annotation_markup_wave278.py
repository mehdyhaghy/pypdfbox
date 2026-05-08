from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSDictionary,
    COSInteger,
    COSName,
    COSObject,
    COSString,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_caret import (
    PDAnnotationCaret,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
    PDAnnotationMarkup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_popup import (
    PDAnnotationPopup,
)


def test_review_workflow_accessors_default_to_none_or_spec_reply() -> None:
    ann = PDAnnotationCaret()

    assert ann.get_creation_date() is None
    assert ann.get_in_reply_to() is None
    assert ann.get_popup() is None
    assert ann.has_popup() is False
    assert ann.get_reply_type() == PDAnnotationMarkup.RT_REPLY
    assert ann.get_intent() is None
    assert ann.get_rich_contents() is None
    assert ann.get_external_data() is None


def test_review_workflow_accessors_round_trip_from_existing_cos_dictionary() -> None:
    popup = PDAnnotationPopup()
    popup.set_open(True)
    parent = COSDictionary()
    external_data = COSDictionary()

    raw = COSDictionary()
    raw.set_string("CreationDate", "D:20260508120000-05'00'")
    raw.set_item("IRT", parent)
    raw.set_item("Popup", popup.get_cos_object())
    raw.set_name("RT", PDAnnotationMarkup.RT_GROUP)
    raw.set_name("IT", "PolygonDimension")
    raw.set_string("RC", "<body><p>round trip</p></body>")
    raw.set_item("ExData", external_data)

    ann = PDAnnotationCaret(raw)

    assert ann.get_creation_date() == "D:20260508120000-05'00'"
    assert ann.get_in_reply_to() is parent
    assert ann.has_popup() is True
    assert ann.get_popup() is not None
    assert ann.get_popup().get_cos_object() is popup.get_cos_object()
    assert ann.get_popup().get_open() is True
    assert ann.get_reply_type() == PDAnnotationMarkup.RT_GROUP
    assert ann.get_intent() == "PolygonDimension"
    assert ann.get_rich_contents() == "<body><p>round trip</p></body>"
    assert ann.get_external_data() is external_data


def test_review_workflow_setters_clear_entries_and_restore_reply_default() -> None:
    ann = PDAnnotationCaret()
    ann.set_creation_date("D:20260508120100-05'00'")
    ann.set_in_reply_to(COSDictionary())
    ann.set_popup(PDAnnotationPopup())
    ann.set_reply_type(PDAnnotationMarkup.RT_GROUP)
    ann.set_intent("FreeTextCallout")
    ann.set_rich_contents("<body><p>x</p></body>")
    ann.set_external_data(COSDictionary())

    ann.set_creation_date(None)
    ann.set_in_reply_to(None)
    ann.set_popup(None)
    ann.set_reply_type(None)
    ann.set_intent(None)
    ann.set_rich_contents(None)
    ann.set_external_data(None)

    raw = ann.get_cos_object()
    for key in ("CreationDate", "IRT", "Popup", "RT", "IT", "RC", "ExData"):
        assert key not in raw

    assert ann.get_creation_date() is None
    assert ann.get_in_reply_to() is None
    assert ann.get_popup() is None
    assert ann.has_popup() is False
    assert ann.get_reply_type() == PDAnnotationMarkup.RT_REPLY
    assert ann.get_intent() is None
    assert ann.get_rich_contents() is None
    assert ann.get_external_data() is None


def test_set_in_reply_to_accepts_typed_annotation_and_stores_its_cos_object() -> None:
    ann = PDAnnotationCaret()
    parent = PDAnnotationCaret()

    ann.set_in_reply_to(parent)

    assert ann.get_cos_object().get_item("IRT") is parent.get_cos_object()
    assert ann.get_in_reply_to() is parent.get_cos_object()


def test_dictionary_accessors_resolve_indirect_cos_objects() -> None:
    popup_dict = PDAnnotationPopup().get_cos_object()
    external_data = COSDictionary()
    parent = COSDictionary()
    raw = COSDictionary()
    raw.set_item("Popup", COSObject(21, resolved=popup_dict))
    raw.set_item("ExData", COSObject(22, resolved=external_data))
    raw.set_item("IRT", COSObject(23, resolved=parent))

    ann = PDAnnotationCaret(raw)

    assert ann.has_popup() is True
    assert ann.get_popup() is not None
    assert ann.get_popup().get_cos_object() is popup_dict
    assert ann.get_external_data() is external_data
    assert ann.get_in_reply_to() is parent


def test_rich_contents_decodes_indirect_cos_string() -> None:
    raw = COSDictionary()
    raw.set_item("RC", COSObject(24, resolved=COSString("indirect rich text")))

    ann = PDAnnotationCaret(raw)

    assert ann.get_rich_contents() == "indirect rich text"


@pytest.mark.parametrize(
    ("key", "value", "getter_name", "expected"),
    [
        ("CreationDate", COSInteger.get(1), "get_creation_date", None),
        ("Popup", COSName.get_pdf_name("NotADictionary"), "get_popup", None),
        ("RT", COSString("Group"), "get_reply_type", PDAnnotationMarkup.RT_REPLY),
        ("IT", COSString("FreeText"), "get_intent", None),
        ("RC", COSName.get_pdf_name("NotAStringOrStream"), "get_rich_contents", None),
        ("ExData", COSString("not a dictionary"), "get_external_data", None),
    ],
)
def test_malformed_review_workflow_shapes_return_safe_defaults(
    key: str,
    value: object,
    getter_name: str,
    expected: object,
) -> None:
    raw = COSDictionary()
    raw.set_item(key, value)  # type: ignore[arg-type]
    ann = PDAnnotationCaret(raw)

    assert getattr(ann, getter_name)() == expected


def test_in_reply_to_preserves_malformed_raw_cos_shape() -> None:
    marker = COSName.get_pdf_name("UnexpectedIRT")
    ann = PDAnnotationCaret()
    ann.get_cos_object().set_item("IRT", marker)

    assert ann.get_in_reply_to() is marker
