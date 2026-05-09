from __future__ import annotations

import pytest

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


def test_wave590_get_default_configuration_repairs_malformed_default_dict() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.D, COSName.get_pdf_name("bad"))
    props = PDOptionalContentProperties(raw)

    cfg = props.get_default_configuration()

    assert cfg.get_name() == "Top"
    assert cfg.get_cos_object() is raw.get_dictionary_object(COSName.D)


def test_wave590_intent_delegates_to_default_configuration() -> None:
    props = PDOptionalContentProperties()

    assert props.get_intent() == "View"
    assert props.is_intent("View") is True

    props.set_intent(["Design", "View"])

    assert props.get_intent() == ["Design", "View"]
    assert props.is_intent("Design") is True
    assert props.is_intent("Print") is False

    props.set_intent(None)

    assert props.get_intent() == "View"


def test_wave590_rbgroup_delegate_enforces_radio_siblings_on_enable() -> None:
    props = PDOptionalContentProperties()
    red = PDOptionalContentGroup("Red")
    blue = PDOptionalContentGroup("Blue")
    green = PDOptionalContentGroup("Green")
    for group in (red, blue, green):
        props.add_group(group)
        props.set_group_enabled(group, False)

    props.add_rbgroup([red, blue])

    assert [[group.get_name() for group in rb] for rb in props.get_rbgroups()] == [
        ["Red", "Blue"]
    ]

    assert props.set_group_enabled(blue, True) is True

    on = _state_array(props, "ON")
    off = _state_array(props, "OFF")
    assert [on.get_object(i) for i in range(on.size())] == [blue.get_cos_object()]
    assert red.get_cos_object() in [off.get_object(i) for i in range(off.size())]
    assert green.get_cos_object() in [off.get_object(i) for i in range(off.size())]


def test_wave590_locked_delegates_to_default_configuration() -> None:
    props = PDOptionalContentProperties()
    first = PDOptionalContentGroup("First")
    second = PDOptionalContentGroup("Second")

    props.set_locked([first])
    props.add_locked(second)

    assert [group.get_name() for group in props.get_locked()] == ["First", "Second"]
    assert props.is_locked(first) is True
    assert props.is_locked(PDOptionalContentGroup("Other")) is False

    props.set_locked(None)

    assert props.get_locked() == []


def test_wave590_configurations_skip_malformed_entries_and_names_without_name() -> None:
    props = PDOptionalContentProperties()
    named = COSDictionary()
    named.set_string(COSName.get_pdf_name("Name"), "Named")
    unnamed = COSDictionary()
    configs = COSArray([COSName.get_pdf_name("bad"), COSObject(4, resolved=named), unnamed])
    props.get_cos_object().set_item(COSName.get_pdf_name("Configs"), configs)

    assert [cfg.get_cos_object() for cfg in props.get_configurations()] == [named, unnamed]
    assert props.get_configuration_names() == ["Named"]
    assert props.get_configuration("Named").get_cos_object() is named
    assert props.get_configuration("Missing") is None
    assert props.has_configuration("Named") is True
    assert props.has_configuration("Missing") is False


def test_wave590_add_configuration_accepts_raw_dict_and_rejects_unknown_type() -> None:
    props = PDOptionalContentProperties()
    raw = COSDictionary()
    raw.set_string(COSName.get_pdf_name("Name"), "Raw")

    returned = props.add_configuration(raw)

    assert isinstance(returned, PDOptionalContentConfiguration)
    assert returned.get_cos_object() is raw
    assert props.get_configuration_names() == ["Raw"]

    with pytest.raises(TypeError, match="config must be"):
        props.add_configuration(object())  # type: ignore[arg-type]
