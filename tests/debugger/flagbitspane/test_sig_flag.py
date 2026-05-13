"""Tests for :class:`SigFlag`."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.debugger.flagbitspane.sig_flag import SigFlag

_SIG_FLAGS = COSName.get_pdf_name("SigFlags")


def _acro_dict(value: int) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_SIG_FLAGS, COSInteger.get(value))
    return d


def test_flag_type():
    assert SigFlag(None, _acro_dict(0)).get_flag_type() == "Signature flag"


def test_flag_value_string():
    assert SigFlag(None, _acro_dict(3)).get_flag_value() == "Flag value: 3"


def test_neither_bit_set():
    rows = SigFlag(None, _acro_dict(0)).get_flag_bits()
    assert [r[0] for r in rows] == [1, 2]
    assert [r[1] for r in rows] == ["SignaturesExist", "AppendOnly"]
    assert [r[2] for r in rows] == [False, False]


def test_only_signatures_exist():
    rows = SigFlag(None, _acro_dict(1)).get_flag_bits()
    flags = {r[1]: r[2] for r in rows}
    assert flags["SignaturesExist"] is True
    assert flags["AppendOnly"] is False


def test_both_bits_set():
    rows = SigFlag(None, _acro_dict(3)).get_flag_bits()
    for _bit, _name, value in rows:
        assert value is True
