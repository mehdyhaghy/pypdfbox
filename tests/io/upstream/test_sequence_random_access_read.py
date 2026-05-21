"""
Ported from
io/src/test/java/org/apache/pdfbox/io/SequenceRandomAccessReadTest.java
(Apache PDFBox 3.0.x).

Exercises ``SequenceRandomAccessRead`` — the concatenation of several
``RandomAccessRead`` sources presented as a single logical stream: empty
list rejection, length, seek/peek/rewind across the underlying boundary,
EOF, empty-stream filtering, and the PDFBOX-5981 regression that probed
``RandomAccessInputStream`` over a many-segment sequence.
"""

from __future__ import annotations

import pytest

from pypdfbox.io.random_access_input_stream import RandomAccessInputStream
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.io.sequence_random_access_read import SequenceRandomAccessRead


def test_create_and_read() -> None:
    input1 = "This is a test string number 1"
    rarb1 = RandomAccessReadBuffer(input1.encode("utf-8"))
    input2 = "This is a test string number 2"
    rarb2 = RandomAccessReadBuffer(input2.encode("utf-8"))
    input_list = [rarb1, rarb2]
    with SequenceRandomAccessRead(input_list) as seq:
        # Views are not supported on sequence readers.
        with pytest.raises((NotImplementedError, OSError)):
            seq.create_view(0, 10)

        overall_length = len(input1) + len(input2)
        assert seq.length() == overall_length

        bytes_read = bytearray(overall_length)
        assert seq.read_into(bytes_read) == overall_length
        assert bytes_read.decode("utf-8") == input1 + input2

    # missing parameter (None)
    with pytest.raises((ValueError, TypeError)):
        SequenceRandomAccessRead(None)  # type: ignore[arg-type]

    # empty list
    with pytest.raises(ValueError):
        SequenceRandomAccessRead([])

    # problematic list — the readers were closed by the first ``with``.
    with pytest.raises((ValueError, OSError)):
        SequenceRandomAccessRead(input_list)


def test_seek_peek_and_rewind() -> None:
    input1 = "01234567890123456789"
    rarb1 = RandomAccessReadBuffer(input1.encode("utf-8"))
    input2 = "abcdefghijklmnopqrst"
    rarb2 = RandomAccessReadBuffer(input2.encode("utf-8"))
    input_list = [rarb1, rarb2]
    with SequenceRandomAccessRead(input_list) as seq:
        # in the first part of the sequence
        seq.seek(4)
        assert seq.get_position() == 4
        assert seq.read() == ord("4")
        assert seq.get_position() == 5
        seq.rewind(1)
        assert seq.get_position() == 4
        assert seq.read() == ord("4")
        assert seq.peek() == ord("5")
        assert seq.get_position() == 5
        assert seq.read() == ord("5")
        assert seq.get_position() == 6
        # in the second part of the sequence
        seq.seek(24)
        assert seq.get_position() == 24
        assert seq.read() == ord("e")
        seq.rewind(1)
        assert seq.read() == ord("e")
        assert seq.peek() == ord("f")
        assert seq.read() == ord("f")
        with pytest.raises(OSError):
            seq.seek(-1)


def test_border_cases() -> None:
    input1 = "01234567890123456789"
    rarb1 = RandomAccessReadBuffer(input1.encode("utf-8"))
    input2 = "abcdefghijklmnopqrst"
    rarb2 = RandomAccessReadBuffer(input2.encode("utf-8"))
    input_list = [rarb1, rarb2]
    with SequenceRandomAccessRead(input_list) as seq:
        # jump to the last byte of the first part of the sequence
        seq.seek(19)
        assert seq.read() == ord("9")
        seq.rewind(1)
        assert seq.read() == ord("9")
        assert seq.peek() == ord("a")
        assert seq.read() == ord("a")

        # jump back to the first sequence and read across the boundary
        seq.seek(17)
        bytes_read = bytearray(6)
        assert seq.read_into(bytes_read) == 6
        assert bytes_read.decode("utf-8") == "789abc"
        assert seq.get_position() == 23

        # rewind back to the first sequence
        seq.rewind(6)
        assert seq.get_position() == 17
        bytes_read = bytearray(6)
        assert seq.read_into(bytes_read) == 6
        assert bytes_read.decode("utf-8") == "789abc"

        # jump to the start of the sequence
        seq.seek(0)
        bytes_read = bytearray(6)
        assert seq.read_into(bytes_read) == 6
        assert bytes_read.decode("utf-8") == "012345"


