"""Wave 1367 — :class:`RandomAccessReadMemoryMapped` boundary coverage.

Edge cases that the existing wave-281 tests miss:
* Zero-length file (mmap rejects empty fd).
* Seek past EOF clamping.
* ``read_into(buf, 0, 0)`` zero-length probe.
* Partial reads at the tail of the mapping.
* ``read`` after close raises.
* ``create_view`` provides an independent file mapping.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from pypdfbox.io.random_access_read_memory_mapped import (
    RandomAccessReadMemoryMapped,
)


def _write_tmp(data: bytes) -> Path:
    fd, name = tempfile.mkstemp(prefix="pypdfbox-w1367-mm-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
    except Exception:
        os.unlink(name)
        raise
    return Path(name)


def test_empty_file_behaves_as_eof_immediately() -> None:
    path = _write_tmp(b"")
    try:
        r = RandomAccessReadMemoryMapped(path)
        try:
            assert r.length() == 0
            assert r.read() == r.EOF
            assert r.read_into(bytearray(4)) == r.EOF
        finally:
            r.close()
    finally:
        path.unlink()


def test_seek_past_eof_clamps() -> None:
    path = _write_tmp(b"abcdef")
    try:
        r = RandomAccessReadMemoryMapped(path)
        try:
            r.seek(10_000)
            assert r.get_position() == 6
            assert r.read() == r.EOF
        finally:
            r.close()
    finally:
        path.unlink()


def test_seek_negative_raises() -> None:
    path = _write_tmp(b"abc")
    try:
        r = RandomAccessReadMemoryMapped(path)
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
        r = RandomAccessReadMemoryMapped(path)
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
        r = RandomAccessReadMemoryMapped(path)
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
        r = RandomAccessReadMemoryMapped(path)
        try:
            r.seek(4)
            out = bytearray(8)
            n = r.read_into(out)
            assert n == 2
            assert bytes(out[:2]) == b"ef"
        finally:
            r.close()
    finally:
        path.unlink()


def test_close_idempotent_and_post_close_raises() -> None:
    path = _write_tmp(b"abc")
    try:
        r = RandomAccessReadMemoryMapped(path)
        r.close()
        r.close()  # idempotent
        # Upstream RandomAccessReadMemoryMappedFile#checkClosed →
        # IOException(simpleName + " already closed") → OSError (wave 1483).
        msg = "RandomAccessReadMemoryMappedFile already closed"
        with pytest.raises(OSError, match=msg):
            r.read()
        with pytest.raises(OSError, match=msg):
            r.seek(0)
        with pytest.raises(OSError, match=msg):
            r.length()
    finally:
        path.unlink()


def test_read_returns_unsigned_byte() -> None:
    path = _write_tmp(b"\xff\x80\x7f\x00")
    try:
        r = RandomAccessReadMemoryMapped(path)
        try:
            assert r.read() == 0xFF
            assert r.read() == 0x80
            assert r.read() == 0x7F
            assert r.read() == 0x00
            assert r.read() == r.EOF
        finally:
            r.close()
    finally:
        path.unlink()


def test_create_view_uses_independent_mapping() -> None:
    path = _write_tmp(b"0123456789abcdef")
    try:
        r = RandomAccessReadMemoryMapped(path)
        try:
            v = r.create_view(4, 4)
            r.seek(10)
            out = bytearray(4)
            assert v.read_into(out) == 4
            assert bytes(out) == b"4567"
            v.close()
        finally:
            r.close()
    finally:
        path.unlink()


def test_create_view_after_close_raises() -> None:
    path = _write_tmp(b"abc")
    try:
        r = RandomAccessReadMemoryMapped(path)
        r.close()
        with pytest.raises(
            OSError, match="RandomAccessReadMemoryMappedFile already closed"
        ):
            r.create_view(0, 1)
    finally:
        path.unlink()


def test_path_property_round_trip() -> None:
    path = _write_tmp(b"x")
    try:
        r = RandomAccessReadMemoryMapped(path)
        try:
            assert r.path == path
        finally:
            r.close()
    finally:
        path.unlink()
