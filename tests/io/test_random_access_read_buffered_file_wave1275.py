"""Wave 1275 parity tests for RandomAccessReadBufferedFile."""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.io.random_access_read_buffered_file import (
    RandomAccessReadBufferedFile,
)


@pytest.fixture
def small_file(tmp_path: Path) -> Path:
    p = tmp_path / "f.bin"
    p.write_bytes(b"abcdefghij" * 1000)  # 10_000 bytes spanning multiple pages
    return p


def test_page_size_constant_matches_upstream() -> None:
    # Upstream PAGE_SIZE_SHIFT = 12 → PAGE_SIZE = 4096.
    assert RandomAccessReadBufferedFile.PAGE_SIZE == 4096


def test_max_cached_pages_matches_upstream() -> None:
    assert RandomAccessReadBufferedFile.MAX_CACHED_PAGES == 1000


def test_read_page_returns_up_to_page_size_bytes(small_file: Path) -> None:
    raf = RandomAccessReadBufferedFile(small_file)
    try:
        page = raf.read_page()
        assert len(page) == RandomAccessReadBufferedFile.PAGE_SIZE
        assert page[:10] == b"abcdefghij"
    finally:
        raf.close()


def test_read_page_short_read_at_eof(small_file: Path) -> None:
    raf = RandomAccessReadBufferedFile(small_file)
    try:
        raf.seek(9_990)  # leaves only 10 bytes before EOF
        page = raf.read_page()
        assert len(page) == 10
    finally:
        raf.close()


def test_remove_eldest_entry_returns_false() -> None:
    # Python port doesn't keep an explicit page cache — predicate is a parity
    # stub, never triggers eviction.
    raf = RandomAccessReadBufferedFile.__new__(RandomAccessReadBufferedFile)
    assert raf.remove_eldest_entry(None) is False
