from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.io import RandomAccessReadBufferedFile


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    p = tmp_path / "sample.bin"
    p.write_bytes(b"abcdefghijklmnopqrstuvwxyz")
    return p


def test_construction_records_length(sample_file: Path) -> None:
    rab = RandomAccessReadBufferedFile(sample_file)
    try:
        assert rab.length() == 26
        assert rab.get_position() == 0
        assert not rab.is_closed()
        assert rab.path == sample_file
    finally:
        rab.close()


def test_sequential_single_byte_read(sample_file: Path) -> None:
    with RandomAccessReadBufferedFile(sample_file) as rab:
        assert rab.read() == ord("a")
        assert rab.read() == ord("b")
        assert rab.read() == ord("c")


def test_read_into_partial_then_eof(sample_file: Path) -> None:
    with RandomAccessReadBufferedFile(sample_file) as rab:
        buf = bytearray(10)
        n = rab.read_into(buf)
        assert n == 10
        assert bytes(buf) == b"abcdefghij"
        rab.seek(20)
        n = rab.read_into(buf)
        assert n == 6
        assert bytes(buf[:6]) == b"uvwxyz"
        n = rab.read_into(buf)
        assert n == -1


def test_seek_and_position(sample_file: Path) -> None:
    with RandomAccessReadBufferedFile(sample_file) as rab:
        rab.seek(10)
        assert rab.get_position() == 10
        assert rab.read() == ord("k")


def test_seek_negative_raises(sample_file: Path) -> None:
    with RandomAccessReadBufferedFile(sample_file) as rab, pytest.raises(OSError):
        rab.seek(-1)


def test_seek_past_end_clamps_to_eof(sample_file: Path) -> None:
    with RandomAccessReadBufferedFile(sample_file) as rab:
        rab.seek(rab.length() + 1)
        assert rab.is_eof()
        assert rab.get_position() == rab.length()


def test_peek_does_not_advance(sample_file: Path) -> None:
    with RandomAccessReadBufferedFile(sample_file) as rab:
        assert rab.peek() == ord("a")
        assert rab.get_position() == 0


def test_rewind_moves_back(sample_file: Path) -> None:
    with RandomAccessReadBufferedFile(sample_file) as rab:
        rab.read()
        rab.read()
        rab.read()
        rab.rewind(2)
        assert rab.get_position() == 1


def test_eof_and_available(sample_file: Path) -> None:
    with RandomAccessReadBufferedFile(sample_file) as rab:
        assert rab.available() == 26
        rab.seek(rab.length())
        assert rab.is_eof()
        assert rab.available() == 0


def test_close_makes_operations_raise(sample_file: Path) -> None:
    rab = RandomAccessReadBufferedFile(sample_file)
    rab.close()
    assert rab.is_closed()
    # Upstream checkClosed throws IOException -> OSError (project convention),
    # with the fully-qualified class name in the message.
    with pytest.raises(OSError, match="RandomAccessReadBufferedFile already closed"):
        rab.read()


def test_close_is_idempotent(sample_file: Path) -> None:
    rab = RandomAccessReadBufferedFile(sample_file)
    rab.close()
    rab.close()
    assert rab.is_closed()


def test_large_file_round_trip(tmp_path: Path) -> None:
    payload = bytes(range(256)) * 1000  # 256,000 bytes — exceeds default buffer
    p = tmp_path / "big.bin"
    p.write_bytes(payload)
    with RandomAccessReadBufferedFile(p) as rab:
        out = bytearray(len(payload))
        n = rab.read_into(out)
        assert n == len(payload)
        assert bytes(out) == payload


def test_create_view_uses_independent_handle(sample_file: Path) -> None:
    # Upstream RandomAccessReadBufferedFile.createView opens a sibling
    # handle so the view's reads don't disturb the parent's position.
    rab = RandomAccessReadBufferedFile(sample_file)
    try:
        rab.seek(2)
        view = rab.create_view(10, 5)  # bytes "klmno"
        try:
            assert view.read() == ord("k")
            assert view.read() == ord("l")
            # parent position must be unaffected by view reads
            assert rab.get_position() == 2
            assert rab.read() == ord("c")
        finally:
            view.close()
    finally:
        rab.close()


def test_create_view_close_parent_releases_sibling(sample_file: Path) -> None:
    # Closing the view must not close the user-facing parent, but it must
    # release the sibling handle the view owns (close_parent=True upstream).
    with RandomAccessReadBufferedFile(sample_file) as rab:
        view = rab.create_view(0, 5)
        view.close()
        assert view.is_closed()
        assert not rab.is_closed()


def test_create_view_on_closed_parent_raises(sample_file: Path) -> None:
    rab = RandomAccessReadBufferedFile(sample_file)
    rab.close()
    with pytest.raises(OSError, match="RandomAccessReadBufferedFile already closed"):
        rab.create_view(0, 5)
