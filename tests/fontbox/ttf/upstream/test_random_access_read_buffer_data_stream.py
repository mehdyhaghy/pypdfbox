from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.ttf_data_stream import RandomAccessReadDataStream
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.io.random_access_read_buffered_file import RandomAccessReadBufferedFile

_LIBERATION_TTF = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def test_eof() -> None:
    """``testEOF`` upstream port."""
    byte_array = bytes(10)
    buffer = RandomAccessReadBuffer(byte_array)
    data_stream = RandomAccessReadDataStream(buffer)
    try:
        # Loop must terminate cleanly when read() hits EOF (returns -1).
        value = data_stream.read()
        while value > -1:
            value = data_stream.read()
        # Reaching here means EOF was detected -- no IndexError.
    finally:
        data_stream.close()


def test_eof_unsigned_short() -> None:
    """``testEOFUnsignedShort`` upstream port."""
    byte_array = bytes(3)
    buffer = RandomAccessReadBuffer(byte_array)
    data_stream = RandomAccessReadDataStream(buffer)
    try:
        data_stream.read_unsigned_short()  # consumes 2 bytes
        with pytest.raises(EOFError):
            data_stream.read_unsigned_short()
    finally:
        data_stream.close()


def test_eof_unsigned_int() -> None:
    """``testEOFUnsignedInt`` upstream port."""
    byte_array = bytes(5)
    buffer = RandomAccessReadBuffer(byte_array)
    data_stream = RandomAccessReadDataStream(buffer)
    try:
        data_stream.read_unsigned_int()  # consumes 4 bytes
        with pytest.raises(EOFError):
            data_stream.read_unsigned_int()
    finally:
        data_stream.close()


def test_eof_unsigned_byte() -> None:
    """``testEOFUnsignedByte`` upstream port."""
    byte_array = bytes(2)
    buffer = RandomAccessReadBuffer(byte_array)
    data_stream = RandomAccessReadDataStream(buffer)
    try:
        data_stream.read_unsigned_byte()
        data_stream.read_unsigned_byte()
        with pytest.raises(EOFError):
            data_stream.read_unsigned_byte()
    finally:
        data_stream.close()


def test_double_close() -> None:
    """``testDoubleClose`` upstream port (PDFBOX-4242)."""
    assert _LIBERATION_TTF.exists(), f"missing fixture: {_LIBERATION_TTF}"
    random_access_read = RandomAccessReadBufferedFile(str(_LIBERATION_TTF))
    data_stream = RandomAccessReadDataStream(random_access_read)
    data_stream.close()
    # Second close must not raise.
    data_stream.close()


def test_ensure_read_finishes() -> None:
    """``ensureReadFinishes`` upstream port (PDFBOX-3605)."""
    fd, path_str = tempfile.mkstemp(prefix="apache-pdfbox", suffix=".dat")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(b"1234567890")

        read_buffer = bytearray(2)
        random_access_read = RandomAccessReadBufferedFile(path_str)
        data_stream = RandomAccessReadDataStream(random_access_read)
        try:
            total_amount_read = 0
            while True:
                amount_read = data_stream.read_into(read_buffer, 0, 2)
                if amount_read == -1:
                    break
                total_amount_read += amount_read
            assert total_amount_read == 10
        finally:
            data_stream.close()
            # ``RandomAccessReadDataStream.close`` does not propagate to the
            # underlying reader; close it explicitly so Windows can unlink
            # the temp file (POSIX allows unlinking open files; Windows does
            # not).
            random_access_read.close()
    finally:
        Path(path_str).unlink(missing_ok=True)


def test_read_buffer() -> None:
    """``testReadBuffer`` upstream port: reading patterns within and across buffers."""
    fd, path_str = tempfile.mkstemp(prefix="apache-pdfbox", suffix=".dat")
    try:
        content = b"012345678A012345678B012345678C012345678D"
        with os.fdopen(fd, "wb") as f:
            f.write(content)

        random_access_read = RandomAccessReadBufferedFile(path_str)
        read_buffer = bytearray(40)
        data_stream = RandomAccessReadDataStream(random_access_read)
        try:
            count = 4
            bytes_read = data_stream.read_into(read_buffer, 0, count)
            assert data_stream.get_current_position() == 4
            assert bytes_read == count
            assert bytes(read_buffer[:count]) == b"0123"

            count = 6
            bytes_read = data_stream.read_into(read_buffer, 0, count)
            assert data_stream.get_current_position() == 10
            assert bytes_read == count
            assert bytes(read_buffer[:count]) == b"45678A"

            count = 10
            bytes_read = data_stream.read_into(read_buffer, 0, count)
            assert data_stream.get_current_position() == 20
            assert bytes_read == count
            assert bytes(read_buffer[:count]) == b"012345678B"

            count = 10
            bytes_read = data_stream.read_into(read_buffer, 0, count)
            assert data_stream.get_current_position() == 30
            assert bytes_read == count
            assert bytes(read_buffer[:count]) == b"012345678C"

            count = 10
            bytes_read = data_stream.read_into(read_buffer, 0, count)
            assert data_stream.get_current_position() == 40
            assert bytes_read == count
            assert bytes(read_buffer[:count]) == b"012345678D"

            assert data_stream.read() == -1

            data_stream.seek(0)
            data_stream.read_into(read_buffer, 0, 7)
            assert data_stream.get_current_position() == 7

            count = 16
            bytes_read = data_stream.read_into(read_buffer, 0, count)
            assert data_stream.get_current_position() == 23
            assert bytes_read == count
            assert bytes(read_buffer[:count]) == b"78A012345678B012"

            bytes_read = data_stream.read_into(read_buffer, 0, 99)
            assert data_stream.get_current_position() == 40
            assert bytes_read == 17
            assert bytes(read_buffer[:17]) == b"345678C012345678D"

            assert data_stream.read() == -1

            data_stream.seek(0)
            data_stream.read_into(read_buffer, 0, 7)
            assert data_stream.get_current_position() == 7

            count = 23
            bytes_read = data_stream.read_into(read_buffer, 0, count)
            assert data_stream.get_current_position() == 30
            assert bytes_read == count
            assert bytes(read_buffer[:count]) == b"78A012345678B012345678C"

            data_stream.seek(0)
            data_stream.read_into(read_buffer, 0, 10)
            assert data_stream.get_current_position() == 10
            count = 23
            bytes_read = data_stream.read_into(read_buffer, 0, count)
            assert data_stream.get_current_position() == 33
            assert bytes_read == count
            assert bytes(read_buffer[:count]) == b"012345678B012345678C012"
        finally:
            data_stream.close()
            # See ``test_ensure_read_finishes`` for the Windows-unlink
            # rationale: close the underlying reader before unlink.
            random_access_read.close()
    finally:
        Path(path_str).unlink(missing_ok=True)
