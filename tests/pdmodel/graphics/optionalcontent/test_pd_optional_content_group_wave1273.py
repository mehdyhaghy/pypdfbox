"""Wave 1273 round-out: ``PDOptionalContentGroup.to_string()`` explicit method."""

from __future__ import annotations

from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)


def test_to_string_includes_name() -> None:
    ocg = PDOptionalContentGroup("ColorLayer")
    # Mirrors upstream ``PDOptionalContentGroup.toString()`` — the
    # property-list parent ``toString`` followed by ``" (<name>)"``.
    rendered = ocg.to_string()
    assert rendered.endswith(" (ColorLayer)")


def test_to_string_matches_str() -> None:
    ocg = PDOptionalContentGroup("MyLayer")
    assert ocg.to_string() == str(ocg)
