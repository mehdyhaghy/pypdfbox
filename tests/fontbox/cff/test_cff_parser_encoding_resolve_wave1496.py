"""Wave 1496 coverage tests for the Top-DICT /Encoding resolver helpers in
:mod:`pypdfbox.fontbox.cff.cff_parser`.

Targets the still-uncovered branches of
``_resolve_top_dict_encoding`` (the ``ExpertEncoding`` predefined string,
the embedded ``list`` -> ``Format0Encoding`` / ``Format1Encoding`` wrap,
the ``.notdef``/empty-name skip, the unknown-string and absent-Encoding
fall-throughs) and ``_embedded_encoding_base_format`` (no-payload,
non-dict ``rawDict``, missing/out-of-range offset, and the supplement-bit
``& 0x7F`` masking of the on-disk format byte).

These helpers are pure functions over a fontTools-shaped ``top`` object
(only ``.Encoding`` and ``.rawDict`` are read), so each branch is pinned
with a hand-built namespace fixture rather than a full CFF parse.
"""

from __future__ import annotations

from types import SimpleNamespace

from pypdfbox.fontbox.cff.cff_expert_encoding import CFFExpertEncoding
from pypdfbox.fontbox.cff.cff_parser import (
    _embedded_encoding_base_format,
    _resolve_top_dict_encoding,
)
from pypdfbox.fontbox.cff.cff_standard_encoding import CFFStandardEncoding
from pypdfbox.fontbox.cff.format0_encoding import Format0Encoding
from pypdfbox.fontbox.cff.format1_encoding import Format1Encoding


def _top(encoding: object, raw_encoding: object = None) -> SimpleNamespace:
    raw_dict: dict[str, object] = {}
    if raw_encoding is not None:
        raw_dict["Encoding"] = raw_encoding
    return SimpleNamespace(Encoding=encoding, rawDict=raw_dict)


# ---------------------------------------------------------------------
# _resolve_top_dict_encoding — predefined strings.
# ---------------------------------------------------------------------
def test_resolve_standard_encoding_string():
    result = _resolve_top_dict_encoding(_top("StandardEncoding"))
    assert result is CFFStandardEncoding.get_instance()


def test_resolve_expert_encoding_string():
    result = _resolve_top_dict_encoding(_top("ExpertEncoding"))
    assert result is CFFExpertEncoding.get_instance()


def test_resolve_unknown_string_returns_none():
    assert _resolve_top_dict_encoding(_top("BogusEncoding")) is None


def test_resolve_absent_encoding_returns_none():
    assert _resolve_top_dict_encoding(SimpleNamespace(Encoding=None)) is None


# ---------------------------------------------------------------------
# _resolve_top_dict_encoding — embedded list wrapping.
# ---------------------------------------------------------------------
def test_resolve_embedded_list_format0_default():
    # 256-name list, no cff_payload -> base format falls back to 0.
    names = [".notdef"] * 256
    names[65] = "A"
    names[66] = "B"
    result = _resolve_top_dict_encoding(_top(names))
    assert isinstance(result, Format0Encoding)
    assert not isinstance(result, Format1Encoding)
    assert result.get_name(65) == "A"
    assert result.get_name(66) == "B"
    # .notdef entries are skipped, not mapped onto their code.
    assert result.get_code("A") == 65
    assert result.get_code("B") == 66


def test_resolve_embedded_list_skips_empty_and_notdef():
    names = [""] * 256
    names[10] = ".notdef"  # explicitly skipped by name filter
    names[20] = "x"
    result = _resolve_top_dict_encoding(_top(names))
    # Empty/.notdef do not land in the code->name map.
    assert result.get_name(10) == ".notdef"
    assert result.get_name(0) == ".notdef"
    assert result.get_name(20) == "x"


def test_resolve_embedded_list_format1_from_payload_byte():
    # Raw Encoding offset 3; payload byte there is 0x01 -> Format1.
    names = [".notdef"] * 256
    names[97] = "a"
    payload = bytes([0x00, 0x00, 0x00, 0x01, 0xFF])
    top = _top(names, raw_encoding=3)
    result = _resolve_top_dict_encoding(top, payload)
    assert isinstance(result, Format1Encoding)
    assert result.get_name(97) == "a"


def test_resolve_embedded_non_string_non_list_returns_none():
    # An int Encoding value (not str / not list) hits the final return None.
    assert _resolve_top_dict_encoding(_top(12345)) is None


# ---------------------------------------------------------------------
# _embedded_encoding_base_format — every fall-back branch.
# ---------------------------------------------------------------------
def test_base_format_no_payload_is_zero():
    assert _embedded_encoding_base_format(_top([], raw_encoding=4), None) == 0
    assert _embedded_encoding_base_format(_top([], raw_encoding=4), b"") == 0


def test_base_format_non_dict_rawdict_is_zero():
    top = SimpleNamespace(Encoding=[], rawDict=None)
    assert _embedded_encoding_base_format(top, b"\x01\x02") == 0


def test_base_format_missing_offset_is_zero():
    top = SimpleNamespace(Encoding=[], rawDict={})
    assert _embedded_encoding_base_format(top, b"\x01\x02") == 0


def test_base_format_offset_out_of_range_is_zero():
    top = _top([], raw_encoding=99)
    assert _embedded_encoding_base_format(top, b"\x01\x02") == 0


def test_base_format_non_int_offset_is_zero():
    # Predefined ids surface as strings, not lists; a str offset is not int.
    top = _top([], raw_encoding="StandardEncoding")
    assert _embedded_encoding_base_format(top, b"\x01\x02") == 0


def test_base_format_reads_low_seven_bits():
    # Supplement bit 0x80 must be masked off: 0x81 -> base format 1.
    payload = bytes([0x81, 0x00])
    top = _top([], raw_encoding=0)
    assert _embedded_encoding_base_format(top, payload) == 1
    # 0x80 (supplement of Format0) -> 0.
    assert _embedded_encoding_base_format(_top([], raw_encoding=0), bytes([0x80])) == 0
