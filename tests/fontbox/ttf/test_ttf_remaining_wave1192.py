from __future__ import annotations

from tests.fontbox.ttf.test_ttf_remaining_wave729 import _BytesRandomAccessSource


def test_bytes_random_access_source_returns_negative_one_after_eof() -> None:
    source = _BytesRandomAccessSource(b"x")
    source.seek(1)

    assert source.read_into(bytearray(1), 0, 1) == -1
