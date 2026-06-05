from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.action import PDActionGoTo
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDNamedDestination,
    PDPageDestination,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)

_D: COSName = COSName.D  # type: ignore[attr-defined]


def test_get_destination_returns_none_when_d_absent() -> None:
    """``/D`` absent yields ``None`` from the typed dispatch."""
    action = PDActionGoTo()
    assert action.get_destination() is None


def test_get_destination_dispatches_array_to_page_destination_subclass() -> None:
    """``/D`` as an explicit page-target ``COSArray`` dispatches to a
    concrete ``PDPageDestination`` subclass."""
    action = PDActionGoTo()
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("XYZ")])
    action.get_cos_object().set_item(_D, arr)

    resolved = action.get_destination()
    assert isinstance(resolved, PDDestination)
    assert isinstance(resolved, PDPageDestination)
    assert isinstance(resolved, PDPageXYZDestination)


def test_get_destination_dispatches_string_to_named_destination() -> None:
    """``/D`` as a ``COSString`` dispatches to a ``PDNamedDestination``
    (upstream parity — PDDestination.create wraps the string form)."""
    action = PDActionGoTo()
    action.get_cos_object().set_item(_D, COSString("Chapter1"))

    resolved = action.get_destination()
    assert isinstance(resolved, PDNamedDestination)
    assert resolved.get_named_destination() == "Chapter1"


def test_get_destination_dispatches_name_to_named_destination() -> None:
    """``/D`` as a ``COSName`` (also a valid named-destination form)
    dispatches to a ``PDNamedDestination``."""
    action = PDActionGoTo()
    action.get_cos_object().set_item(_D, COSName.get_pdf_name("Chapter2"))

    resolved = action.get_destination()
    assert isinstance(resolved, PDNamedDestination)
    assert resolved.get_named_destination() == "Chapter2"


def test_set_destination_pd_page_destination_round_trips() -> None:
    """A typed ``PDPageDestination`` round-trips through ``/D``.

    Note: GoTo requires a page-dictionary target (PDF 32000-1 §12.6.4.2);
    ``set_page_number`` is reserved for remote-destination arrays."""
    action = PDActionGoTo()
    dest = PDPageXYZDestination()
    page = COSDictionary()
    page.set_name(COSName.get_pdf_name("Type"), "Page")
    dest.set_page(page)
    action.set_destination(dest)

    resolved = action.get_destination()
    assert isinstance(resolved, PDPageXYZDestination)
    assert resolved.get_page() is page


def test_set_destination_named_string_round_trips() -> None:
    """A ``str`` argument writes a named destination as ``COSString`` and
    is read back via ``get_destination`` as the same string."""
    action = PDActionGoTo()
    action.set_destination("named-dest")

    raw = action.get_cos_object().get_dictionary_object(_D)
    assert isinstance(raw, COSString)
    assert raw.get_string() == "named-dest"
    resolved = action.get_destination()
    assert isinstance(resolved, PDNamedDestination)
    assert resolved.get_named_destination() == "named-dest"


def test_set_destination_none_clears_d() -> None:
    """Passing ``None`` removes ``/D`` entirely."""
    action = PDActionGoTo()
    action.set_destination("named-dest")
    assert action.get_cos_object().contains_key(_D)

    action.set_destination(None)
    assert not action.get_cos_object().contains_key(_D)
    assert action.get_destination() is None
