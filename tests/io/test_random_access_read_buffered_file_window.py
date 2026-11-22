"""``RandomAccessReadBufferedFile._read_window``: the offset reads behind the
parser's chunk-scanning fast paths. They must return the file's bytes, give
up (``None``) when the file no longer holds them, fall back to the reference
cursor read for a file that fits the buffer or has changed underneath, and
release every handle on close."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import pypdfbox.io.random_access_read_buffered_file as module
from pypdfbox.io import RandomAccessReadBufferedFile

# A buffer smaller than every test file, so the page cache is used.
_SMALL_BUFFER = 8


@pytest.fixture(params=[True, False], ids=["pread", "second_handle"])
def has_pread(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> bool:
    # ``False`` runs the Windows code path (a second read-only handle) on
    # every platform.
    if request.param and not hasattr(os, "pread"):
        pytest.skip("os.pread is not available on this platform")
    monkeypatch.setattr(module, "_HAS_PREAD", request.param)
    return request.param


@pytest.fixture
def small_pages(monkeypatch: pytest.MonkeyPatch) -> int:
    # 16-byte pages, at most 4 cached: page crossings and evictions on tiny
    # files.
    monkeypatch.setattr(module, "_WINDOW_PAGE_SHIFT", 4)
    monkeypatch.setattr(module, "_WINDOW_PAGE_SIZE", 16)
    monkeypatch.setattr(module, "_WINDOW_MAX_PAGES", 4)
    return 16


def _data(size: int, salt: int = 3) -> bytes:
    return bytes((i * 7 + salt) & 0xFF for i in range(size))


def _write(tmp_path: Path, data: bytes) -> Path:
    path = tmp_path / "f.bin"
    path.write_bytes(data)
    return path


@pytest.mark.parametrize("cached", [True, False], ids=["cache", "reference"])
def test_window_returns_file_bytes(
    tmp_path: Path, has_pread: bool, small_pages: int, cached: bool
) -> None:
    data = _data(100)
    path = _write(tmp_path, data)
    src = RandomAccessReadBufferedFile(
        path, buffer_size=_SMALL_BUFFER if cached else 4096
    )
    try:
        assert src._window_cache is cached
        for start in range(100):
            for size in (1, 5, 16, 17, 31, 40):
                got = src._read_window(start, size)
                if start + size <= 100:
                    assert got == data[start : start + size], (start, size)
                else:
                    assert got is None, (start, size)
        if cached:
            assert 0 < len(src._pages) <= 4
        else:
            assert src._pages == {}
    finally:
        src.close()


def test_window_larger_than_a_page_is_read_directly(
    tmp_path: Path, has_pread: bool
) -> None:
    size = module._WINDOW_PAGE_SIZE * 3 + 5
    data = _data(size + 10)
    src = RandomAccessReadBufferedFile(_write(tmp_path, data), buffer_size=_SMALL_BUFFER)
    try:
        assert src._read_window(7, size) == data[7 : 7 + size]
        assert src._pages == {}
        assert src._read_window(11, size) is None
    finally:
        src.close()


def test_cached_window_leaves_cursor_and_reads_alone(
    tmp_path: Path, has_pread: bool, small_pages: int
) -> None:
    data = _data(80)
    src = RandomAccessReadBufferedFile(_write(tmp_path, data), buffer_size=_SMALL_BUFFER)
    try:
        src.seek(5)
        assert src.read() == data[5]
        assert src._read_window(30, 20) == data[30:50]
        assert src.get_position() == 6
        assert src.peek() == data[6]
        assert src.read() == data[6]
        src.rewind(2)
        assert src.read() == data[5]
        assert not src.is_eof()
    finally:
        src.close()


def test_reference_window_leaves_cursor_at_start(tmp_path: Path) -> None:
    data = _data(80)
    src = RandomAccessReadBufferedFile(_write(tmp_path, data))
    try:
        assert src._read_window(30, 20) == data[30:50]
        assert src.get_position() == 30
        assert src.read() == data[30]
    finally:
        src.close()


@pytest.mark.parametrize("cached", [True, False], ids=["cache", "reference"])
def test_window_on_empty_file(tmp_path: Path, has_pread: bool, cached: bool) -> None:
    src = RandomAccessReadBufferedFile(
        _write(tmp_path, b""), buffer_size=_SMALL_BUFFER if cached else 4096
    )
    try:
        assert not src._window_cache
        assert src._read_window(0, 1) is None
        assert src._read_window(0, module._WINDOW_PAGE_SIZE + 1) is None
        assert src.read() == src.EOF
    finally:
        src.close()


def test_window_after_file_shrank(tmp_path: Path, has_pread: bool, small_pages: int) -> None:
    data = _data(64)
    path = _write(tmp_path, data)
    src = RandomAccessReadBufferedFile(path, buffer_size=_SMALL_BUFFER)
    try:
        assert src._read_window(0, 10) == data[:10]
        assert src._window_cache
        path.write_bytes(data[:20])
        # A page read before the change keeps its bytes, like upstream's
        # page cache.
        assert src._read_window(2, 8) == data[2:10]
        # The next page read notices the change and drops the cache; from
        # then on the reference read runs, which finds the bytes gone.
        assert src._read_window(40, 4) is None
        assert not src._window_cache
        assert src._pages == {}
        assert src._read_window(18, 4) is None
        assert src._read_window(4, 4) == data[4:8]
        assert src.length() == 64
    finally:
        src.close()


def test_window_after_same_size_rewrite(
    tmp_path: Path, has_pread: bool, small_pages: int
) -> None:
    data = _data(64)
    path = _write(tmp_path, data)
    src = RandomAccessReadBufferedFile(path, buffer_size=_SMALL_BUFFER)
    try:
        assert src._read_window(0, 10) == data[:10]
        changed = _data(64, salt=11)
        path.write_bytes(changed)
        stat = path.stat()
        # Make the change visible even on a coarse-grained file system clock.
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
        assert src._read_window(40, 4) == changed[40:44]
        assert not src._window_cache
        assert src._pages == {}
    finally:
        src.close()


def test_large_window_after_change_takes_reference_read(
    tmp_path: Path, has_pread: bool
) -> None:
    size = module._WINDOW_PAGE_SIZE + 1
    data = _data(size + 4)
    path = _write(tmp_path, data)
    src = RandomAccessReadBufferedFile(path, buffer_size=_SMALL_BUFFER)
    try:
        path.write_bytes(data[:10])
        assert src._read_window(0, size) is None
        assert not src._window_cache
        assert src.get_position() == 0
    finally:
        src.close()


def test_window_on_closed_source_raises(tmp_path: Path, has_pread: bool) -> None:
    src = RandomAccessReadBufferedFile(_write(tmp_path, _data(32)), buffer_size=_SMALL_BUFFER)
    src.close()
    with pytest.raises(OSError, match="already closed"):
        src._read_window(0, 4)


def test_close_releases_window_handles(
    tmp_path: Path, has_pread: bool, small_pages: int
) -> None:
    path = _write(tmp_path, _data(64))
    src = RandomAccessReadBufferedFile(path, buffer_size=_SMALL_BUFFER)
    assert src._read_window(20, 10) is not None
    window_fh = src._window_fh
    assert (window_fh is None) == has_pread
    src.close()
    src.close()
    assert src._pages == {}
    assert src._window_fh is None
    if window_fh is not None:
        assert window_fh.closed
    # Every handle is closed, so the file can go (Windows refuses to delete
    # an open file).
    path.unlink()
    assert not path.exists()


def test_reopen_after_close_reads_new_bytes(tmp_path: Path, has_pread: bool) -> None:
    path = _write(tmp_path, b"A" * 50)
    src = RandomAccessReadBufferedFile(path, buffer_size=_SMALL_BUFFER)
    assert src._read_window(0, 10) == b"A" * 10
    src.close()
    path.write_bytes(b"B" * 50)
    src = RandomAccessReadBufferedFile(path, buffer_size=_SMALL_BUFFER)
    try:
        assert src._read_window(0, 10) == b"B" * 10
    finally:
        src.close()
