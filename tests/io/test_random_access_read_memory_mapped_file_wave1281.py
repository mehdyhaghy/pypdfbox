"""Wave 1281: RandomAccessReadMemoryMappedFile alias port."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.io import RandomAccessReadMemoryMappedFile


def test_mmap_alias_reads_file(tmp_path: Path) -> None:
    p = tmp_path / "sample.bin"
    p.write_bytes(b"hello world")
    reader = RandomAccessReadMemoryMappedFile(p)
    try:
        assert reader.length() == 11
        out = bytearray(11)
        n = reader.read_into(out)
        assert n == 11
        assert bytes(out) == b"hello world"
    finally:
        reader.close()


def test_mmap_alias_seek(tmp_path: Path) -> None:
    p = tmp_path / "sample.bin"
    p.write_bytes(b"0123456789")
    reader = RandomAccessReadMemoryMappedFile(p)
    try:
        reader.seek(5)
        assert reader.get_position() == 5
        out = bytearray(2)
        reader.read_into(out)
        assert bytes(out) == b"56"
    finally:
        reader.close()
