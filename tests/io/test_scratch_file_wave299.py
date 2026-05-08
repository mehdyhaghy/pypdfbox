from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessReadBuffer, ScratchFile


class FailingReadBuffer(RandomAccessReadBuffer):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self._calls = 0

    def read_into(
        self, buf: bytearray, offset: int = 0, length: int | None = None
    ) -> int:
        self._calls += 1
        if self._calls > 1:
            raise OSError("source failed")
        return super().read_into(buf, offset, length)


def test_create_buffer_from_input_closes_partial_buffer_on_source_failure() -> None:
    with ScratchFile(page_size=4) as sf:
        with pytest.raises(OSError, match="source failed"):
            sf.create_buffer_from_input(FailingReadBuffer(b"abcdmore"))

        # The partially allocated page should have been returned to the owner.
        assert sf.get_new_page() == 0
        assert sf.get_page_count() == 1
