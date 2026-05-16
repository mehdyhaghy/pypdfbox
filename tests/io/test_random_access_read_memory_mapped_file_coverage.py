"""Wave 1321: RandomAccessReadMemoryMappedFile coverage-boost tests.

Covers the ``check_closed`` guard that raises ``OSError`` after the
reader has been closed (Java line 195, private). The remainder of the
class is the shim over :class:`RandomAccessReadMemoryMapped` already
exercised in the wave-1281 tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.io import RandomAccessReadMemoryMappedFile


def test_check_closed_no_raise_when_open(tmp_path: Path) -> None:
    p = tmp_path / "sample.bin"
    p.write_bytes(b"abc")
    reader = RandomAccessReadMemoryMappedFile(p)
    try:
        # Open reader — must not raise.
        reader.check_closed()
    finally:
        reader.close()


def test_check_closed_raises_after_close(tmp_path: Path) -> None:
    p = tmp_path / "sample.bin"
    p.write_bytes(b"abc")
    reader = RandomAccessReadMemoryMappedFile(p)
    reader.close()
    with pytest.raises(OSError, match="already closed"):
        reader.check_closed()


def test_check_closed_error_message_uses_class_name(tmp_path: Path) -> None:
    p = tmp_path / "sample.bin"
    p.write_bytes(b"abc")
    reader = RandomAccessReadMemoryMappedFile(p)
    reader.close()
    with pytest.raises(OSError) as excinfo:
        reader.check_closed()
    assert "RandomAccessReadMemoryMappedFile" in str(excinfo.value)
