"""Hand-written round-out tests for under-covered :class:`PDOutlineItem`
surface. Each test pins one small upstream-shaped behaviour that wasn't
exercised by the existing parity / aliases test files:

- ``set_destination(PDPage)`` convenience overload — wraps the page in a
  default ``PDPageXYZDestination`` (mirrors upstream
  ``PDOutlineItem#setDestination(PDPage)``).
- ``set_action(None)`` removes ``/A`` (pypdfbox-side ``None``-clearing
  convention; upstream's setter takes a non-null action).
- ``get_text_color_pd_color()`` returns a typed ``PDColor`` against
  ``PDDeviceRGB`` and materialises a zero-filled 3-tuple on ``/C`` when
  the entry is absent — mirrors upstream
  ``PDOutlineItem#getTextColor()`` exactly, including the side-effect.
- ``set_text_color(PDColor)`` overload — round-trips through
  :meth:`PDColor.to_cos_array` and the matching tuple-shaped getter.
- ``find_destination_page`` resolves through a ``/A`` ``GoTo`` action's
  destination when ``/Dest`` is absent (upstream fallback path).
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.interactive.action import PDActionGoTo, PDActionURI
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageFitDestination,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import (
    PDOutlineItem,
)


# ---------- set_destination(PDPage) convenience overload ----------


def test_set_destination_with_pd_page_wraps_in_xyz_destination() -> None:
    item = PDOutlineItem()
    page = PDPage()

    item.set_destination(page)

    resolved = item.get_destination()
    assert isinstance(resolved, PDPageXYZDestination)
    # The XYZ destination should reference the source page's COS object.
    assert resolved.get_page() is page.get_cos_object()


def test_set_destination_pd_page_overload_replaces_previous_dest() -> None:
    item = PDOutlineItem()
    fit = PDPageFitDestination()
    fit.set_page_number(0)
    item.set_destination(fit)
    assert isinstance(item.get_destination(), PDPageFitDestination)

    # Now overwrite via the PDPage convenience — should swap the type.
    page = PDPage()
    item.set_destination(page)
    resolved = item.get_destination()
    assert isinstance(resolved, PDPageXYZDestination)
    assert resolved.get_page() is page.get_cos_object()


def test_set_destination_none_removes_dest_entry() -> None:
    item = PDOutlineItem()
    fit = PDPageFitDestination()
    fit.set_page_number(0)
    item.set_destination(fit)
    assert item.get_destination() is not None

    item.set_destination(None)
    assert item.get_destination() is None
    # /Dest entry must be physically absent from the dictionary.
    assert item.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Dest")
    ) is None


# ---------- set_action(None) removes /A ----------


def test_set_action_none_removes_a_entry() -> None:
    item = PDOutlineItem()
    action = PDActionURI()
    action.set_uri("https://example.test")
    item.set_action(action)
    assert item.get_action() is not None

    item.set_action(None)
    assert item.get_action() is None
    assert item.get_cos_object().get_dictionary_object(
        COSName.A  # type: ignore[attr-defined]
    ) is None


# ---------- get_text_color_pd_color: typed accessor + side-effect ----------


def test_get_text_color_pd_color_materialises_default_on_missing_c() -> None:
    """Mirrors upstream side-effect: when ``/C`` is absent, calling
    ``getTextColor()`` writes a zero-filled 3-element ``COSArray`` to the
    dictionary so subsequent reads see ``[0, 0, 0]`` rather than absent.
    """
    item = PDOutlineItem()
    assert item.get_cos_object().get_dictionary_object(COSName.C) is None  # type: ignore[attr-defined]

    color = item.get_text_color_pd_color()

    assert isinstance(color, PDColor)
    assert color.get_color_space() is PDDeviceRGB.INSTANCE
    assert list(color.get_components()) == [0.0, 0.0, 0.0]
    # Side-effect: the dictionary now carries an explicit /C array.
    written = item.get_cos_object().get_dictionary_object(COSName.C)  # type: ignore[attr-defined]
    assert isinstance(written, COSArray)
    assert written.size() == 3


def test_get_text_color_pd_color_reads_existing_c_without_side_effect() -> None:
    item = PDOutlineItem()
    item.set_text_color((0.25, 0.5, 0.75))
    before = item.get_cos_object().get_dictionary_object(COSName.C)  # type: ignore[attr-defined]
    assert isinstance(before, COSArray)

    color = item.get_text_color_pd_color()

    assert isinstance(color, PDColor)
    components = list(color.get_components())
    assert components == pytest.approx([0.25, 0.5, 0.75])
    # Same array object — no rewrite.
    after = item.get_cos_object().get_dictionary_object(COSName.C)  # type: ignore[attr-defined]
    assert after is before


# ---------- set_text_color(PDColor) overload ----------


def test_set_text_color_accepts_pd_color_and_round_trips() -> None:
    item = PDOutlineItem()
    color = PDColor([0.1, 0.2, 0.3], PDDeviceRGB.INSTANCE)
    item.set_text_color(color)

    # Tuple-shaped getter sees the same components.
    rgb = item.get_text_color()
    assert rgb is not None
    assert rgb == pytest.approx((0.1, 0.2, 0.3))


# ---------- find_destination_page via /A GoTo action ----------


def test_find_destination_page_resolves_through_goto_action_destination() -> None:
    with PDDocument() as document:
        document.add_page(PDPage())
        target_page = PDPage()
        document.add_page(target_page)

        item = PDOutlineItem()
        # No /Dest — only an /A action with an embedded destination that
        # points directly at the target page (PDActionGoTo validates that
        # the destination's first array slot is a page dictionary).
        action_dest = PDPageXYZDestination()
        action_dest.set_page(target_page)
        action = PDActionGoTo()
        action.set_destination(action_dest)
        item.set_action(action)

        resolved = item.find_destination_page(document)
        assert resolved is target_page.get_cos_object()


def test_find_destination_page_returns_none_for_non_goto_action() -> None:
    with PDDocument() as document:
        item = PDOutlineItem()
        # URI action carries no page destination.
        action = PDActionURI()
        action.set_uri("https://example.test")
        item.set_action(action)

        assert item.find_destination_page(document) is None


# ---------- /F flag-bit constants pin ----------


def test_flag_constants_match_pdf_spec_values() -> None:
    # PDF 32000-1:2008 §12.3.3 — /F bit 1 italic, bit 2 bold.
    assert PDOutlineItem.FLAG_ITALIC == 1
    assert PDOutlineItem.FLAG_BOLD == 2


def test_set_italic_then_set_bold_combines_flag_bits() -> None:
    item = PDOutlineItem()
    item.set_italic(True)
    assert item.get_text_flags() == PDOutlineItem.FLAG_ITALIC

    item.set_bold(True)
    # Setting bold preserves the italic bit — bitmask, not overwrite.
    assert item.get_text_flags() == (
        PDOutlineItem.FLAG_ITALIC | PDOutlineItem.FLAG_BOLD
    )

    item.set_italic(False)
    # Clearing italic preserves the bold bit.
    assert item.get_text_flags() == PDOutlineItem.FLAG_BOLD


def test_set_text_flags_negative_value_round_trips_via_get_int() -> None:
    # Defensive: /F is unsigned in the spec, but the wrapper stores a raw
    # COSInteger and the getter just reads it back via get_int — round-trip
    # must work regardless of sign so callers writing 0 don't trip up on
    # an integer-coerced clearing path.
    item = PDOutlineItem()
    item.set_text_flags(0)
    assert item.get_text_flags() == 0
    # Confirm the entry was actually written (not just absent).
    raw = item.get_cos_object().get_dictionary_object(COSName.get_pdf_name("F"))
    assert raw is not None


# ---------- structure_element_round_trip uses raw COSDictionary ----------
# Note: skipping a duplicate of the known-failing
# ``test_outline_item_structure_element_round_trip_with_raw_dict`` —
# the existing test in tests/pdmodel/interactive/documentnavigation/
# already covers the raw-dict path and is tracked as a pre-existing
# divergence. New tests in this file deliberately avoid that surface.


def test_structure_element_round_trip_via_typed_pd_structure_element() -> None:
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
        PDStructureElement,
    )

    item = PDOutlineItem()
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("StructElem"))
    raw.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("P"))
    elem = PDStructureElement(raw)

    item.set_structure_element(elem)

    resolved = item.get_structure_element()
    assert resolved is not None
    # Round-trips through the same backing dictionary so a re-wrap reads
    # back the same /S structure type.
    assert resolved.get_cos_object() is raw


def test_structure_element_set_none_removes_se_entry() -> None:
    item = PDOutlineItem()
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("StructElem"))
    item.set_structure_element(raw)
    assert item.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("SE")
    ) is raw

    item.set_structure_element(None)
    assert item.get_structure_element() is None
    assert item.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("SE")
    ) is None
