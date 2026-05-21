"""Wave 1367 — :class:`RandomAccessReadBufferedFile` boundary coverage."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from pypdfbox.io.random_access_read_buffered_file import (
    RandomAccessReadBufferedFile,
)


def _write_tmp(data: bytes) -> Path:
    fd, name = tempfile.mkstemp(prefix="pypdfbox-w1367-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
    except Exception:
        os.unlink(name)
        raise
    return Path(name)


def test_seek_past_eof_clamps() -> None:
    path = _write_tmp(b"abcdef")
    try:
        r = RandomAccessReadBufferedFile(path)
        try:
            r.seek(10_000)
            assert r.get_position() == 6
            assert r.is_eof() is True
            assert r.read() == r.EOF
        finally:
            r.close()
    finally:
        path.unlink()


def test_seek_negative_raises() -> None:
    path = _write_tmp(b"abc")
    try:
        r = RandomAccessReadBufferedFile(path)
        try:
            with pytest.raises(OSError):
                r.seek(-1)
        finally:
            r.close()
    finally:
        path.unlink()


def test_read_into_zero_length_at_eof_returns_zero() -> None:
    path = _write_tmp(b"abc")
    try:
        r = RandomAccessReadBufferedFile(path)
        try:
            r.seek(3)
            assert r.read_into(bytearray(8), 0, 0) == 0
        finally:
            r.close()
    finally:
        path.unlink()


def test_read_into_bad_offset_raises() -> None:
    path = _write_tmp(b"abc")
    try:
        r = RandomAccessReadBufferedFile(path)
        try:
            with pytest.raises(ValueError):
                r.read_into(bytearray(2), 0, 3)
            with pytest.raises(ValueError):
                r.read_into(bytearray(2), -1, 1)
            with pytest.raises(ValueError):
                r.read_into(bytearray(2), 0, -1)
        finally:
            r.close()
    finally:
        path.unlink()


def test_read_into_partial_at_tail() -> None:
    path = _write_tmp(b"abcdef")
    try:
        r = RandomAccessReadBufferedFile(path)
        try:
            r.seek(4)
            out = bytearray(8)
            n = r.read_into(out)
            assert n == 2
            assert bytes(out[:2]) == b"ef"
            # Subsequent read at EOF yields EOF, not zero.
            assert r.read_into(bytearray(4)) == r.EOF
        finally:
            r.close()
    finally:
        path.unlink()


def test_close_idempotent_and_post_close_ops_raise() -> None:
    path = _write_tmp(b"abc")
    try:
        r = RandomAccessReadBufferedFile(path)
        r.close()
        r.close()  # idempotent
        assert r.is_closed() is True
        with pytest.raises(ValueError):
            r.read()
        with pytest.raises(ValueError):
            r.seek(0)
        with pytest.raises(ValueError):
            r.length()
        with pytest.raises(ValueError):
            r.check_closed()
        with pytest.raises(ValueError):
            r.read_page()
    finally:
        path.unlink()


def test_read_page_returns_up_to_page_size() -> None:
    payload = b"x" * (RandomAccessReadBufferedFile.PAGE_SIZE + 100)
    path = _write_tmp(payload)
    try:
        r = RandomAccessReadBufferedFile(path)
        try:
            page = r.read_page()
            assert len(page) == RandomAccessReadBufferedFile.PAGE_SIZE
            page2 = r.read_page()
            assert len(page2) == 100  # tail
        finally:
            r.close()
    finally:
        path.unlink()


def test_remove_eldest_entry_always_false() -> None:
    path = _write_tmp(b"a")
    try:
        r = RandomAccessReadBufferedFile(path)
        try:
            assert r.remove_eldest_entry() is False
            assert r.remove_eldest_entry(object()) is False
        finally:
            r.close()
    finally:
        path.unlink()


def test_create_view_independent_handle() -> None:
    payload = b"0123456789abcdef"
    path = _write_tmp(payload)
    try:
        r = RandomAccessReadBufferedFile(path)
        try:
            view = r.create_view(4, 4)  # "4567"
            r.seek(10)  # parent moves
            out = bytearray(4)
            n = view.read_into(out)
            assert n == 4
            assert bytes(out) == b"4567"
            view.close()
        finally:
            r.close()
    finally:
        path.unlink()


def test_path_property_returns_pathlib() -> None:
    path = _write_tmp(b"x")
    try:
        r = RandomAccessReadBufferedFile(path)
        try:
            assert r.path == path
            assert isinstance(r.path, Path)
        finally:
            r.close()
    finally:
        path.unlink()


def test_is_eof_via_peek() -> None:
    path = _write_tmp(b"ab")
    try:
        r = RandomAccessReadBufferedFile(path)
        try:
            assert r.is_eof() is False
            r.seek(2)
            assert r.is_eof() is True
        finally:
            r.close()
    finally:
        path.unlink()
