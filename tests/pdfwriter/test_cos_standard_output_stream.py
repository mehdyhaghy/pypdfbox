from __future__ import annotations

import io

import pytest

from pypdfbox.pdfwriter.cos_standard_output_stream import (
    CRLF,
    EOL,
    COSStandardOutputStream,
)


def _stream() -> tuple[COSStandardOutputStream, io.BytesIO]:
    sink = io.BytesIO()
    return COSStandardOutputStream(sink), sink


def test_initial_state() -> None:
    out, _ = _stream()
    assert out.get_position() == 0
    assert out.get_pos() == 0
    assert out.is_on_newline() is False


def test_upstream_class_constants_are_exposed() -> None:
    assert COSStandardOutputStream.CRLF == CRLF == b"\r\n"
    assert COSStandardOutputStream.LF == b"\n"
    assert COSStandardOutputStream.EOL == EOL == b"\n"


def test_pdfbox_spelled_aliases_delegate_to_line_and_position_helpers() -> None:
    out, sink = _stream()

    out.writeCRLF()
    assert sink.getvalue() == CRLF
    assert out.getPos() == 2
    assert out.isOnNewLine() is False

    out.writeEOL()
    assert sink.getvalue() == CRLF + EOL
    assert out.isOnNewLine() is True

    out.writeEOL()
    assert sink.getvalue() == CRLF + EOL

    out.setOnNewLine(False)
    out.writeLF()
    assert sink.getvalue() == CRLF + EOL + b"\n"
    assert out.get_position() == out.getPos() == len(sink.getvalue())


def test_write_bytes_advances_position() -> None:
    out, sink = _stream()
    out.write(b"abc")
    assert out.get_position() == 3
    assert sink.getvalue() == b"abc"
    assert out.is_on_newline() is False


def test_write_int_emits_decimal_ascii() -> None:
    out, sink = _stream()
    out.write_int(0)
    out.write_int(42)
    out.write_int(-7)
    assert sink.getvalue() == b"042-7"
    assert out.get_position() == 5


def test_write_eol_emits_lf_and_marks_newline() -> None:
    out, sink = _stream()
    out.write(b"hello")
    out.write_eol()
    assert sink.getvalue() == b"hello" + EOL
    assert out.is_on_newline() is True


def test_write_eol_does_not_double_when_already_on_newline() -> None:
    out, sink = _stream()
    out.write_eol()
    out.write_eol()
    assert sink.getvalue() == EOL
    assert out.is_on_newline() is True


def test_write_lf_always_emits_even_when_on_newline() -> None:
    out, sink = _stream()
    out.write_eol()
    out.write_lf()
    # ``write_lf`` writes raw LF and resets onNewLine to False (matches
    # upstream's ``write(byte[])`` semantics).
    assert sink.getvalue() == b"\n\n"
    assert out.is_on_newline() is False


def test_write_crlf_emits_cr_lf() -> None:
    out, sink = _stream()
    out.write_crlf()
    assert sink.getvalue() == CRLF
    assert out.get_position() == 2
    # write_crlf is just a write; on_newline goes False because last byte
    # was LF but the upstream contract resets to False after raw write.
    assert out.is_on_newline() is False


def test_write_after_eol_resets_on_newline() -> None:
    out, _ = _stream()
    out.write_eol()
    out.write(b"x")
    assert out.is_on_newline() is False


def test_set_on_newline_manual_override() -> None:
    out, _ = _stream()
    out.set_on_newline(True)
    out.write_eol()
    # Already marked → no extra EOL.
    assert out.get_position() == 0


def test_write_byte_advances_one() -> None:
    out, sink = _stream()
    out.write_byte(0x41)
    assert sink.getvalue() == b"A"
    assert out.get_position() == 1


def test_write_byte_rejects_out_of_range() -> None:
    out, _ = _stream()
    with pytest.raises(ValueError):
        out.write_byte(256)
    with pytest.raises(ValueError):
        out.write_byte(-1)


def test_write_with_offset_and_length() -> None:
    out, sink = _stream()
    out.write(b"abcdef", offset=1, length=3)
    assert sink.getvalue() == b"bcd"
    assert out.get_position() == 3


def test_write_zero_length_is_noop() -> None:
    out, sink = _stream()
    out.write(b"abc", offset=0, length=0)
    assert sink.getvalue() == b""
    assert out.get_position() == 0


def test_write_negative_length_raises() -> None:
    out, _ = _stream()
    with pytest.raises(ValueError):
        out.write(b"abc", offset=0, length=-1)


def test_initial_position_argument_respected() -> None:
    sink = io.BytesIO()
    out = COSStandardOutputStream(sink, position=100)
    out.write(b"xy")
    assert out.get_position() == 102


def test_multi_write_sequence() -> None:
    out, sink = _stream()
    out.write(b"%PDF-1.4")
    out.write_eol()
    out.write(b"%")
    out.write(b"\xf6\xe4\xfc\xdf")
    out.write_eol()
    assert sink.getvalue() == b"%PDF-1.4\n%\xf6\xe4\xfc\xdf\n"
    assert out.get_position() == len(sink.getvalue())
    assert out.is_on_newline() is True
