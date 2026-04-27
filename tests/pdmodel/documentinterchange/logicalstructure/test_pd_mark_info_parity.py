from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_mark_info import (
    PDMarkInfo,
)

_MARKED = COSName.get_pdf_name("Marked")
_USER_PROPERTIES = COSName.get_pdf_name("UserProperties")
_SUSPECTS = COSName.get_pdf_name("Suspects")


# ---------- /Marked ----------


def test_is_marked_default_false() -> None:
    mi = PDMarkInfo()
    assert mi.is_marked() is False


def test_is_marked_default_false_existing_dict() -> None:
    mi = PDMarkInfo(COSDictionary())
    assert mi.is_marked() is False


def test_set_marked_true_round_trip() -> None:
    mi = PDMarkInfo()
    mi.set_marked(True)
    assert mi.is_marked() is True
    assert mi.get_cos_object().get_boolean(_MARKED, False) is True


def test_set_marked_false_round_trip() -> None:
    mi = PDMarkInfo()
    mi.set_marked(True)
    mi.set_marked(False)
    assert mi.is_marked() is False
    assert mi.get_cos_object().get_boolean(_MARKED, True) is False


# ---------- /UserProperties ----------


def test_is_user_properties_default_false() -> None:
    mi = PDMarkInfo()
    assert mi.is_user_properties() is False


def test_uses_user_properties_default_false_upstream_alias() -> None:
    mi = PDMarkInfo()
    assert mi.uses_user_properties() is False


def test_set_user_properties_true_round_trip() -> None:
    mi = PDMarkInfo()
    mi.set_user_properties(True)
    assert mi.is_user_properties() is True
    assert mi.uses_user_properties() is True
    assert mi.get_cos_object().get_boolean(_USER_PROPERTIES, False) is True


def test_set_user_properties_false_round_trip() -> None:
    mi = PDMarkInfo()
    mi.set_user_properties(True)
    mi.set_user_properties(False)
    assert mi.is_user_properties() is False
    assert mi.uses_user_properties() is False


# ---------- /Suspects ----------


def test_is_suspect_default_false() -> None:
    mi = PDMarkInfo()
    assert mi.is_suspect() is False
    assert mi.is_suspects() is False


def test_set_suspect_true_round_trip_fixes_upstream_bug() -> None:
    # Upstream PDFBox 3.0.x setSuspect() always writes ``false`` regardless
    # of the argument; pypdfbox writes the actual value. This test asserts
    # the fix.
    mi = PDMarkInfo()
    mi.set_suspect(True)
    assert mi.is_suspect() is True
    assert mi.is_suspects() is True
    assert mi.get_cos_object().get_boolean(_SUSPECTS, False) is True


def test_set_suspect_false_round_trip() -> None:
    mi = PDMarkInfo()
    mi.set_suspect(True)
    mi.set_suspect(False)
    assert mi.is_suspect() is False
    assert mi.is_suspects() is False
    assert mi.get_cos_object().get_boolean(_SUSPECTS, True) is False


def test_set_suspects_true_round_trip() -> None:
    mi = PDMarkInfo()
    mi.set_suspects(True)
    assert mi.is_suspect() is True
    assert mi.is_suspects() is True


# ---------- get_cos_object identity ----------


def test_get_cos_object_returns_wrapped_dict() -> None:
    backing = COSDictionary()
    mi = PDMarkInfo(backing)
    assert mi.get_cos_object() is backing


def test_get_cos_object_default_constructor_creates_dict() -> None:
    mi = PDMarkInfo()
    assert isinstance(mi.get_cos_object(), COSDictionary)
