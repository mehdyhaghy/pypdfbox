"""Ported from upstream PDFBox 3.0
``fontbox/src/test/java/org/apache/fontbox/cmap/TestCodespaceRange.java``.

Exercises :class:`pypdfbox.fontbox.cmap.CodespaceRange` for code-length
calculation, the PDFBOX-4923 mixed-length-constructor relaxation, and
single- / two-byte range matching.

Translation notes
-----------------
* ``IllegalArgumentException`` in upstream → :class:`ValueError` here
  (already raised by the production class for mismatched start/end
  lengths).
* Java ``byte`` literals are signed; we use unsigned ``int`` bytes
  in Python's ``bytes`` constructor.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap import CodespaceRange


def test_code_length() -> None:
    """Check whether the code length calculation works."""
    range1 = CodespaceRange(bytes([0x00]), bytes([0x20]))
    assert range1.get_code_length() == 1

    range2 = CodespaceRange(bytes([0x00, 0x00]), bytes([0x01, 0x20]))
    assert range2.get_code_length() == 2


def test_constructor() -> None:
    """Check whether the constructor checks the length of the start and end bytes."""
    # PDFBOX-4923 — "1 begincodespacerange <00> <ffff> endcodespacerange"
    # is accepted (single 0x00 start widened to match the end length).
    CodespaceRange(bytes([0x00]), bytes([0xFF, 0xFF]))

    # Other cases of different lengths are rejected.
    with pytest.raises(ValueError):
        CodespaceRange(bytes([0x01]), bytes([0x01, 0x20]))


def test_matches() -> None:
    """Matching behaviour for single- and two-byte ranges, including the
    rectangular check the PostScript CMap spec mandates for >1-byte
    ranges."""
    range1 = CodespaceRange(bytes([0x00]), bytes([0xA0]))
    # check start and end value
    assert range1.matches(bytes([0x00]))
    assert range1.matches(bytes([0xA0]))
    # check any value within range
    assert range1.matches(bytes([0x10]))
    # check first value out of range
    assert not range1.matches(bytes([0xA1]))
    # check any value out of range
    assert not range1.matches(bytes([0xD0]))
    # check any value with a different code length
    assert not range1.matches(bytes([0x00, 0x10]))

    range2 = CodespaceRange(bytes([0x81, 0x40]), bytes([0x9F, 0xFC]))
    # check lower start and end value
    assert range2.matches(bytes([0x81, 0x40]))
    assert range2.matches(bytes([0x81, 0xFC]))
    # check higher start and end value
    assert range2.matches(bytes([0x81, 0x40]))
    assert range2.matches(bytes([0x9F, 0x40]))
    # check any value within lower range
    assert range2.matches(bytes([0x81, 0x65]))
    # check any value within higher range
    assert range2.matches(bytes([0x90, 0x40]))
    # check first value out of lower range
    assert not range2.matches(bytes([0x81, 0xFD]))
    # check first value out of higher range
    assert not range2.matches(bytes([0xA0, 0x40]))
    # check any value out of lower range
    assert not range2.matches(bytes([0x81, 0x20]))
    # check any value out of higher range
    assert not range2.matches(bytes([0x10, 0x40]))
    # check value between start and end but not within the rectangle
    assert not range2.matches(bytes([0x82, 0x20]))
    # check any value with a different code length
    assert not range2.matches(bytes([0x00]))
