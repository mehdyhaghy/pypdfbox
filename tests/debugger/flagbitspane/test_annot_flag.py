"""Tests for :class:`AnnotFlag`."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.debugger.flagbitspane.annot_flag import AnnotFlag

_F = COSName.get_pdf_name("F")


def _annot_dict(flag_value: int) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_F, COSInteger.get(flag_value))
    return d


def test_flag_type_is_annot_flag():
    assert AnnotFlag(_annot_dict(0)).get_flag_type() == "Annot flag"


def test_flag_value_string():
    assert AnnotFlag(_annot_dict(7)).get_flag_value() == "Flag value: 7"


def test_no_flags_set_all_false():
    rows = AnnotFlag(_annot_dict(0)).get_flag_bits()
    # 10 named annotation flags
    assert len(rows) == 10
    for _bit, _name, value in rows:
        assert value is False


def test_all_low_flags_set_true():
    # Bits 1..10 all set
    mask = (1 << 10) - 1
    rows = AnnotFlag(_annot_dict(mask)).get_flag_bits()
    for _bit, _name, value in rows:
        assert value is True


def test_bit_positions_match_upstream_order():
    rows = AnnotFlag(_annot_dict(0)).get_flag_bits()
    positions = [row[0] for row in rows]
    names = [row[1] for row in rows]
    assert positions == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert names == [
        "Invisible",
        "Hidden",
        "Print",
        "NoZoom",
        "NoRotate",
        "NoView",
        "ReadOnly",
        "Locked",
        "ToggleNoView",
        "LockedContents",
    ]


def test_only_print_bit_set():
    # /F bit 3 == Print
    rows = AnnotFlag(_annot_dict(1 << 2)).get_flag_bits()
    flags = {row[1]: row[2] for row in rows}
    assert flags["Print"] is True
    assert flags["Invisible"] is False
    assert flags["Hidden"] is False


def test_default_column_names():
    assert AnnotFlag(_annot_dict(0)).get_column_names() == [
        "Bit Position",
        "Name",
        "Set",
    ]
