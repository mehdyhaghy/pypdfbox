from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.cos.cos_object import COSObject
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentConfiguration,
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


def test_add_group_sets_type_and_appends_to_order() -> None:
    props = PDOptionalContentProperties()
    raw = COSDictionary()
    raw.set_string(COSName.get_pdf_name("Name"), "Layer")
    group = PDOptionalContentGroup(raw)
    raw.remove_item(COSName.TYPE)

    props.add_group(group)

    assert raw.get_dictionary_object(COSName.TYPE) == COSName.get_pdf_name("OCG")
    order = _default_dict(props).get_dictionary_object(COSName.get_pdf_name("Order"))
    assert isinstance(order, COSArray)
    assert order.size() == 1
    assert order.get_object(0) is raw


def test_get_group_and_has_group_resolve_indirect_ocg_entries() -> None:
    props = PDOptionalContentProperties()
    group = PDOptionalContentGroup("Indirect")
    ocgs = props.get_cos_object().get_dictionary_object(COSName.get_pdf_name("OCGs"))
    assert isinstance(ocgs, COSArray)
    ocgs.add(COSObject(12, resolved=group.get_cos_object()))

    found = props.get_group("Indirect")

    assert found is not None
    assert found.get_cos_object() is group.get_cos_object()
    assert props.has_group("Indirect") is True
    assert props.has_group("Missing") is False


def test_set_group_enabled_by_name_updates_every_matching_layer() -> None:
    props = PDOptionalContentProperties()
    first = PDOptionalContentGroup("Duplicate")
    second = PDOptionalContentGroup("Duplicate")
    props.add_group(first)
    props.add_group(second)

    assert props.set_group_enabled("Duplicate", False) is False

    off = _state_array(props, "OFF")
    assert off.size() == 2
    assert {off.get_object(0), off.get_object(1)} == {
        first.get_cos_object(),
        second.get_cos_object(),
    }
    assert props.is_group_enabled(first) is False
    assert props.is_group_enabled(second) is False


def test_set_group_enabled_preserves_indirect_entry_when_turning_on() -> None:
    props = PDOptionalContentProperties()
    group = PDOptionalContentGroup("Wrapped")
    props.add_group(group)
    wrapped = COSObject(44, resolved=group.get_cos_object())
    _default_dict(props).set_item(COSName.get_pdf_name("OFF"), COSArray([wrapped]))

    assert props.set_group_enabled(group, True) is True

    on = _state_array(props, "ON")
    off = _state_array(props, "OFF")
    assert on.size() == 1
    assert on.get(0) is wrapped
    assert off.size() == 0


def test_intent_delegates_to_default_configuration_and_can_clear() -> None:
    props = PDOptionalContentProperties()

    assert props.get_intent() == "View"
    assert props.is_intent("View") is True

    props.set_intent(["View", "Design"])
    assert props.get_intent() == ["View", "Design"]
    assert props.is_intent("Design") is True

    props.set_intent(None)
    assert props.get_intent() == "View"
    assert props.is_intent("Design") is False


def test_add_configuration_with_wrapper_returns_same_wrapper() -> None:
    props = PDOptionalContentProperties()
    config = PDOptionalContentConfiguration()
    config.set_name("Review")

    returned = props.add_configuration(config)

    assert returned is config
    assert props.get_configuration("Review") is not None
    assert props.get_configuration("Review").get_cos_object() is config.get_cos_object()
    assert props.get_configuration_names() == ["Review"]


def test_configuration_accessors_skip_junk_and_unnamed_entries() -> None:
    props = PDOptionalContentProperties()
    named = COSDictionary()
    named.set_string(COSName.get_pdf_name("Name"), "Named")
    unnamed = COSDictionary()
    configs = COSArray(
        [
            COSName.get_pdf_name("junk"),
            COSObject(5, resolved=unnamed),
            COSObject(6, resolved=named),
        ]
    )
    props.get_cos_object().set_item(COSName.get_pdf_name("Configs"), configs)

    wrapped = props.get_configurations()

    assert [cfg.get_cos_object() for cfg in wrapped] == [unnamed, named]
    assert props.get_configuration_names() == ["Named"]
    assert props.get_configuration("Named").get_cos_object() is named
    assert props.get_configuration("Missing") is None


def test_get_configurations_returns_empty_when_configs_is_not_array() -> None:
    props = PDOptionalContentProperties()
    props.get_cos_object().set_item(
        COSName.get_pdf_name("Configs"), COSName.get_pdf_name("bad")
    )

    assert props.get_configurations() == []
    assert props.get_configuration_names() == []
