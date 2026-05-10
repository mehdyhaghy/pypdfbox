"""Wave 1238 — parity for ``toString()`` on ``Format0FDSelect`` /
``Format3FDSelect``.

Upstream CFFParser.java lines 1109-1114 (``Format3FDSelect.toString``)
and 1160-1164 (``Format0FDSelect.toString``) define a structured debug
representation. Java's ``Arrays.toString(int[])`` formats integer arrays
as ``[1, 2, 3]`` (comma + space), which we mirror here.
"""

from __future__ import annotations

from pypdfbox.fontbox.cff.fd_select import Format0FDSelect, Format3FDSelect


def test_format0_repr_matches_upstream_arrays_to_string_layout() -> None:
    select = Format0FDSelect([0, 1, 2, 1])

    rep = repr(select)

    assert rep == "Format0FDSelect[fds=[0, 1, 2, 1]]"


def test_format0_repr_empty_array_renders_empty_brackets() -> None:
    select = Format0FDSelect([])

    assert repr(select) == "Format0FDSelect[fds=[]]"


def test_format0_repr_coerces_through_int_for_robustness() -> None:
    select = Format0FDSelect([1, 2])
    select._fds = [True, False]  # type: ignore[list-item]  # noqa: SLF001

    assert repr(select) == "Format0FDSelect[fds=[1, 0]]"


def test_format3_repr_matches_upstream_layout_with_sentinel() -> None:
    select = Format3FDSelect(ranges=[(0, 2), (3, 4)], sentinel=6)

    rep = repr(select)

    assert rep == (
        "Format3FDSelect[nbRanges=2, range3=[Range3[first=0, fd=2], "
        "Range3[first=3, fd=4]] sentinel=6]"
    )


def test_format3_repr_empty_ranges_renders_zero_nbranges() -> None:
    select = Format3FDSelect(ranges=[], sentinel=0)

    assert repr(select) == "Format3FDSelect[nbRanges=0, range3=[] sentinel=0]"


def test_format3_repr_single_range_no_trailing_comma() -> None:
    select = Format3FDSelect(ranges=[(0, 7)], sentinel=10)

    assert (
        repr(select)
        == "Format3FDSelect[nbRanges=1, range3=[Range3[first=0, fd=7]] sentinel=10]"
    )
