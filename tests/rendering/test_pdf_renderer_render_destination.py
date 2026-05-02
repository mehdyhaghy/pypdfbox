"""Tests for the ``RenderDestination`` enum and its interaction with
``PDFRenderer.set_default_destination`` / ``get_default_destination``.

Mirrors upstream ``org.apache.pdfbox.rendering.RenderDestination`` and
the ``PDFRenderer.setDefaultDestination(RenderDestination)`` setter.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer, RenderDestination


def _make_doc() -> PDDocument:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    doc.add_page(PDPage(PDRectangle(0.0, 0.0, 50.0, 50.0)))
    return doc


# ---------------------------------------------------------------------------
# enum surface
# ---------------------------------------------------------------------------


def test_render_destination_has_three_values_matching_upstream() -> None:
    names = {member.name for member in RenderDestination}
    assert names == {"EXPORT", "VIEW", "PRINT"}


@pytest.mark.parametrize(
    ("member", "expected_value"),
    [
        (RenderDestination.EXPORT, "Export"),
        (RenderDestination.VIEW, "View"),
        (RenderDestination.PRINT, "Print"),
    ],
)
def test_render_destination_value_round_trips_string(
    member: RenderDestination, expected_value: str
) -> None:
    assert member.value == expected_value


# ---------------------------------------------------------------------------
# PDFRenderer.set_default_destination accepts the enum
# ---------------------------------------------------------------------------


def test_set_default_destination_accepts_enum_value() -> None:
    renderer = PDFRenderer(_make_doc())
    renderer.set_default_destination(RenderDestination.PRINT)
    # Stored as the string equivalent so existing string-based getters
    # keep working without behaviour change.
    assert renderer.get_default_destination() == "Print"


def test_set_default_destination_accepts_string_for_backward_compat() -> None:
    renderer = PDFRenderer(_make_doc())
    renderer.set_default_destination("Export")
    assert renderer.get_default_destination() == "Export"


def test_set_default_destination_round_trip_for_all_enum_members() -> None:
    renderer = PDFRenderer(_make_doc())
    for member in RenderDestination:
        renderer.set_default_destination(member)
        assert renderer.get_default_destination() == member.value
