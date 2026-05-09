from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_font import _cff_string_to_str
from pypdfbox.fontbox.cff.fd_select import FDSelect, Format3FDSelect
from pypdfbox.fontbox.cff.type1_char_string import Type1CharString


class _LenGetItemFDSelect:
    format = 3

    def __len__(self) -> int:
        return 4

    def __getitem__(self, gid: int) -> int:
        return gid + 10


class _CIDFontWithBlankGlyphName(CFFCIDFont):
    def gid_for_cid(self, cid: int) -> int:
        return cid

    def get_name_for_gid(self, gid: int) -> str:
        return ""


def test_cff_string_to_str_none_returns_empty_string() -> None:
    assert _cff_string_to_str(None) == ""


def test_fdselect_len_and_getitem_delegate_to_accessors() -> None:
    select = FDSelect.from_fonttools(_LenGetItemFDSelect())

    assert len(select) == 4
    assert select[2] == 12


def test_format3_gid_before_first_range_falls_back_to_zero() -> None:
    select = Format3FDSelect(ranges=[(3, 1), (5, 2)], sentinel=8)

    assert select.get_fd_index(1) == 0


def test_cid_selector_numeric_string_and_negative_gid_tails() -> None:
    assert CFFCIDFont._coerce_to_cid("42") == 42

    font = CFFCIDFont()
    assert font.gid_for_cid(-1) == 0


def test_cid_path_and_width_return_defaults_when_gid_name_is_blank() -> None:
    font = _CIDFontWithBlankGlyphName()

    assert font.get_path(7) == []
    assert font.get_width(7) == 0.0


def test_type1_width_and_path_fall_back_when_draw_fails() -> None:
    char_string = Type1CharString(None, "F", "broken", None)
    char_string._t1 = object()  # type: ignore[attr-defined]  # noqa: SLF001

    assert char_string.get_width() == 0.0
    assert char_string.get_path() == []


def test_type1_path_falls_back_without_precomputed_width() -> None:
    char_string = Type1CharString(None, "F", "broken", None)

    class _BadCharString:
        program: list[Any] = []

    char_string._t1 = _BadCharString()  # type: ignore[attr-defined]  # noqa: SLF001

    assert char_string.get_path() == []
