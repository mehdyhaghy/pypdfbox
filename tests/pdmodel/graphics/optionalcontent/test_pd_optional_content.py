from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)


def test_group_round_trip_name_and_intents() -> None:
    group = PDOptionalContentGroup("Layer 1")
    assert group.get_name() == "Layer 1"

    cos = group.get_cos_object()
    assert cos.get_dictionary_object(COSName.TYPE) == COSName.get_pdf_name("OCG")  # type: ignore[attr-defined]

    group.set_name("Layer A")
    assert group.get_name() == "Layer A"

    view = COSName.get_pdf_name("View")
    design = COSName.get_pdf_name("Design")
    group.set_intents(view)
    assert group.get_intents() == [view]
    group.set_intents([view, design])
    assert group.get_intents() == [view, design]
    group.set_intents(None)
    assert group.get_intents() == []


def test_group_rejects_wrong_type_dictionary() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.get_pdf_name("Catalog"))  # type: ignore[attr-defined]
    with pytest.raises(ValueError):
        PDOptionalContentGroup(raw)


def test_group_renders_state_round_trip_and_export_fallback() -> None:
    group = PDOptionalContentGroup("L")
    assert group.get_render_state("Print") is None

    group.set_render_state("OFF", "Print")
    assert group.get_render_state("Print") == "OFF"

    # Export fallback when View entry missing.
    group.set_render_state("ON", "Export")
    assert group.get_render_state("View") == "ON"


def test_properties_default_layout() -> None:
    props = PDOptionalContentProperties()
    cos = props.get_cos_object()
    ocgs = cos.get_dictionary_object(COSName.get_pdf_name("OCGs"))
    d = cos.get_dictionary_object(COSName.D)  # type: ignore[attr-defined]
    assert isinstance(ocgs, COSArray)
    assert isinstance(d, COSDictionary)
    assert d.get_string(COSName.get_pdf_name("Name")) == "Top"


def test_add_and_lookup_groups() -> None:
    props = PDOptionalContentProperties()
    a = PDOptionalContentGroup("Layer A")
    b = PDOptionalContentGroup("Layer B")
    props.add_group(a)
    props.add_group(b)

    groups = props.get_groups()
    assert [g.get_name() for g in groups] == ["Layer A", "Layer B"]
    assert props.has_group("Layer A")
    assert props.has_group("Layer B")
    assert not props.has_group("Layer C")

    found = props.get_group("Layer B")
    assert found is not None
    assert found.get_cos_object() is b.get_cos_object()
    assert props.get_group("Layer C") is None

    # /Order array on default config must include both.
    d = props.get_cos_object().get_dictionary_object(COSName.D)  # type: ignore[attr-defined]
    assert isinstance(d, COSDictionary)
    order = d.get_dictionary_object(COSName.get_pdf_name("Order"))
    assert isinstance(order, COSArray)
    assert order.size() == 2


def test_is_group_enabled_and_set_group_enabled_toggle() -> None:
    props = PDOptionalContentProperties()
    a = PDOptionalContentGroup("Layer A")
    b = PDOptionalContentGroup("Layer B")
    props.add_group(a)
    props.add_group(b)

    # Default base state ON: groups are enabled until added to /OFF.
    assert props.is_group_enabled(a) is True
    assert props.is_group_enabled("Layer B") is True

    # Initial set_group_enabled returns False — group not in /ON or /OFF yet.
    assert props.set_group_enabled(a, False) is False
    assert props.is_group_enabled(a) is False
    assert props.is_group_enabled("Layer A") is False

    # Toggling back returns True (group was on /OFF).
    assert props.set_group_enabled(a, True) is True
    assert props.is_group_enabled(a) is True

    # Disable by name.
    assert props.set_group_enabled("Layer B", False) is False
    assert props.is_group_enabled("Layer B") is False


def test_base_state_round_trip() -> None:
    props = PDOptionalContentProperties()
    assert props.get_base_state() == "ON"

    props.set_base_state("OFF")
    assert props.get_base_state() == "OFF"

    props.set_base_state("Unchanged")
    assert props.get_base_state() == "Unchanged"

    props.set_base_state("ON")
    assert props.get_base_state() == "ON"

    with pytest.raises(ValueError):
        props.set_base_state("Maybe")


def test_get_configuration_names_reads_configs_array() -> None:
    props = PDOptionalContentProperties()
    assert props.get_configuration_names() == []

    cfg1 = COSDictionary()
    cfg1.set_string(COSName.get_pdf_name("Name"), "Alt 1")
    cfg2 = COSDictionary()
    cfg2.set_string(COSName.get_pdf_name("Name"), "Alt 2")
    props.get_cos_object().set_item(
        COSName.get_pdf_name("Configs"), COSArray([cfg1, cfg2])
    )
    assert props.get_configuration_names() == ["Alt 1", "Alt 2"]


def test_base_state_off_marks_groups_disabled_by_default() -> None:
    props = PDOptionalContentProperties()
    a = PDOptionalContentGroup("Layer A")
    props.add_group(a)
    props.set_base_state("OFF")
    assert props.is_group_enabled(a) is False

    # Explicit /ON entry overrides base state.
    props.set_group_enabled(a, True)
    assert props.is_group_enabled(a) is True
