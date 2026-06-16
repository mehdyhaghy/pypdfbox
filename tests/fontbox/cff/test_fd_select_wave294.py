from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.cff.fd_select import FDSelect, Format0FDSelect, Format3FDSelect


def test_wrapped_fdselect_malformed_format_and_value_fall_back_to_default() -> None:
    class _MalformedFDSelect:
        format = "not-an-int"

        def __len__(self) -> int:
            return 2

        def __getitem__(self, gid: int) -> str:
            return "bad"

    select = FDSelect.from_fonttools(_MalformedFDSelect())

    assert select.get_format() == 0
    assert select.get_num_glyphs() == 2
    assert select.get_fd_index(0) == 0


def test_format0_malformed_fd_entry_falls_back_to_default() -> None:
    select = Format0FDSelect([1])
    select._fds = ["bad"]  # type: ignore[list-item]  # noqa: SLF001

    assert select.get_fd_index(0) == 0
    assert select.get_fd_index(1) == 0


def test_format3_negative_sentinel_clamps_to_zero() -> None:
    select = Format3FDSelect(ranges=[(0, 2)], sentinel=-4)
    # Negative sentinel clamps to 0, so the count/membership views collapse. But
    # get_fd_index mirrors upstream CFFParser$Format3FDSelect.getFDIndex (verified
    # by disassembly + CffFdSelectFuzzProbe oracle): the range walk does NOT
    # short-circuit on a zero sentinel, so GID 0 (last range, gid >= sentinel)
    # returns -1, not 0 (the pre-wave-1551 short-circuit bug).
    assert select.get_num_glyphs() == 0
    assert select.get_sentinel() == 0
    assert select.get_fd_index(0) == -1
    assert 0 not in select


def test_wrapped_fdselect_malformed_len_falls_back_to_zero() -> None:
    class _MalformedLength:
        format = 3

        def __len__(self) -> Any:
            raise ValueError("bad length")

        def __getitem__(self, gid: int) -> int:
            return 1

    select = FDSelect.from_fonttools(_MalformedLength())

    assert select.get_num_glyphs() == 0
    assert 0 not in select


def test_format3_gid_at_or_after_sentinel_returns_minus_one_like_pdfbox() -> None:
    select = Format3FDSelect(ranges=[(0, 2), (3, 4)], sentinel=6)

    assert select.get_fd_index(5) == 4
    assert select.get_fd_index(6) == -1
    assert select.get_fd_index(99) == -1
