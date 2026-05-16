"""Hand-written tests for the public flag-bit accessors on :class:`FieldFlag`.

Covers the four ``get_*_flag_bits`` methods and the ``is_flag_bit_set`` helper.
Row counts and labels are checked against upstream
``FieldFlag.java`` (PDFBox 3.0.x).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.debugger.flagbitspane.field_flag import FieldFlag


@pytest.fixture()
def ff() -> FieldFlag:
    return FieldFlag(COSDictionary())


# ---- row counts (verified against upstream Java) ---------------------------

def test_button_field_flag_bits_row_count(ff: FieldFlag) -> None:
    # Upstream: 7 rows (1, 2, 3, 15, 16, 17, 26)
    assert len(ff.get_button_field_flag_bits(0)) == 7


def test_text_field_flag_bits_row_count(ff: FieldFlag) -> None:
    # Upstream: 10 rows
    assert len(ff.get_text_field_flag_bits(0)) == 10


def test_choice_field_flag_bits_row_count(ff: FieldFlag) -> None:
    # Upstream: 9 rows
    assert len(ff.get_choice_field_flag_bits(0)) == 9


def test_field_flag_bits_row_count(ff: FieldFlag) -> None:
    # Upstream: 3 common rows (ReadOnly / Required / NoExport)
    assert len(ff.get_field_flag_bits(0)) == 3


# ---- label spot-checks (verified against upstream Java) --------------------

def test_button_field_pushbutton_label(ff: FieldFlag) -> None:
    rows = ff.get_button_field_flag_bits(0)
    # row index 5 is bit 17 — upstream label "Pushbutton"
    assert rows[5][0] == 17
    assert rows[5][1] == "Pushbutton"


def test_text_field_multiline_label(ff: FieldFlag) -> None:
    rows = ff.get_text_field_flag_bits(0)
    # row index 3 is bit 13 — upstream label "Multiline"
    assert rows[3][0] == 13
    assert rows[3][1] == "Multiline"


def test_choice_field_combo_label(ff: FieldFlag) -> None:
    rows = ff.get_choice_field_flag_bits(0)
    # row index 3 is bit 18 — upstream label "Combo"
    assert rows[3][0] == 18
    assert rows[3][1] == "Combo"


def test_field_flag_readonly_label(ff: FieldFlag) -> None:
    rows = ff.get_field_flag_bits(0)
    assert rows[0][0] == 1
    assert rows[0][1] == "ReadOnly"


# ---- is_flag_bit_set semantics ---------------------------------------------

def test_is_flag_bit_set_round_trip_low_bit() -> None:
    assert FieldFlag.is_flag_bit_set(1, 1) is True
    assert FieldFlag.is_flag_bit_set(0, 1) is False


def test_is_flag_bit_set_round_trip_higher_bits() -> None:
    # bit 13 == 1 << 12
    assert FieldFlag.is_flag_bit_set(1 << 12, 13) is True
    assert FieldFlag.is_flag_bit_set(1 << 12, 14) is False
    # bit 17 == 1 << 16
    assert FieldFlag.is_flag_bit_set(1 << 16, 17) is True
    assert FieldFlag.is_flag_bit_set((1 << 16) - 1, 17) is False


def test_is_flag_bit_set_drives_table_set_column(ff: FieldFlag) -> None:
    # bit 17 == Pushbutton (button-field row index 5)
    rows = ff.get_button_field_flag_bits(1 << 16)
    assert rows[5][2] is True
    # untouched neighbour rows remain False
    assert rows[4][2] is False  # Radio (bit 16)
    assert rows[6][2] is False  # RadiosInUnison (bit 26)
