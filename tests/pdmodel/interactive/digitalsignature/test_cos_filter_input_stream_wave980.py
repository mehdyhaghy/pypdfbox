from __future__ import annotations

from pypdfbox.pdmodel.interactive.digitalsignature.cos_filter_input_stream import (
    COSFilterInputStream,
)


def test_context_manager_closes_wrapped_source_once() -> None:
    class Source:
        def __init__(self) -> None:
            self.closed = 0

        def read(self, size: int = -1) -> bytes:
            return b"abc"[:size]

        def close(self) -> None:
            self.closed += 1

    source = Source()

    with COSFilterInputStream(source, [0, 1]) as stream:
        assert stream.read(1) == b"a"

    assert source.closed == 1
    stream.close()
    assert source.closed == 1
