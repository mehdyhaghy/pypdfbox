"""Hand-written tests for ``Format0FDSelect.to_string`` /
``Format3FDSelect.to_string``.

Mirrors upstream ``Format0FDSelect.toString()`` (CFFParser.java lines
1161-1163) and ``Format3FDSelect.toString()`` (CFFParser.java lines
1110-1113), plus the inner ``Range3.toString()`` (CFFParser.java lines
1132-1135).
"""

from __future__ import annotations

from pypdfbox.fontbox.cff.fd_select import Format0FDSelect, Format3FDSelect


def test_format0_to_string_empty() -> None:
    fd = Format0FDSelect([])
    assert fd.to_string() == "Format0FDSelect[fds=[]]"
    assert repr(fd) == fd.to_string()


def test_format0_to_string_values() -> None:
    fd = Format0FDSelect([1, 2, 3])
    assert fd.to_string() == "Format0FDSelect[fds=[1, 2, 3]]"
    assert repr(fd) == fd.to_string()


def test_format3_to_string_empty() -> None:
    fd = Format3FDSelect([], 0)
    assert fd.to_string() == "Format3FDSelect[nbRanges=0, range3=[] sentinel=0]"
    assert repr(fd) == fd.to_string()


def test_format3_to_string_ranges() -> None:
    fd = Format3FDSelect([(0, 1), (5, 2)], 10)
    expected = (
        "Format3FDSelect[nbRanges=2, range3=["
        "Range3[first=0, fd=1], Range3[first=5, fd=2]] sentinel=10]"
    )
    assert fd.to_string() == expected
    assert repr(fd) == fd.to_string()
