"""Upstream-equivalent parity tests for
``pypdfbox.rendering.RenderDestination``.

Upstream PDFBox does not ship a dedicated JUnit file for
``RenderDestination`` — the enum is tiny (three members, no methods) and
upstream tests it transitively through ``PDFRenderer``. We pin the
member set + value mapping explicitly here so a future upstream re-sync
that adds or renames a member surfaces immediately, and so the snake_case
accessors on ``PDFRenderer`` that consume the enum stay parity-checked.

Source: ``pdfbox/src/main/java/org/apache/pdfbox/rendering/RenderDestination.java``
(PDFBox 3.0.x).
"""
from __future__ import annotations

import pytest

from pypdfbox.rendering import PDFRenderer, RenderDestination


def test_enum_has_exactly_three_members_named_export_view_print() -> None:
    """Upstream RenderDestination.java declares exactly three enum
    constants: EXPORT, VIEW, PRINT. Pin the membership so a re-sync
    that adds a new render purpose triggers a test failure.
    """
    names = [member.name for member in RenderDestination]
    assert names == ["EXPORT", "VIEW", "PRINT"]


def test_member_count_matches_upstream() -> None:
    assert len(list(RenderDestination)) == 3


@pytest.mark.parametrize(
    "member, name",
    [
        (RenderDestination.EXPORT, "EXPORT"),
        (RenderDestination.VIEW, "VIEW"),
        (RenderDestination.PRINT, "PRINT"),
    ],
)
def test_member_name_round_trips_via_index(
    member: RenderDestination, name: str
) -> None:
    """``RenderDestination[name]`` returns the same instance — mirrors
    Java's ``RenderDestination.valueOf(name)``.
    """
    assert RenderDestination[name] is member


def test_members_are_distinct_singletons() -> None:
    """Identity comparisons against ``is`` (Java enum ``==`` semantics)."""
    a, b, c = RenderDestination.EXPORT, RenderDestination.VIEW, RenderDestination.PRINT
    assert a is not b
    assert b is not c
    assert a is not c


def test_value_is_capitalised_label() -> None:
    """pypdfbox-only divergence: the enum carries a capitalised string
    value (``"Export"`` / ``"View"`` / ``"Print"``) matching the PDF
    spec's optional-content "intent" array convention. Java relies on
    ``name()`` returning the upper-case form. Pin the value so any
    drift between snake_case helper APIs and the wire form gets caught.
    """
    assert RenderDestination.EXPORT.value == "Export"
    assert RenderDestination.VIEW.value == "View"
    assert RenderDestination.PRINT.value == "Print"


def test_pdfrenderer_default_destination_defaults_to_view() -> None:
    """Upstream ``PDFRenderer`` ctor sets defaultDestination = VIEW.
    Pin so the default doesn't silently slip to EXPORT.

    Divergence note: pypdfbox stores the default destination as the
    enum's string value (``"View"``) rather than the enum member itself.
    The getter returns the same string. Either form must round-trip back
    through ``RenderDestination(...)``.
    """
    from pypdfbox.pdmodel import PDDocument

    document = PDDocument()
    renderer = PDFRenderer(document)
    try:
        value = renderer.get_default_destination()
        assert RenderDestination(value) is RenderDestination.VIEW
    finally:
        document.close()


@pytest.mark.parametrize(
    "destination", list(RenderDestination), ids=[m.name for m in RenderDestination]
)
def test_pdfrenderer_set_default_destination_round_trip_for_each_member(
    destination: RenderDestination,
) -> None:
    """Upstream ``setDefaultDestination(RenderDestination)`` mutator
    round-trips through the getter for every enum member.

    Divergence note: pypdfbox's getter returns the *string* value (the
    enum's ``.value``), not the enum member. We compare via
    ``RenderDestination(...)`` so the contract stays parity-checked
    regardless of internal storage choice.
    """
    from pypdfbox.pdmodel import PDDocument

    document = PDDocument()
    renderer = PDFRenderer(document)
    try:
        renderer.set_default_destination(destination)
        value = renderer.get_default_destination()
        assert RenderDestination(value) is destination
    finally:
        document.close()


def test_pdfrenderer_set_default_destination_accepts_bare_string_value() -> None:
    """pypdfbox-only convenience: pass the capitalised string label
    (``"Print"``) directly without wrapping it in the enum.

    Mirrors the Python-friendliness divergence documented in
    ``set_default_destination``'s docstring.
    """
    from pypdfbox.pdmodel import PDDocument

    document = PDDocument()
    renderer = PDFRenderer(document)
    try:
        renderer.set_default_destination("Print")
        value = renderer.get_default_destination()
        assert RenderDestination(value) is RenderDestination.PRINT
    finally:
        document.close()
