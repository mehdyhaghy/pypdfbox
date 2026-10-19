"""Hand-written tests for ``BytecodeStream``: input types and function-body limits."""

import pytest

from pypdfbox.fontbox.ttf.bytecode_stream import BytecodeStream
from pypdfbox.fontbox.ttf.hinting_exception import HintingException


def test_accepts_int_lists_and_none():
    # GlyphDescription.get_instructions() returns a list of 0-255 ints
    s = BytecodeStream([0xB0, 7])
    assert isinstance(s.get_code(), bytes)
    assert s.next_byte() == 0xB0
    empty = BytecodeStream(None)
    assert not empty.has_next()
    assert empty.get_code() == b""


def test_bytes_are_not_copied():
    code = bytearray([1, 2, 3])
    assert BytecodeStream(code).get_code() is code


def test_set_end_limits_reads_and_seeks():
    s = BytecodeStream(bytes([0x10, 0x11, 0x2D, 0x99]))
    s.set_end(2)  # ENDF at 2
    s.seek(3)  # one past the ENDF is the exclusive limit
    assert not s.has_next()
    with pytest.raises(HintingException):
        s.seek(4)
    s.seek(1)
    assert s.next_byte() == 0x11
    assert s.next_byte() == 0x2D
    with pytest.raises(HintingException):
        s.next_byte()


def test_set_end_never_exceeds_code_length():
    s = BytecodeStream(bytes([1, 2]))
    s.set_end(100)
    s.seek(2)
    with pytest.raises(HintingException):
        s.seek(3)


def test_skip_and_signed_words():
    s = BytecodeStream(bytes([0x80, 0x00, 0x7F, 0xFF, 0x00]))
    assert s.next_word() == -32768
    assert s.next_word() == 32767
    s.skip(-4)
    assert s.position() == 0
    with pytest.raises(HintingException):
        s.skip(-1)
    s.seek(4)
    with pytest.raises(HintingException):
        s.next_word()  # one byte left
