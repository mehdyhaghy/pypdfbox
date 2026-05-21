"""Upstream-parity port for ``PDActionHide``.

Mirrors ``PDActionHide.java`` (PDFBox 3.0.x). Upstream ships no JUnit
test for the hide action wrapper — this module ports the source's
behavioural contract: SUB_TYPE stamp, /T target accessor (dict / string /
array), /H hide-flag accessor with documented default ``true``.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action.pd_action_hide import PDActionHide

_S = COSName.get_pdf_name("S")
_T = COSName.get_pdf_name("T")
_H = COSName.get_pdf_name("H")


def test_default_constructor_stamps_subtype():
    action = PDActionHide()
    assert action.get_sub_type() == "Hide"
    assert action.get_cos_object().get_name(_S) == "Hide"


def test_default_h_is_true_per_spec():
    # Upstream: ``action.getBoolean(COSName.H, true)`` — hide-by-default.
    action = PDActionHide()
    assert action.get_h() is True


def test_set_h_round_trip():
    action = PDActionHide()
    action.set_h(False)
    assert action.get_h() is False
    action.set_h(True)
    assert action.get_h() is True


def test_get_t_returns_none_when_missing():
    action = PDActionHide()
    assert action.get_t() is None


def test_set_t_accepts_cos_string():
    # Per upstream: ``setT(COSBase t)`` — a /T may be a field name string.
    action = PDActionHide()
    action.set_t(COSString("FieldName"))
    payload = action.get_t()
    assert isinstance(payload, COSString)
    assert payload.get_string() == "FieldName"


def test_set_t_accepts_cos_array():
    # /T may also be an array of annotation refs / field names.
    action = PDActionHide()
    arr = COSArray([COSString("Field1"), COSString("Field2")])
    action.set_t(arr)
    payload = action.get_t()
    assert isinstance(payload, COSArray)
    assert payload.size() == 2


def test_set_t_accepts_cos_dictionary():
    # /T may also be a single annotation dictionary reference.
    action = PDActionHide()
    annot = COSDictionary()
    annot.set_name(COSName.get_pdf_name("Type"), "Annot")
    action.set_t(annot)
    payload = action.get_t()
    assert isinstance(payload, COSDictionary)


def test_sub_type_constant_equals_hide():
    assert PDActionHide.SUB_TYPE == "Hide"
