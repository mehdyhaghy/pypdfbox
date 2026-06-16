from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)


def _default_dict(props: PDOptionalContentProperties) -> COSDictionary:
    raw = props.get_cos_object().get_dictionary_object(COSName.D)
    assert isinstance(raw, COSDictionary)
    return raw


def _state_array(props: PDOptionalContentProperties, name: str) -> COSArray:
    raw = _default_dict(props).get_dictionary_object(COSName.get_pdf_name(name))
    assert isinstance(raw, COSArray)
    return raw


def _usage_state(category: str, state_key: str, state: str) -> COSDictionary:
    usage = COSDictionary()
    category_dict = COSDictionary()
    category_dict.set_item(COSName.get_pdf_name(state_key), COSName.get_pdf_name(state))
    usage.set_item(COSName.get_pdf_name(category), category_dict)
    return usage


def test_wave549_auto_state_skips_malformed_entries_then_uses_ordered_categories() -> None:
    props = PDOptionalContentProperties()
    layer = PDOptionalContentGroup("Layer")
    props.add_group(layer)
    props.set_base_state("OFF")

    usage = _usage_state("View", "ViewState", "ON")
    unchanged = COSDictionary()
    unchanged.set_item(COSName.get_pdf_name("ViewState"), COSName.get_pdf_name("Unchanged"))
    usage.set_item(COSName.get_pdf_name("Print"), unchanged)
    layer.get_cos_object().set_item(COSName.get_pdf_name("Usage"), usage)

    wrong_event = COSDictionary()
    wrong_event.set_item(COSName.get_pdf_name("Event"), COSName.get_pdf_name("Print"))

    missing_categories = COSDictionary()
    missing_categories.set_item(COSName.get_pdf_name("Event"), COSName.get_pdf_name("View"))

    bad_ocgs = COSDictionary()
    bad_ocgs.set_item(COSName.get_pdf_name("Event"), COSName.get_pdf_name("View"))
    bad_ocgs.set_item(COSName.get_pdf_name("Category"), COSName.get_pdf_name("View"))
    bad_ocgs.set_item(COSName.get_pdf_name("OCGs"), COSName.get_pdf_name("not-array"))

    valid = COSDictionary()
    valid.set_item(COSName.get_pdf_name("Event"), COSName.get_pdf_name("View"))
    valid.set_item(
        COSName.get_pdf_name("Category"),
        COSArray(
            [
                COSName.get_pdf_name("Print"),
                COSName.get_pdf_name("junk"),
                COSName.get_pdf_name("View"),
            ]
        ),
    )
    valid.set_item(
        COSName.get_pdf_name("OCGs"),
        COSArray([COSObject(7, resolved=layer.get_cos_object())]),
    )

    _default_dict(props).set_item(
        COSName.get_pdf_name("AS"),
        COSArray([COSName.get_pdf_name("bad"), wrong_event, missing_categories, bad_ocgs, valid]),
    )

    assert props.compute_visible_ocgs("View") == {id(layer.get_cos_object())}


def test_wave549_auto_state_unknown_state_name_leaves_prior_visibility() -> None:
    props = PDOptionalContentProperties()
    layer = PDOptionalContentGroup("Layer")
    props.add_group(layer)

    layer.get_cos_object().set_item(
        COSName.get_pdf_name("Usage"),
        _usage_state("View", "ViewState", "Maybe"),
    )
    auto_state = COSDictionary()
    auto_state.set_item(COSName.get_pdf_name("Event"), COSName.get_pdf_name("View"))
    auto_state.set_item(COSName.get_pdf_name("Category"), COSName.get_pdf_name("View"))
    auto_state.set_item(COSName.get_pdf_name("OCGs"), COSArray([layer.get_cos_object()]))
    _default_dict(props).set_item(COSName.get_pdf_name("AS"), COSArray([auto_state]))

    assert props.compute_visible_ocgs("View") == {id(layer.get_cos_object())}


def test_wave549_visibility_aliases_move_entries_and_report_existing_state() -> None:
    props = PDOptionalContentProperties()
    layer = PDOptionalContentGroup("Layer")
    props.add_group(layer)

    assert props.set_hidden("Layer") is False
    assert props.is_group_visible(layer) is False
    assert _state_array(props, "OFF").get_object(0) is layer.get_cos_object()

    assert props.set_visible(layer) is True
    assert props.is_group_visible("Layer") is True
    assert _state_array(props, "OFF").size() == 0
    assert _state_array(props, "ON").get_object(0) is layer.get_cos_object()


def test_wave549_group_count_and_names_skip_or_mark_malformed_ocg_slots() -> None:
    props = PDOptionalContentProperties()
    first = PDOptionalContentGroup("First")
    unnamed = COSDictionary()
    ocgs = COSArray(
        [
            first.get_cos_object(),
            COSName.get_pdf_name("bad"),
            COSObject(8, resolved=unnamed),
        ]
    )
    props.get_cos_object().set_item(COSName.get_pdf_name("OCGs"), ocgs)

    assert props.get_groups()[0].get_cos_object() is first.get_cos_object()
    assert props.get_groups()[1].get_cos_object() is unnamed
    assert props.get_group_count() == 2
    assert len(props) == 2
    assert props.has_groups() is True
    # Upstream getGroupNames() stores an *uncoalesced* getString(/Name) for
    # dictionary entries (PDOptionalContentProperties.java line 178): the third
    # slot is an empty COSDictionary with no /Name, so it yields a genuine
    # ``None`` (Java null), whereas the non-dictionary COSName slot yields "".
    # (Retargeted in wave 1559 after the live oracle proved upstream does not
    # collapse the dict-with-no-/Name case to "".)
    assert props.get_group_names() == ["First", "", None]


def test_wave549_base_state_rejects_non_state_inputs() -> None:
    props = PDOptionalContentProperties()

    with pytest.raises(TypeError, match="base state must be str"):
        props.set_base_state(object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="base state must be"):
        props.set_base_state("Visible")
    with pytest.raises(ValueError, match="BaseState has no member"):
        props.is_base_state(COSName.get_pdf_name("Visible"))
