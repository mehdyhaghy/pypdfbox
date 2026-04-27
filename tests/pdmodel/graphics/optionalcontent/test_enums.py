from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    BaseState,
    MembershipDictionaryVisibilityPolicy,
    PDOptionalContentGroup,
    PDOptionalContentMembershipDictionary,
    PDOptionalContentProperties,
    RenderState,
)


# ---------- RenderState ----------


def test_render_state_values() -> None:
    assert RenderState.ON.value == "ON"
    assert RenderState.OFF.value == "OFF"


def test_render_state_value_of() -> None:
    assert RenderState.value_of("on") is RenderState.ON
    assert RenderState.value_of("OFF") is RenderState.OFF
    with pytest.raises(ValueError):
        RenderState.value_of("Unchanged")


def test_render_state_exposed_as_nested() -> None:
    # Mirrors upstream PDOptionalContentGroup.RenderState.ON
    assert PDOptionalContentGroup.RenderState is RenderState
    assert PDOptionalContentGroup.RenderState.ON is RenderState.ON


def test_render_state_round_trip_typed() -> None:
    group = PDOptionalContentGroup("L")
    assert group.get_render_state_enum("Print") is None
    group.set_render_state_enum(RenderState.OFF, "Print")
    assert group.get_render_state_enum("Print") is RenderState.OFF
    group.set_render_state_enum(RenderState.ON, "View")
    assert group.get_render_state_enum("View") is RenderState.ON


def test_render_state_typed_setter_rejects_non_enum() -> None:
    group = PDOptionalContentGroup("L")
    with pytest.raises(TypeError):
        group.set_render_state_enum("ON", "Print")  # type: ignore[arg-type]


# ---------- BaseState ----------


def test_base_state_values() -> None:
    assert BaseState.ON.value == "ON"
    assert BaseState.OFF.value == "OFF"
    assert BaseState.UNCHANGED.value == "Unchanged"


def test_base_state_pdf_name() -> None:
    assert BaseState.ON.get_pdf_name() == COSName.get_pdf_name("ON")
    assert BaseState.UNCHANGED.get_pdf_name() == COSName.get_pdf_name(
        "Unchanged"
    )


def test_base_state_value_of_case_insensitive() -> None:
    assert BaseState.value_of("ON") is BaseState.ON
    assert BaseState.value_of("off") is BaseState.OFF
    assert BaseState.value_of("Unchanged") is BaseState.UNCHANGED
    assert BaseState.value_of("UNCHANGED") is BaseState.UNCHANGED
    with pytest.raises(ValueError):
        BaseState.value_of("Bogus")


def test_base_state_exposed_as_nested() -> None:
    assert PDOptionalContentProperties.BaseState is BaseState


def test_base_state_round_trip_via_enum() -> None:
    props = PDOptionalContentProperties()
    # Default is "ON"
    assert props.get_base_state_enum() is BaseState.ON
    props.set_base_state(BaseState.OFF)
    assert props.get_base_state() == "OFF"
    assert props.get_base_state_enum() is BaseState.OFF
    props.set_base_state(BaseState.UNCHANGED)
    assert props.get_base_state() == "Unchanged"
    assert props.get_base_state_enum() is BaseState.UNCHANGED


def test_base_state_string_setter_still_works() -> None:
    props = PDOptionalContentProperties()
    props.set_base_state("OFF")
    assert props.get_base_state_enum() is BaseState.OFF


# ---------- MembershipDictionaryVisibilityPolicy ----------


def test_visibility_policy_values() -> None:
    assert MembershipDictionaryVisibilityPolicy.ALL_ON.value == "AllOn"
    assert MembershipDictionaryVisibilityPolicy.ANY_ON.value == "AnyOn"
    assert MembershipDictionaryVisibilityPolicy.ANY_OFF.value == "AnyOff"
    assert MembershipDictionaryVisibilityPolicy.ALL_OFF.value == "AllOff"


def test_visibility_policy_value_of() -> None:
    assert (
        MembershipDictionaryVisibilityPolicy.value_of("AnyOn")
        is MembershipDictionaryVisibilityPolicy.ANY_ON
    )
    assert (
        MembershipDictionaryVisibilityPolicy.value_of("AllOff")
        is MembershipDictionaryVisibilityPolicy.ALL_OFF
    )
    with pytest.raises(ValueError):
        MembershipDictionaryVisibilityPolicy.value_of("anyon")
    with pytest.raises(ValueError):
        MembershipDictionaryVisibilityPolicy.value_of("Bogus")


def test_visibility_policy_pdf_name() -> None:
    assert MembershipDictionaryVisibilityPolicy.ALL_ON.get_pdf_name() == (
        COSName.get_pdf_name("AllOn")
    )


def test_visibility_policy_exposed_as_nested() -> None:
    assert (
        PDOptionalContentMembershipDictionary.VisibilityPolicy
        is MembershipDictionaryVisibilityPolicy
    )


def test_visibility_policy_round_trip_via_enum() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    # Default per spec is "AnyOn"
    assert ocmd.get_visibility_policy() == "AnyOn"
    assert (
        ocmd.get_visibility_policy_enum()
        is MembershipDictionaryVisibilityPolicy.ANY_ON
    )
    ocmd.set_visibility_policy(
        MembershipDictionaryVisibilityPolicy.ALL_OFF
    )
    assert ocmd.get_visibility_policy() == "AllOff"
    assert (
        ocmd.get_visibility_policy_enum()
        is MembershipDictionaryVisibilityPolicy.ALL_OFF
    )


def test_visibility_policy_string_setter_still_works() -> None:
    ocmd = PDOptionalContentMembershipDictionary()
    ocmd.set_visibility_policy("AllOn")
    assert (
        ocmd.get_visibility_policy_enum()
        is MembershipDictionaryVisibilityPolicy.ALL_ON
    )
    with pytest.raises(ValueError):
        ocmd.set_visibility_policy("Bogus")
