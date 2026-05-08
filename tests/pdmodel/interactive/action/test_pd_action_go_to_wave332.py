from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action import PDActionGoTo

_D: COSName = COSName.D  # type: ignore[attr-defined]
_S: COSName = COSName.get_pdf_name("S")


def test_goto_has_clear_and_is_empty_track_destination_presence() -> None:
    action = PDActionGoTo()

    assert action.has_destination() is False
    assert action.is_empty() is True

    action.set_destination("Chapter1")

    assert action.has_destination() is True
    assert action.is_empty() is False

    action.clear_destination()

    assert action.has_destination() is False
    assert action.is_empty() is True
    assert action.get_destination() is None
    assert not action.get_cos_object().contains_key(_D)


def test_goto_has_destination_reports_malformed_d_presence() -> None:
    raw = COSDictionary()
    raw.set_name(_S, PDActionGoTo.SUB_TYPE)
    raw.set_item(_D, COSDictionary())
    action = PDActionGoTo(raw)

    assert action.get_destination() is None
    assert action.has_destination() is True
    assert action.is_empty() is False

    action.clear_destination()

    assert action.has_destination() is False
    assert action.is_empty() is True


def test_goto_is_valid_reflects_subtype() -> None:
    assert PDActionGoTo().is_valid() is True

    raw = COSDictionary()
    raw.set_name(_S, "GoToR")
    action = PDActionGoTo(raw)

    assert action.is_valid() is False
