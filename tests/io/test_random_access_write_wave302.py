from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessWriteBuffer


def test_write_bytes_camelcase_alias_writes_selected_slice() -> None:
    writer = RandomAccessWriteBuffer()

    writer.writeBytes(b"0123456789", 3, 4)

    assert writer.to_bytes() == b"3456"
    assert writer.tell() == 4


def test_write_bytes_camelcase_alias_preserves_validation() -> None:
    writer = RandomAccessWriteBuffer()

    with pytest.raises(ValueError, match="offset/length out of range"):
        writer.writeBytes(b"abc", 2, 2)


def test_write_bytes_camelcase_alias_raises_when_closed() -> None:
    writer = RandomAccessWriteBuffer()
    writer.close()

    with pytest.raises(ValueError, match="operation on closed"):
        writer.writeBytes(b"x")
