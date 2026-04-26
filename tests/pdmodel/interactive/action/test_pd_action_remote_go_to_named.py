from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName
from pypdfbox.pdmodel.interactive.action import PDActionRemoteGoTo

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
