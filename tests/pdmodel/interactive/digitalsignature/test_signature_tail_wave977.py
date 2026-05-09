from __future__ import annotations

from tests.pdmodel.interactive.digitalsignature import (
    test_signature_tail_wave828 as wave828,
)


def test_wave977_short_non_seekable_read_all_remaining_and_close() -> None:
    source = wave828._ShortNonSeekable(b"abcdef")

    assert source.read(2) == b"ab"
    assert source.read() == b"cdef"

    source.close()

    assert source.read() == b""
