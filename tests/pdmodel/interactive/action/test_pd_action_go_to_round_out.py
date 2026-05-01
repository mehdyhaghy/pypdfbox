"""Round-out tests for :class:`PDActionGoTo` covering the typed
``/D`` accessors (``get_destination`` / ``set_destination``).

These cover the explicit-array, ``COSString`` and ``COSName`` named-form,
and removal-via-``None`` paths in addition to the ``PDDestination``
typed setter.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.action import PDActionGoTo
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)

_D: COSName = COSName.D  # type: ignore[attr-defined]


def test_default_subtype_is_goto() -> None:
    action = PDActionGoTo()
    assert action.get_sub_type() == "GoTo"


def test_get_destination_returns_none_when_d_absent() -> None:
    action = PDActionGoTo()
    assert action.get_destination() is None


def test_set_destination_with_pd_destination_round_trip() -> None:
    """GoTo (local) destinations require a page-dictionary at index 0;
    ``set_page_number`` is for remote destinations only (PDF 32000-1
    §12.6.4.2)."""
    action = PDActionGoTo()
    dest = PDPageXYZDestination()
    page = COSDictionary()
    page.set_name(COSName.get_pdf_name("Type"), "Page")
    dest.set_page(page)
    action.set_destination(dest)

    resolved = action.get_destination()
    assert isinstance(resolved, PDDestination)
    assert isinstance(resolved, PDPageXYZDestination)
    assert resolved.get_page() is page


def test_set_destination_with_string_writes_named_destination() -> None:
    action = PDActionGoTo()
    action.set_destination("Chapter1")

    assert action.get_destination() == "Chapter1"
    raw = action.get_cos_object().get_dictionary_object(_D)
    assert isinstance(raw, COSString)


def test_set_destination_with_cos_array_round_trips_via_typed_getter() -> None:
    action = PDActionGoTo()
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("XYZ")])
    action.set_destination(arr)

    resolved = action.get_destination()
    assert isinstance(resolved, PDPageXYZDestination)


def test_set_destination_none_removes_d() -> None:
    action = PDActionGoTo()
    action.set_destination("Chapter1")
    assert action.get_cos_object().contains_key(_D)

    action.set_destination(None)
    assert not action.get_cos_object().contains_key(_D)
    assert action.get_destination() is None


def test_get_destination_dispatches_cos_name_to_str() -> None:
    """``/D`` written as a ``COSName`` is also returned as a plain ``str``."""
    action = PDActionGoTo()
    action.get_cos_object().set_item(_D, COSName.get_pdf_name("Outline1"))

    assert action.get_destination() == "Outline1"
