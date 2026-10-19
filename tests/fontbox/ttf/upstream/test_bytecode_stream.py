"""Port of upstream ``BytecodeStreamTest``: the cursor, including bounds checking."""

import pytest

from pypdfbox.fontbox.ttf.bytecode_stream import BytecodeStream
from pypdfbox.fontbox.ttf.hinting_exception import HintingException


def test_sequential_reads():
    s = BytecodeStream(bytes([0xB0, 0x05, 0xFF, 0x01]))
    assert s.has_next()
    assert s.next_byte() == 0xB0
    assert s.next_byte() == 5
    # 0xFF01 as a signed word is negative
    assert s.next_word() == 0xFF01 - 0x10000
    assert not s.has_next()


def test_byte_read_past_end_throws():
    s = BytecodeStream(bytes([0x01]))
    assert s.next_byte() == 1
    with pytest.raises(HintingException):
        s.next_byte()


def test_word_read_past_end_throws():
    # only one byte, but a word needs two
    s = BytecodeStream(bytes([0x01]))
    with pytest.raises(HintingException):
        s.next_word()


def test_seek_out_of_range_throws():
    s = BytecodeStream(bytes([0x01, 0x02]))
    s.seek(2)  # end position is valid
    assert not s.has_next()
    with pytest.raises(HintingException):
        s.seek(3)
    with pytest.raises(HintingException):
        s.seek(-1)


def test_instruction_start_tracking():
    s = BytecodeStream(bytes([0x10, 0x11, 0x12]))
    s.next_byte()
    s.mark_instruction_start()
    assert s.instruction_start() == 1
    assert s.next_byte() == 0x11
