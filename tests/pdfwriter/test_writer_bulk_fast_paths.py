"""Bulk (non per-byte) writer paths must emit exactly what the original
per-byte algorithms emitted: literal/hex strings, ``/Name`` escaping,
``COSStandardOutputStream`` bookkeeping and the object-stream token writer."""

import io
import random

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObjectKey,
    COSString,
)
from pypdfbox.pdfwriter._name_token import name_token
from pypdfbox.pdfwriter.compress.cos_writer_object_stream import (
    COSWriterObjectStream,
)
from pypdfbox.pdfwriter.cos_standard_output_stream import COSStandardOutputStream
from pypdfbox.pdfwriter.cos_writer import COSWriter


def _reference_string(data: bytes, force_hex: bool) -> bytes:
    """Upstream ``COSWriter.writeString`` byte-for-byte (per-byte switch)."""
    is_ascii = not force_hex and all(b < 0x80 and b not in (0x0D, 0x0A) for b in data)
    if is_ascii:
        out = bytearray(b"(")
        for b in data:
            if b in (0x28, 0x29, 0x5C):
                out.append(0x5C)
            out.append(b)
        out.append(0x29)
        return bytes(out)
    return b"<" + "".join(f"{b:02X}" for b in data).encode("ascii") + b">"


def _reference_name(raw: bytes) -> bytes:
    """Upstream ``COSName.writePDF`` byte-for-byte."""
    out = bytearray(b"/")
    for b in raw:
        printable = (
            0x41 <= b <= 0x5A
            or 0x61 <= b <= 0x7A
            or 0x30 <= b <= 0x39
            or b in b"+-_@*$;."
        )
        out += bytes((b,)) if printable else f"#{b:02X}".encode("ascii")
    return bytes(out)


def _write(value: COSString | bytes) -> bytes:
    sink = io.BytesIO()
    COSWriter.write_string(value, sink)
    return sink.getvalue()


_EDGE_CASES = [
    b"",
    b"plain text",
    b"(balanced)",
    b"unbalanced (",
    b"unbalanced )",
    b")(",
    b"\\",
    b"back\\slash \\( \\)",
    b"\\\\",
    b"tab\there",
    b"\x00\x01\x1f\x7f",
    b"line\nfeed",
    b"carriage\rreturn",
    b"\r\n",
    b"caf\xe9",
    b"\xff\xfe\x00A",
    b"((()))\\\\))",
]


@pytest.mark.parametrize("data", _EDGE_CASES, ids=[f"case{i}" for i in range(len(_EDGE_CASES))])
def test_write_string_edge_cases(data: bytes) -> None:
    assert _write(data) == _reference_string(data, False)
    assert _write(COSString(data)) == _reference_string(data, False)
    forced = COSString(data)
    forced.set_force_hex_form(True)
    assert _write(forced) == _reference_string(data, True)


def test_write_string_random_bytes_match_reference() -> None:
    rng = random.Random(1234)
    alphabet = b"()\\\r\nabc \x00\x7f\x80\xff"
    for _ in range(2000):
        n = rng.randrange(0, 24)
        if rng.random() < 0.5:
            data = bytes(rng.choice(alphabet) for _ in range(n))
        else:
            data = bytes(rng.randrange(0, 128) for _ in range(n))
        assert _write(data) == _reference_string(data, False)


def test_write_string_accepts_bytearray_and_memoryview() -> None:
    assert _write(bytearray(b"a(b")) == b"(a\\(b)"
    assert _write(memoryview(b"a)b")) == b"(a\\)b)"
    with pytest.raises(TypeError):
        COSWriter.write_string("text", io.BytesIO())  # type: ignore[arg-type]


def test_write_string_into_standard_output_stream_tracks_position() -> None:
    sink = io.BytesIO()
    out = COSStandardOutputStream(sink)
    out.write_eol()
    COSWriter.write_string(COSString(b"x(y"), out)
    assert sink.getvalue() == b"\n(x\\(y)"
    assert out.get_position() == len(sink.getvalue())
    assert not out.is_on_new_line()


