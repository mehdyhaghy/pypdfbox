from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.action import PDActionRemoteGoTo
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDNamedDestination,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)

_D: COSName = COSName.D  # type: ignore[attr-defined]


def test_set_named_destination_round_trips() -> None:
    """``/D`` set as a string is readable back via ``get_named_destination``."""
    action = PDActionRemoteGoTo()
    action.set_named_destination("Chapter1")

    assert action.get_named_destination() == "Chapter1"


def test_get_named_destination_returns_none_for_array_d() -> None:
    """When ``/D`` is an explicit page-target array, ``get_named_destination``
    returns ``None`` rather than coercing the array to a string."""
    action = PDActionRemoteGoTo()
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("XYZ")])
    action.set_d(arr)

    assert action.get_named_destination() is None
    # Sanity: the raw array is still accessible via get_d.
    assert action.get_d() is arr


def test_set_named_destination_none_removes_d() -> None:
    """Setting the named destination to ``None`` removes ``/D`` entirely."""
    action = PDActionRemoteGoTo()
    action.set_named_destination("Chapter1")
    assert action.get_cos_object().contains_key(_D)

    action.set_named_destination(None)
    assert not action.get_cos_object().contains_key(_D)
    assert action.get_named_destination() is None


def test_get_destination_dispatches_array_to_pd_destination() -> None:
    """``/D`` as an explicit page-target array dispatches to a concrete
    ``PDDestination`` subclass via ``get_destination``."""
    action = PDActionRemoteGoTo()
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("XYZ")])
    action.set_d(arr)

    resolved = action.get_destination()
    assert isinstance(resolved, PDDestination)
    assert isinstance(resolved, PDPageXYZDestination)


def test_get_destination_dispatches_string_to_named_destination() -> None:
    """``/D`` as a ``COSString`` named destination dispatches to a
    ``PDNamedDestination`` (upstream parity via PDDestination.create)."""
    action = PDActionRemoteGoTo()
    action.set_d(COSString("Chapter1"))

    resolved = action.get_destination()
    assert isinstance(resolved, PDNamedDestination)
    assert resolved.get_named_destination() == "Chapter1"


def test_get_destination_dispatches_name_to_named_destination() -> None:
    """``/D`` as a ``COSName`` also dispatches to a ``PDNamedDestination``."""
    action = PDActionRemoteGoTo()
    action.set_d(COSName.get_pdf_name("Chapter1"))

    resolved = action.get_destination()
    assert isinstance(resolved, PDNamedDestination)
    assert resolved.get_named_destination() == "Chapter1"


def test_get_destination_returns_none_when_d_absent() -> None:
    """``/D`` absent yields ``None`` from the typed dispatch."""
    action = PDActionRemoteGoTo()
    assert action.get_destination() is None
