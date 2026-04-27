from __future__ import annotations

from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)


def test_get_name_returns_constructor_supplied_name() -> None:
    group = PDOptionalContentGroup("Layer A")
    assert group.get_name() == "Layer A"


def test_set_name_round_trip() -> None:
    group = PDOptionalContentGroup("Layer A")
    group.set_name("Layer B")
    assert group.get_name() == "Layer B"


def test_get_intent_default_is_view() -> None:
    group = PDOptionalContentGroup("Layer")
    assert group.get_intent() == "View"


def test_set_intent_design_round_trip() -> None:
    group = PDOptionalContentGroup("Layer")
    group.set_intent("Design")
    assert group.get_intent() == "Design"


def test_set_intent_list_round_trip() -> None:
    group = PDOptionalContentGroup("Layer")
    group.set_intent(["View", "Design"])
    assert group.get_intent() == ["View", "Design"]
