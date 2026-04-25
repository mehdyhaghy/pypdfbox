"""
Ported from
io/src/test/java/org/apache/pdfbox/io/RandomAccessReadWriteBufferTest.java
(Apache PDFBox 3.0).

pypdfbox does not implement a combined Read+Write ``RandomAccessReadWriteBuffer``
class — read+write buffering is handled by ``ScratchFileBuffer``. This file
ports only the tests that exercise the write-side semantics (length, clear,
close) which apply to ``RandomAccessWriteBuffer``. Tests that require seeking
on a write buffer (testRandomAccessRead, testEOFBugInSeek, testBufferSeek,
testBufferEOF, testAlreadyClose's seek) are covered by the upstream
ScratchFileBufferTest port instead.
"""

from __future__ import annotations

import pytest

from pypdfbox.io import RandomAccessWriteBuffer


def test_close() -> None:
    rw = RandomAccessWriteBuffer()
    rw.write_bytes(bytes([1, 2, 3, 4]))
    assert not rw.is_closed()
    rw.close()
    assert rw.is_closed()


def test_clear() -> None:
    with RandomAccessWriteBuffer() as rw:
        rw.write_bytes(bytes([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
        assert rw.length() == 10
        rw.clear()
        assert not rw.is_closed()
        assert rw.length() == 0


def test_length_write_byte() -> None:
    with RandomAccessWriteBuffer() as rw:
        assert rw.length() == 0
        rw.write(1)
        rw.write(2)
        rw.write(3)
        assert rw.length() == 3


def test_length_write_bytes() -> None:
    with RandomAccessWriteBuffer() as rw:
        assert rw.length() == 0
        rw.write_bytes(bytes([1, 2, 3, 4, 5, 6, 7]))
        assert rw.length() == 7
        rw.write_bytes(bytes([8, 9, 10, 11]))
        assert rw.length() == 11


# skipped: testPaging — pypdfbox RandomAccessWriteBuffer uses io.BytesIO
# directly; there is no internal page list to exercise.

# skipped: testRandomAccessRead, testEOFBugInSeek, testBufferLength,
# testBufferSeek, testBufferEOF — those require read+seek on the write buffer.
# pypdfbox's RandomAccessWriteBuffer is write-only; combined read+write
# scenarios are covered by ScratchFileBuffer's upstream port.


def test_already_close() -> None:
    rw = RandomAccessWriteBuffer()
    rw.write_bytes(bytes(4096))
    rw.close()
    with pytest.raises((OSError, ValueError)):
        rw.write(0)
