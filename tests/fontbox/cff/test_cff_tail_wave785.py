from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_font import CFFFont, _cff_string_to_str
from pypdfbox.fontbox.cff.fd_select import FDSelect, Format0FDSelect, Format3FDSelect
from pypdfbox.fontbox.cff.type1_char_string import Type1CharString


class _CIDTop:
    charset = [".notdef", "cid00007", "cid00042"]
    rawDict: dict[str, Any] = {}
    CharStrings: dict[str, Any] = {}  # noqa: N815
    GlobalSubrs: list[Any] = []  # noqa: N815
    Private = None


class _KeyErrorFDSelect:
    format = 3

    def __len__(self) -> int:
        return 2

    def __getitem__(self, _gid: int) -> int:
        raise KeyError("missing")


class _BadLengthFDSelect:
    format = 3

    def __len__(self) -> int:
        return -1

    def __getitem__(self, _gid: int) -> int:
        return 1


def test_cff_string_to_str_handles_byte_arrays_and_plain_objects() -> None:
    class _Named:
        def __str__(self) -> str:
            return "named-value"

    assert _cff_string_to_str(b"ABC") == "ABC"
    assert _cff_string_to_str(bytearray(b"DEF")) == "DEF"
    assert _cff_string_to_str(_Named()) == "named-value"


def test_fdselect_wrapper_falls_back_for_key_errors_and_bad_lengths() -> None:
    keyed = FDSelect.from_fonttools(_KeyErrorFDSelect())
    bad_length = FDSelect.from_fonttools(_BadLengthFDSelect())

    assert keyed[1] == 0
    assert bad_length.get_num_glyphs() == 0
    assert len(bad_length) == 0


def test_synthetic_fdselect_accessors_return_copies_and_item_lookup() -> None:
    format0 = Format0FDSelect([2, 1, 0])
    fds = format0.get_fds()
    fds[0] = 99

    format3 = Format3FDSelect(ranges=[(2, 5), (4, 7)], sentinel=6)
    ranges = format3.get_ranges()
    ranges.append((99, 99))

    assert format0[0] == 2
    assert format0.get_fds() == [2, 1, 0]
    assert format3[1] == 0
    assert format3[4] == 7
    assert format3.get_ranges() == [(2, 5), (4, 7)]
    assert format3.get_sentinel() == 6
    assert format3.get_num_ranges() == 2


def test_cid_font_selector_strings_and_missing_charstrings_are_safe() -> None:
    font = CFFCIDFont()
    font._top = _CIDTop()  # noqa: SLF001

    assert CFFCIDFont._coerce_to_cid("cid00042") == 42
    assert CFFCIDFont._coerce_to_cid("cidbad") == -1
    assert font.has_glyph("cid00007") is True
    assert font.has_glyph("cidbad") is False
    assert font.gid_for_cid(42) == 2
    assert font.get_path("cid00042") == []
    assert font.get_width("cid00042") == 0.0


def test_cff_font_bbox_and_type2_fallbacks_for_synthetic_font() -> None:
    font = CFFFont()
    font.add_value_to_top_dict("FontBBox", object())

    cid_font = CFFCIDFont()
    cid_font._top = _CIDTop()  # noqa: SLF001

    char_string = cid_font.get_type2_char_string(-10)

    assert font.get_font_b_box() == [0.0, 0.0, 0.0, 0.0]
    assert char_string.get_gid() == 0
    assert char_string.get_name() == ".notdef"


def test_type1_width_can_be_read_from_previously_cached_path() -> None:
    char_string = Type1CharString(None, "F", "cached", None)
    char_string._cached_path = [("moveto", 0.0, 0.0)]  # noqa: SLF001
    char_string._t1 = SimpleNamespace(width=321.5)  # noqa: SLF001

    assert char_string.get_width() == 321.5
    char_string._t1.width = 100.0  # noqa: SLF001
    assert char_string.get_width() == 321.5