def test_name_token_matches_reference_for_all_bytes() -> None:
    every_byte = bytes(range(256))
    assert name_token(every_byte) == _reference_name(every_byte)
    for raw in (b"", b"Type", b"A B", b"#", b"Name#20", b"\xe9t\xe9", b"a.b;c$d*e@f_g-h+i"):
        assert name_token(raw) == _reference_name(raw)
    assert name_token(bytearray(b"A/B")) == b"/A#2FB"


def test_cos_writer_visit_from_name_uses_escaping() -> None:
    sink = io.BytesIO()
    writer = COSWriter(sink)
    COSName.get_pdf_name("A B#").accept(writer)
    assert sink.getvalue() == b"/A#20B#23"


def test_standard_output_stream_fast_path_bookkeeping() -> None:
    sink = io.BytesIO()
    out = COSStandardOutputStream(sink, position=10)
    out.write(b"")
    assert out.get_position() == 10
    out.write_eol()
    out.write(b"")
    assert out.is_on_new_line()  # an empty write leaves the EOL state alone
    out.write(b"abc")
    assert out.get_position() == 14
    assert not out.is_on_new_line()
    out.write_byte(0x41)
    out.write_int(42)
    assert sink.getvalue() == b"\nabcA42"
    assert out.get_position() == 17


def test_standard_output_stream_copies_mutable_buffers() -> None:
    chunks: list[object] = []

    class Sink:
        def write(self, data: bytes) -> None:
            chunks.append(data)

    out = COSStandardOutputStream(Sink())
    buf = bytearray(b"xyz")
    out.write(buf)
    buf[0] = 0x41
    assert chunks == [b"xyz"]
    out.write(b"hello", 1, 3)
    assert chunks[-1] == b"ell"


def test_standard_output_stream_still_validates_arguments() -> None:
    out = COSStandardOutputStream(io.BytesIO())
    with pytest.raises(TypeError):
        out.write(b"abc", False)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        out.write(None)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        out.write_byte(256)
    with pytest.raises(TypeError):
        out.write_byte(True)
    with pytest.raises(TypeError):
        out.write_int(True)


class _Pool:
    def __init__(self, keyed: dict[int, COSObjectKey] | None = None) -> None:
        self._keyed = keyed or {}

    def contains(self, obj: object) -> bool:
        return id(obj) in self._keyed

    def get_key(self, obj: object) -> COSObjectKey | None:
        return self._keyed.get(id(obj))


def test_object_stream_writer_tokens() -> None:
    indirect = COSDictionary()
    pool = _Pool({id(indirect): COSObjectKey(7, 2)})
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Int"), COSInteger.get(-5))
    d.set_item(COSName.get_pdf_name("Odd Name"), COSName.get_pdf_name("V#1"))
    d.set_item(COSName.get_pdf_name("F"), COSFloat(1.5))
    d.set_item(COSName.get_pdf_name("B"), COSBoolean.TRUE)
    d.set_item(COSName.get_pdf_name("N"), COSNull.NULL)
    d.set_item(COSName.get_pdf_name("S"), COSString(b"a(b"))
    d.set_item(COSName.get_pdf_name("Ref"), indirect)
    arr = COSArray()
    arr.add(COSInteger.get(1))
    arr.add(COSName.get_pdf_name("X"))
    d.set_item(COSName.get_pdf_name("A"), arr)
    buf = io.BytesIO()
    COSWriterObjectStream(pool).write_object(buf, d, top_level=True)
    assert buf.getvalue() == (
        b"<</Int -5 /Odd#20Name /V#231 /F 1.5 /B true /N null /S (a\\(b) "
        b"/Ref 7 2 R /A [1 /X ] >> "
    )


def test_object_stream_writer_rejects_unknown_type() -> None:
    with pytest.raises(OSError, match="Unknown type"):
        COSWriterObjectStream(_Pool()).write_object(io.BytesIO(), object(), top_level=True)  # type: ignore[arg-type]
