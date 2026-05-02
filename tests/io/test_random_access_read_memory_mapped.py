from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.io import RandomAccessReadMemoryMapped


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    p = tmp_path / "mm.bin"
    p.write_bytes(b"abcdefghijklmnopqrstuvwxyz")
    return p


def test_basic_read(sample_file: Path) -> None:
    with RandomAccessReadMemoryMapped(sample_file) as r:
        assert r.length() == 26
        assert r.read() == ord("a")
        assert r.read() == ord("b")


def test_read_into_full(sample_file: Path) -> None:
    with RandomAccessReadMemoryMapped(sample_file) as r:
        buf = bytearray(26)
        assert r.read_into(buf) == 26
        assert bytes(buf) == b"abcdefghijklmnopqrstuvwxyz"


def test_seek_and_position(sample_file: Path) -> None:
    with RandomAccessReadMemoryMapped(sample_file) as r:
        r.seek(13)
        assert r.get_position() == 13
        assert r.read() == ord("n")


def test_eof_behavior(sample_file: Path) -> None:
    with RandomAccessReadMemoryMapped(sample_file) as r:
        r.seek(r.length())
        assert r.read() == -1
        buf = bytearray(4)
        assert r.read_into(buf) == -1


def test_zero_length_file(tmp_path: Path) -> None:
    p = tmp_path / "empty.bin"
    p.write_bytes(b"")
    with RandomAccessReadMemoryMapped(p) as r:
        assert r.length() == 0
        assert r.read() == -1


def test_close_releases_mmap(sample_file: Path) -> None:
    r = RandomAccessReadMemoryMapped(sample_file)
    r.close()
    assert r.is_closed()
    with pytest.raises(ValueError):
        r.read()


def test_create_view_works(sample_file: Path) -> None:
    with RandomAccessReadMemoryMapped(sample_file) as r:
        v = r.create_view(2, 5)
        try:
            buf = bytearray(5)
            assert v.read_into(buf) == 5
            assert bytes(buf) == b"cdefg"
        finally:
            v.close()


def test_create_view_uses_independent_mapping(sample_file: Path) -> None:
    # Upstream RandomAccessReadMemoryMappedFile.createView duplicates the
    # underlying buffer so the view's position is independent of the parent.
    with RandomAccessReadMemoryMapped(sample_file) as r:
        r.seek(2)
        view = r.create_view(10, 5)  # bytes "klmno"
        try:
            assert view.read() == ord("k")
            assert view.read() == ord("l")
            assert r.get_position() == 2
            assert r.read() == ord("c")
        finally:
            view.close()


def test_create_view_close_does_not_close_parent(sample_file: Path) -> None:
    with RandomAccessReadMemoryMapped(sample_file) as r:
        view = r.create_view(0, 5)
        view.close()
        assert view.is_closed()
        assert not r.is_closed()
        # parent must still be usable after view close
        assert r.read() == ord("a")


def test_create_view_on_closed_parent_raises(sample_file: Path) -> None:
    r = RandomAccessReadMemoryMapped(sample_file)
    r.close()
    with pytest.raises(ValueError):
        r.create_view(0, 5)
