"""
Ported from
io/src/test/java/org/apache/pdfbox/io/TestIOUtils.java
(Apache PDFBox 3.0).

Only tests for functions that pypdfbox.io.io_utils actually exposes are
included. Newer upstream helpers (closeAndLogException, unmap,
createMemoryOnlyStreamCache, createTempFileOnlyStreamCache,
createProtectedTempDir, createProtectedTempFile) are out of scope for the
io-module backfill.
"""

from __future__ import annotations

import io

from pypdfbox.io import close_quietly, copy, populate_buffer, to_byte_array


def test_populate_buffer() -> None:
    data = b"Hello World!"
    buffer = bytearray(len(data))
    count = populate_buffer(io.BytesIO(data), buffer)
    assert count == 12

    buffer = bytearray(len(data) - 2)  # buffer too small
    in_stream = io.BytesIO(data)
    count = populate_buffer(in_stream, buffer)
    assert count == 10
    left_over = to_byte_array(in_stream)
    assert len(left_over) == 2

    buffer = bytearray(len(data) + 2)  # buffer too big
    in_stream = io.BytesIO(data)
    count = populate_buffer(in_stream, buffer)
    assert count == 12
    assert in_stream.read(1) == b""  # EOD reached


def test_populate_buffer_empty() -> None:
    buffer = bytearray(10)
    in_stream = io.BytesIO(b"")
    count = populate_buffer(in_stream, buffer)
    assert count == 0


def test_to_byte_array() -> None:
    data = b"Test Data"
    result = to_byte_array(io.BytesIO(data))
    assert len(result) == len(data)
    assert result == data


def test_to_byte_array_empty() -> None:
    result = to_byte_array(io.BytesIO(b""))
    assert len(result) == 0


def test_to_byte_array_large() -> None:
    data = bytes(i % 256 for i in range(10000))
    result = to_byte_array(io.BytesIO(data))
    assert len(result) == len(data)


def test_copy() -> None:
    data = b"Copy Test Content"
    in_stream = io.BytesIO(data)
    out_stream = io.BytesIO()
    copied = copy(in_stream, out_stream)
    assert copied == len(data)
    assert out_stream.getvalue() == data


def test_copy_empty() -> None:
    in_stream = io.BytesIO(b"")
    out_stream = io.BytesIO()
    copied = copy(in_stream, out_stream)
    assert copied == 0
    assert out_stream.getbuffer().nbytes == 0


def test_copy_large() -> None:
    data = bytes(i % 256 for i in range(50000))
    in_stream = io.BytesIO(data)
    out_stream = io.BytesIO()
    copied = copy(in_stream, out_stream)
    assert copied == len(data)
    assert out_stream.getbuffer().nbytes == len(data)


def test_close_quietly_null() -> None:
    # Should not throw
    close_quietly(None)


def test_close_quietly() -> None:
    stream = io.BytesIO(bytes(10))
    close_quietly(stream)


def test_close_quietly_suppresses_exception() -> None:
    class FailingCloseable:
        def close(self) -> None:
            raise OSError("Test IOException")

    # Should not raise
    close_quietly(FailingCloseable())


# skipped: testCloseAndLogException* — pypdfbox.io has no closeAndLogException
# helper. Logging is delegated to Python's stdlib ``logging`` module.

# skipped: testUnmap* — pypdfbox uses Python ``mmap.mmap.close()`` directly,
# no manual unmap helper required (CPython garbage-collects mappings).

# skipped: testCreateMemoryOnlyStreamCache / testCreateTempFileOnlyStreamCache
# — pypdfbox uses ``MemoryUsageSetting.setup_main_memory_only`` /
# ``setup_temp_file_only`` factories instead of stream-cache builders.

# skipped: testCreateProtectedTempDir* / testCreateProtectedTempFile* —
# pypdfbox uses Python's ``tempfile`` module directly; protected-temp helpers
# are not part of the io module's public surface.
