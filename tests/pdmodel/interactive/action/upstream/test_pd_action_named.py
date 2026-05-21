"""Upstream-parity port for ``PDActionNamed``.

Mirrors ``PDActionNamed.java`` (PDFBox 3.0.x). Upstream ships no JUnit
test for the named-action wrapper — this module ports the source's
behavioural contract: SUB_TYPE stamp, /N name accessor pair, /N missing
returns null.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_named import PDActionNamed

_S = COSName.get_pdf_name("S")
_N = COSName.get_pdf_name("N")


def test_default_constructor_stamps_subtype():
    action = PDActionNamed()
    assert action.get_sub_type() == "Named"
    assert action.get_cos_object().get_name(_S) == "Named"


def test_cos_dictionary_constructor_preserves_payload():
    d = COSDictionary()
    d.set_name(_S, "Named")
    d.set_name(_N, "NextPage")
    action = PDActionNamed(d)
    assert action.get_n() == "NextPage"


def test_get_n_returns_none_when_missing():
    action = PDActionNamed()
    assert action.get_n() is None


def test_set_n_writes_cos_name():
    action = PDActionNamed()
    action.set_n("PrevPage")
    assert action.get_n() == "PrevPage"
    assert action.get_cos_object().get_name(_N) == "PrevPage"


def test_set_n_round_trip_with_known_pdf_names():
    # PDF 32000-1 §12.6.4.11 Table 199 — built-in named actions.
    action = PDActionNamed()
    for name in ("NextPage", "PrevPage", "FirstPage", "LastPage"):
        action.set_n(name)
        assert action.get_n() == name


def test_sub_type_constant_equals_named():
    assert PDActionNamed.SUB_TYPE == "Named"
