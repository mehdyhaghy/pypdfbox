from __future__ import annotations

from tests.pdmodel.interactive.test_navigation_signature_tail_wave844 import (
    _ShortNonSeekable,
)


def test_wave975_short_non_seekable_default_read_and_close() -> None:
    stream = _ShortNonSeekable(b"wave975")

    assert stream.read() == b"wave975"

    stream = _ShortNonSeekable(b"tail")
    stream.close()

    assert stream.read() == b""
