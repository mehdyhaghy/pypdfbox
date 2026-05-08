from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action import PDActionNamed

_N: COSName = COSName.get_pdf_name("N")
_S: COSName = COSName.get_pdf_name("S")


def test_named_has_and_clear_n_track_typed_name_entry() -> None:
    action = PDActionNamed()

    assert action.has_n() is False

    action.set_n(PDActionNamed.NAMED_ACTION_NEXT_PAGE)

    assert action.has_n() is True
    assert action.get_n() == PDActionNamed.NAMED_ACTION_NEXT_PAGE

    action.clear_n()

    assert action.has_n() is False
    assert action.get_n() is None
    assert not action.get_cos_object().contains_key(_N)


def test_named_malformed_n_is_not_reported_present_and_can_be_cleared() -> None:
    raw = COSDictionary()
    raw.set_name(_S, PDActionNamed.SUB_TYPE)
    raw.set_item(_N, COSString(PDActionNamed.NAMED_ACTION_NEXT_PAGE))
    action = PDActionNamed(raw)

    assert action.get_n() is None
    assert action.has_n() is False
    assert action.is_next_page() is False
    assert action.is_standard_named_action() is False

    action.clear_n()

    assert not raw.contains_key(_N)


def test_named_is_valid_reflects_subtype() -> None:
    assert PDActionNamed().is_valid() is True

    raw = COSDictionary()
    raw.set_name(_S, "JavaScript")
    action = PDActionNamed(raw)

    assert action.is_valid() is False
