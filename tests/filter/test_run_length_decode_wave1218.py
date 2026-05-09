from __future__ import annotations

from tests.filter.test_run_length_decode import _ShortReadBytesIO


def test_wave1218_short_read_bytesio_unbounded_read_uses_base_read() -> None:
    stream = _ShortReadBytesIO(b"abcdef")

    assert stream.read() == b"abcdef"
