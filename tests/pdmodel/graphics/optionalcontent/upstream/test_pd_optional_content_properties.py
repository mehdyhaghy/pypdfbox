"""Ported from upstream Apache PDFBox 3.0.x:
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/optionalcontent/PDOptionalContentPropertiesTest.java``.

Translation rules per the project's "Test Porting Conventions".
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
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


# Mirrors upstream private getOCGs() — see
# PDOptionalContentProperties.java line 120.
def test_get_oc_gs_returns_underlying_array_and_seeds_when_missing() -> None:
    props = PDOptionalContentProperties()
    ocgs = props.get_oc_gs()
    assert isinstance(ocgs, COSArray)
    # Same identity on subsequent calls — no rebuild.
    assert props.get_oc_gs() is ocgs
    # Seeded into /OCProperties when previously absent.
    raw = COSDictionary()
    bare = PDOptionalContentProperties(raw)
    seeded = bare.get_oc_gs()
    assert isinstance(seeded, COSArray)
    assert raw.get_dictionary_object(COSName.get_pdf_name("OCGs")) is seeded


# Mirrors upstream private getD() — see
# PDOptionalContentProperties.java line 136.
def test_get_d_returns_default_configuration_dict() -> None:
    props = PDOptionalContentProperties()
    d = props.get_d()
    assert isinstance(d, COSDictionary)
    assert d.get_string(COSName.get_pdf_name("Name")) == "Top"
    # Seeded into a bare /OCProperties wrapper.
    raw = COSDictionary()
    bare = PDOptionalContentProperties(raw)
    seeded = bare.get_d()
    assert isinstance(seeded, COSDictionary)
    assert raw.get_dictionary_object(COSName.D) is seeded
    assert seeded.get_string(COSName.get_pdf_name("Name")) == "Top"


# Mirrors upstream private toDictionary(COSBase) — see
# PDOptionalContentProperties.java line 358.
def test_to_dictionary_unwraps_and_filters() -> None:
    inner = COSDictionary()
    # Direct dictionary input round-trips.
    assert PDOptionalContentProperties.to_dictionary(inner) is inner
    # Non-dictionary input → None.
    assert PDOptionalContentProperties.to_dictionary(COSArray()) is None
    assert PDOptionalContentProperties.to_dictionary(None) is None


@pytest.mark.parametrize(
    "method_name",
    ["get_oc_gs", "get_d", "to_dictionary"],
)
def test_upstream_private_helpers_exposed(method_name: str) -> None:
    """Upstream PDOptionalContentProperties has package-private helpers
    ``getOCGs``, ``getD``, ``toDictionary``. pypdfbox exposes them with the
    snake-cased upstream spellings for porting parity."""
    assert hasattr(PDOptionalContentProperties, method_name)