def test_eof() -> None:
    input1 = "01234567890123456789"
    rarb1 = RandomAccessReadBuffer(input1.encode("utf-8"))
    input2 = "abcdefghijklmnopqrst"
    rarb2 = RandomAccessReadBuffer(input2.encode("utf-8"))
    input_list = [rarb1, rarb2]
    seq = SequenceRandomAccessRead(input_list)

    overall_length = len(input1) + len(input2)

    seq.seek(overall_length - 1)
    assert not seq.is_eof()
    assert seq.peek() == ord("t")
    assert not seq.is_eof()
    assert seq.read() == ord("t")
    assert seq.is_eof()
    assert seq.read() == -1
    assert seq.read_into(bytearray(1), 0, 1) == -1
    # rewind
    seq.rewind(5)
    assert not seq.is_eof()
    bytes_read = bytearray(5)
    assert seq.read_into(bytes_read) == 5
    assert bytes_read.decode("utf-8") == "pqrst"
    assert seq.is_eof()

    # seek to a position beyond the end of the input
    seq.seek(overall_length + 10)
    assert seq.is_eof()
    assert seq.get_position() == overall_length

    assert not seq.is_closed()
    seq.close()
    assert seq.is_closed()
    # closing twice shouldn't be a problem
    seq.close()

    with pytest.raises(OSError):
        seq.read()


def test_empty_stream() -> None:
    input1 = "01234567890123456789"
    rarb1 = RandomAccessReadBuffer(input1.encode("utf-8"))
    input2 = "abcdefghijklmnopqrst"
    rarb2 = RandomAccessReadBuffer(input2.encode("utf-8"))
    empty_buffer = RandomAccessReadBuffer(b"")

    input_list = [rarb1, empty_buffer, rarb2]

    with SequenceRandomAccessRead(input_list) as seq:
        assert seq.length() == len(input1) + len(input2)

        # read from both parts of the sequence
        bytes_read = bytearray(10)
        seq.seek(15)
        assert seq.read_into(bytes_read) == 10
        assert bytes_read.decode("utf-8") == "56789abcde"

        # rewind and read again
        seq.rewind(15)
        bytes_read = bytearray(5)
        assert seq.read_into(bytes_read) == 5
        assert bytes_read.decode("utf-8") == "01234"

        # check EOF when reading
        bytes_read = bytearray(5)
        seq.seek(38)
        assert seq.read_into(bytes_read) == 2
        assert bytes_read[:2].decode("utf-8") == "st"

        # check EOF after seek
        seq.seek(40)
        assert seq.is_eof()


def test_pdfbox_5981() -> None:
    """PDFBOX-5981: a many-segment sequence wrapped in
    ``RandomAccessInputStream`` and read via the input-stream surface.
    """
    r1 = RandomAccessReadBuffer(bytes(2448))
    r2 = RandomAccessReadBuffer(bytes(2412))
    r3 = RandomAccessReadBuffer(bytes(2417))
    r4 = RandomAccessReadBuffer(bytes(2433))
    r5 = RandomAccessReadBuffer(bytes(2432))
    r6 = RandomAccessReadBuffer(bytes(2416))
    r7 = RandomAccessReadBuffer(bytes(2417))
    r8 = RandomAccessReadBuffer(bytes(2266))

    with SequenceRandomAccessRead([r1, r2, r3, r4, r5, r6, r7, r8]) as srar, \
            RandomAccessInputStream(srar) as rais:
        # zero-length readinto returns 0 immediately
        rc = rais.readinto(bytearray(0))
        assert rc == 0
        result = rais.read()
        assert len(result) == 19241
        assert srar.length() == len(result)
