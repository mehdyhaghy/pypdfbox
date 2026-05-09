from __future__ import annotations

from tests.pdmodel.interactive.digitalsignature import (
    test_signature_tail_wave815 as wave815,
)


def test_wave978_non_seekable_read_all_remaining_and_close() -> None:
    source = wave815._NonSeekable(b"abcdef")

    assert source.read(2) == b"ab"
    assert source.read() == b"cdef"

    source.close()

    assert source.read() == b""
