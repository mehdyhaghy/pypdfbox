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


def test_write_bytes_alias_writes_full_buffer() -> None:
    out, sink = _stream()
    out.write_bytes(b"%PDF-1.7")
    assert sink.getvalue() == b"%PDF-1.7"
    assert out.get_position() == 8
    assert out.is_on_newline() is False


def test_write_bytes_accepts_memoryview_and_bytearray() -> None:
    out, sink = _stream()
    out.write_bytes(bytearray(b"abc"))
    out.write_bytes(memoryview(b"def"))
    assert sink.getvalue() == b"abcdef"
    assert out.get_position() == 6


def test_get_out_returns_underlying_sink() -> None:
    sink = io.BytesIO()
    out = COSStandardOutputStream(sink)
    assert out.get_out() is sink


def test_context_manager_flushes_and_closes() -> None:
    class _Tracker(io.BytesIO):
        flushed = False
        closed_calls = 0

        def flush(self) -> None:
            self.flushed = True
            super().flush()

        def close(self) -> None:
            self.closed_calls += 1
            super().close()

    sink = _Tracker()
    with COSStandardOutputStream(sink) as out:
        out.write(b"hi")
    assert sink.flushed is True
    assert sink.closed_calls == 1


def test_context_manager_closes_even_when_body_raises() -> None:
    class _Tracker(io.BytesIO):
        closed_calls = 0

        def close(self) -> None:
            self.closed_calls += 1
            super().close()

    sink = _Tracker()
    with pytest.raises(RuntimeError), COSStandardOutputStream(sink) as out:
        out.write(b"x")
        raise RuntimeError("boom")
    assert sink.closed_calls == 1


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


# ---------- write_text ----------


def test_write_text_default_encoding_is_iso_8859_1() -> None:
    out, sink = _stream()
    out.write_text("startxref")
    assert sink.getvalue() == b"startxref"
    assert out.get_position() == 9
    assert out.is_on_newline() is False


def test_write_text_iso_8859_1_handles_high_bytes() -> None:
    # PDFBox uses ISO-8859-1 for its writeReference / startxref byte sequences;
    # a byte like 0xE4 round-trips one-to-one rather than UTF-8 multi-byte.
    out, sink = _stream()
    out.write_text("ä")
    assert sink.getvalue() == b"\xe4"
    assert out.get_position() == 1


def test_write_text_explicit_encoding_override() -> None:
    out, sink = _stream()
    out.write_text("ä", encoding="utf-8")
    assert sink.getvalue() == b"\xc3\xa4"
    assert out.get_position() == 2


def test_write_text_rejects_non_string() -> None:
    out, _ = _stream()
    with pytest.raises(TypeError):
        out.write_text(b"already-bytes")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        out.write_text(123)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        out.write_text(None)  # type: ignore[arg-type]


def test_write_text_resets_on_newline_flag() -> None:
    out, _ = _stream()
    out.write_eol()
    assert out.is_on_newline() is True
    out.write_text("abc")
    assert out.is_on_newline() is False


def test_write_text_empty_string_is_noop() -> None:
    out, sink = _stream()
    out.set_on_newline(True)
    out.write_text("")
    # Zero-length payload short-circuits in ``write`` so on_newline
    # is preserved and no bytes flow to the sink.
    assert sink.getvalue() == b""
    assert out.get_position() == 0
    assert out.is_on_newline() is True


# ---------- closed property ----------


def test_closed_property_reflects_lifecycle() -> None:
    sink = io.BytesIO()
    out = COSStandardOutputStream(sink)
    assert out.closed is False
    out.close()
    assert out.closed is True


def test_close_is_idempotent_on_underlying_sink() -> None:
    class _Tracker(io.BytesIO):
        close_calls = 0

        def close(self) -> None:
            self.close_calls += 1
            super().close()

    sink = _Tracker()
    out = COSStandardOutputStream(sink)
    out.close()
    out.close()
    out.close()
    # Underlying sink is closed exactly once even if the wrapper is
    # closed multiple times — matches the writer's release / context-
    # manager call pattern.
    assert sink.close_calls == 1
    assert out.closed is True


def test_context_manager_marks_closed() -> None:
    sink = io.BytesIO()
    with COSStandardOutputStream(sink) as out:
        assert out.closed is False
        out.write(b"x")
    assert out.closed is True


# ---------- defensive None handling ----------


def test_write_rejects_none_with_typeerror() -> None:
    out, _ = _stream()
    with pytest.raises(TypeError):
        out.write(None)  # type: ignore[arg-type]


def test_write_bytes_rejects_none_with_typeerror() -> None:
    out, _ = _stream()
    with pytest.raises(TypeError):
        out.write_bytes(None)  # type: ignore[arg-type]


# ---------- repr ----------


def test_repr_includes_position_and_state() -> None:
    out, _ = _stream()
    out.write(b"abc")
    out.write_eol()
    text = repr(out)
    assert "COSStandardOutputStream" in text
    assert "position=4" in text
    assert "on_newline=True" in text
    assert "closed=False" in text


def test_repr_after_close_marks_closed_state() -> None:
    out, _ = _stream()
    out.close()
    assert "closed=True" in repr(out)
