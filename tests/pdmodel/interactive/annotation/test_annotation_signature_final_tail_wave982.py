from __future__ import annotations

from tests.pdmodel.interactive.annotation import (
    test_annotation_signature_final_tail_wave834 as wave834,
)


def test_short_non_seekable_read_all_and_close_tails() -> None:
    stream = wave834._ShortNonSeekable(b"abc")  # noqa: SLF001

    assert stream.read() == b"abc"

    stream = wave834._ShortNonSeekable(b"abc")  # noqa: SLF001
    assert stream.read(1) == b"a"

    stream.close()

    assert stream.read() == b""
