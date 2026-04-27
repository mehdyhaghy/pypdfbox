"""Ported from upstream Apache PDFBox 3.0.x:
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/optionalcontent/PDOptionalContentPropertiesTest.java``.

Translation rules per CLAUDE.md §"Test Porting Conventions".
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.optionalcontent import (
    BaseState,
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)


# Java: testCreateNewProperties
def test_create_new_properties() -> None:
    props = PDOptionalContentProperties()
    assert props.get_groups() == []
    assert props.get_base_state() == "ON"


# Java: testAddGroup
def test_add_group() -> None:
    props = PDOptionalContentProperties()
    props.add_group(PDOptionalContentGroup("Layer 1"))
    props.add_group(PDOptionalContentGroup("Layer 2"))
    assert [g.get_name() for g in props.get_groups()] == [
        "Layer 1",
        "Layer 2",
    ]
    assert props.has_group("Layer 1")
    assert not props.has_group("Layer X")


# Java: testGroupNames
def test_group_names() -> None:
    props = PDOptionalContentProperties()
    props.add_group(PDOptionalContentGroup("A"))
    props.add_group(PDOptionalContentGroup("B"))
    assert props.get_group_names() == ["A", "B"]


# Java: testEnableGroup
def test_enable_group() -> None:
    props = PDOptionalContentProperties()
    props.add_group(PDOptionalContentGroup("L"))
    assert props.is_group_enabled("L")
    props.set_group_enabled("L", False)
    assert not props.is_group_enabled("L")
    props.set_group_enabled("L", True)
    assert props.is_group_enabled("L")


# Java: testBaseState
def test_base_state_round_trip() -> None:
    props = PDOptionalContentProperties()
    props.set_base_state("OFF")
    assert props.get_base_state() == "OFF"
    props.set_base_state("Unchanged")
    assert props.get_base_state() == "Unchanged"
    with pytest.raises(ValueError):
        props.set_base_state("Bogus")


# Java: testBaseStateEnum
def test_base_state_enum() -> None:
    props = PDOptionalContentProperties()
    props.set_base_state(BaseState.UNCHANGED)
    assert props.get_base_state_enum() is BaseState.UNCHANGED


# Java: testRemoveGroup
def test_remove_group() -> None:
    props = PDOptionalContentProperties()
    props.add_group(PDOptionalContentGroup("Keep"))
    props.add_group(PDOptionalContentGroup("Drop"))
    assert props.remove_group("Drop") is True
    assert [g.get_name() for g in props.get_groups()] == ["Keep"]
    assert props.remove_group("Missing") is False
