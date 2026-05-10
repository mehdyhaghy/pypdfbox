"""Hand-written tests for :class:`pypdfbox.fontbox.cff.header.Header`.

Mirrors upstream ``CFFParser.Header`` (``CFFParser.java`` lines
1280-1303): the dataclass is immutable, the four fields map 1:1 to the
CFF wire layout, and ``to_string`` produces a Java-style debug rendering.
"""

from __future__ import annotations

import dataclasses

import pytest

from pypdfbox.fontbox.cff.header import Header


def test_construction_stores_fields() -> None:
    header = Header(major=1, minor=0, hdr_size=4, off_size=2)
    assert header.major == 1
    assert header.minor == 0
    assert header.hdr_size == 4
    assert header.off_size == 2


def test_to_string_format() -> None:
    header = Header(major=1, minor=0, hdr_size=4, off_size=2)
    assert header.to_string() == "Header[major=1, minor=0, hdrSize=4, offSize=2]"
    # ``str()`` should match ``to_string`` for parity with upstream
    # toString being the default rendering.
    assert str(header) == header.to_string()


def test_is_frozen() -> None:
    header = Header(major=1, minor=0, hdr_size=4, off_size=2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        header.major = 2  # type: ignore[misc]


def test_equality() -> None:
    a = Header(1, 0, 4, 2)
    b = Header(1, 0, 4, 2)
    c = Header(1, 0, 4, 3)
    assert a == b
    assert a != c
    assert hash(a) == hash(b)
