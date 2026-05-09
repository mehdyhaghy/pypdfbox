from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSObject
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentConfiguration,
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    RenderState,
)
from pypdfbox.rendering.render_destination import RenderDestination


def test_wave678_group_constructor_and_intent_validation_edges() -> None:
    with pytest.raises(TypeError):
        PDOptionalContentGroup(123)  # type: ignore[arg-type]

    group = PDOptionalContentGroup("Layer")
    intent = COSName.get_pdf_name("Intent")
    group.get_cos_object().set_item(intent, COSDictionary())

    assert group.get_intents() == []
    assert group.get_intent() == "View"

    with pytest.raises(TypeError):
        group.set_intents([COSName.get_pdf_name("View"), "Design"])  # type: ignore[list-item]
    with pytest.raises(TypeError):
        group.set_intent(["View", COSName.get_pdf_name("Design")])  # type: ignore[list-item]
    with pytest.raises(TypeError):
        group.set_intent(COSName.get_pdf_name("View"))  # type: ignore[arg-type]


def test_wave678_group_render_state_missing_and_typed_paths() -> None:
    group = PDOptionalContentGroup("Layer")
    usage = COSDictionary()
    print_usage = COSDictionary()
    print_usage.set_item(COSName.get_pdf_name("PrintState"), COSDictionary())
    usage.set_item(COSName.get_pdf_name("Print"), print_usage)
    group.get_cos_object().set_item(COSName.get_pdf_name("Usage"), usage)

    assert group.get_render_state(RenderDestination.PRINT) is None
    assert group.get_render_state_enum(RenderDestination.PRINT) is None

    group.set_render_state_enum(RenderState.OFF, RenderDestination.VIEW)
    assert group.get_render_state(RenderDestination.VIEW) == "OFF"
    assert group.get_render_state_enum(RenderDestination.VIEW) is RenderState.OFF

    with pytest.raises(ValueError):
        group.set_render_state("MAYBE")
    with pytest.raises(TypeError):
        group.set_render_state_enum("OFF")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        group.get_render_state(object())


def test_wave678_group_usage_accessors_prune_empty_usage_dicts() -> None:
    group = PDOptionalContentGroup("Layer")
    assert group.get_usage_dict() is None
    assert group.get_usage() is None

    usage = group.get_or_create_usage()
    assert usage.get_cos_object() is group.get_usage_dict()

    group.set_usage_view_state("ON")
    group.set_usage_print_state("OFF")
    group.set_usage_export_state("ON")
    assert group.get_usage_view_state() == "ON"
    assert group.get_usage_print_state() == "OFF"
    assert group.get_usage_export_state() == "ON"

    group.set_usage_creator("tool")
    group.set_usage_language("en-US")
    assert group.get_usage_creator() == "tool"
    assert group.get_usage_language() == "en-US"

    with pytest.raises(ValueError):
        group.set_usage_view_state("MAYBE")

    group.set_usage_view_state(None)
    group.set_usage_print_state(None)
    group.set_usage_export_state(None)
    group.set_usage_creator(None)
    group.set_usage_language(None)
    assert group.get_usage_dict() is None


def test_wave678_configuration_base_state_and_intent_malformed_defaults() -> None:
    cfg = PDOptionalContentConfiguration()
    cfg.get_cos_object().set_item(COSName.get_pdf_name("BaseState"), COSDictionary())
    cfg.get_cos_object().set_item(COSName.get_pdf_name("Intent"), COSDictionary())

    assert cfg.get_base_state() == "ON"
    assert cfg.get_intents() == []
    assert cfg.get_intent() == "View"
    assert cfg.is_intent("View") is False

    cfg.set_base_state(PDOptionalContentProperties.BaseState.UNCHANGED)
    assert cfg.get_base_state() == "Unchanged"
    assert (
        cfg.get_base_state_enum()
        is PDOptionalContentProperties.BaseState.UNCHANGED
    )
    cfg.set_base_state(COSName.get_pdf_name("OFF"))
    assert cfg.get_base_state() == "OFF"
    with pytest.raises(TypeError):
        cfg.set_base_state(None)


def test_wave678_configuration_wraps_indirect_ocgs_and_skips_bad_entries() -> None:
    cfg = PDOptionalContentConfiguration()
    good = PDOptionalContentGroup("Good")

    bad_type = COSDictionary()
    bad_type.set_item(COSName.TYPE, COSName.get_pdf_name("Catalog"))  # type: ignore[attr-defined]

    on = COSArray()
    on.add(COSName.get_pdf_name("NotADictionary"))
    on.add(COSObject(1, resolved=bad_type))
    on.add(COSObject(2, resolved=good.get_cos_object()))
    cfg.get_cos_object().set_item(COSName.get_pdf_name("ON"), on)

    assert [group.get_name() for group in cfg.get_on()] == ["Good"]
    assert cfg.is_on(good) is True
    assert cfg.remove_on(good) is True
    assert cfg.get_on() == []


def test_wave678_configuration_on_off_bulk_and_remove_paths() -> None:
    cfg = PDOptionalContentConfiguration()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")

    cfg.set_on([a, b])
    cfg.set_off([b])
    assert [group.get_name() for group in cfg.get_on()] == ["A", "B"]
    assert [group.get_name() for group in cfg.get_off()] == ["B"]

    assert cfg.remove_on(a) is True
    assert cfg.remove_on(PDOptionalContentGroup("Missing")) is False
    assert cfg.remove_off(b) is True
    assert cfg.remove_off(b) is False

    cfg.set_on(None)
    cfg.set_off(None)
    assert cfg.get_on() == []
    assert cfg.get_off() == []

    with pytest.raises(TypeError):
        cfg.set_on([a, "bad"])  # type: ignore[list-item]
    with pytest.raises(TypeError):
        cfg.set_off(["bad"])  # type: ignore[list-item]


def test_wave678_configuration_rbgroups_ignore_non_array_entries() -> None:
    cfg = PDOptionalContentConfiguration()
    a = PDOptionalContentGroup("A")
    groups = COSArray()
    groups.add(COSName.get_pdf_name("NotAnArray"))
    groups.add(COSArray([COSObject(3, resolved=a.get_cos_object())]))
    cfg.get_cos_object().set_item(COSName.get_pdf_name("RBGroups"), groups)

    assert [[group.get_name() for group in row] for row in cfg.get_rbgroups()] == [
        ["A"]
    ]
    assert cfg.remove_rbgroup(PDOptionalContentGroup("Missing")) is False
    assert cfg.remove_rbgroup(a) is True
