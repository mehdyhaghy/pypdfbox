"""Wave 1275 — PDSoftMask.get_sub_type alias."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask


def _make(subtype: str | None) -> PDSoftMask:
    d = COSDictionary()
    if subtype is not None:
        d.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name(subtype))
    return PDSoftMask(d)


def test_get_sub_type_alpha() -> None:
    sm = _make("Alpha")
    result = sm.get_sub_type()
    assert isinstance(result, COSName)
    assert result.name == "Alpha"


def test_get_sub_type_luminosity() -> None:
    sm = _make("Luminosity")
    result = sm.get_sub_type()
    assert result is not None
    assert result.name == "Luminosity"


def test_get_sub_type_returns_none_when_absent() -> None:
    sm = _make(None)
    assert sm.get_sub_type() is None


def test_get_sub_type_matches_get_subtype() -> None:
    sm = _make("Alpha")
    assert sm.get_sub_type() == sm.get_subtype()
