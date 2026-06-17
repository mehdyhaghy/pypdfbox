"""Fuzz / parity tests for stream-body ``/Length`` validation and lenient
recovery in ``PDFParser`` — the ``validateStreamLength`` /
``readUntilEndStream`` workaround in upstream ``COSParser.parseCOSStream``
(COSParser.java lines 904-967, 983-1075, 1077-1112).

When ``/Length`` is present the parser reads that many bytes then verifies an
``endstream`` keyword follows (``validateStreamLength``). When it does not —
a too-small, too-large, zero or otherwise wrong ``/Length`` — the parser
falls back to scanning forward to the next ``endstream`` (or ``endobj`` when a
producer omitted ``endstream``) and rewrites ``/Length`` with the recovered
value. A correct ``/Length`` is trusted wholesale even when the body contains
the literal bytes ``endstream`` (no false match).

These build synthetic PDF object bytes with exact byte offsets so the
``/Length`` field can be made deliberately correct / wrong, then load the file
through :class:`Loader` and assert the recovered body + ``/Length`` entry
match upstream PDFBox 3.0.7 behaviour.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSInteger, COSName, COSObject, COSObjectKey, COSStream
from pypdfbox.loader import Loader

# ---------- synthetic PDF builder ----------


def _build_pdf(stream_obj: bytes, length_obj: bytes | None = None) -> bytes:
    """Assemble a minimal, xref-correct single-stream PDF.

    ``stream_obj`` is the full ``3 0 obj ... endobj`` bytes for the stream
    under test. ``length_obj`` (when given) is the full ``4 0 obj ... endobj``
    bytes for an indirect ``/Length`` target. Offsets in the xref table are
    computed exactly so the lazy loader seeks straight to object 3.
    """
    parts: list[bytes] = [b"%PDF-1.7\n"]
    offsets: dict[int, int] = {}

    def add(num: int, data: bytes) -> None:
        offsets[num] = sum(len(p) for p in parts)
        parts.append(data)

    add(1, b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    add(2, b"2 0 obj\n<< /Type /Pages /Count 0 /Kids [] >>\nendobj\n")
    add(3, stream_obj)
    if length_obj is not None:
        add(4, length_obj)

    xref_pos = sum(len(p) for p in parts)
    count = 4 if length_obj is not None else 3
    size = count + 1
    xref = b"xref\n0 " + str(size).encode("ascii") + b"\n0000000000 65535 f \n"
    for i in range(1, size):
        xref += f"{offsets[i]:010d} 00000 n \n".encode("ascii")
    parts.append(xref)
    parts.append(
        b"trailer\n<< /Size "
        + str(size).encode("ascii")
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_pos).encode("ascii")
        + b"\n%%EOF"
    )
    return b"".join(parts)


def _load_stream(pdf: bytes) -> tuple[bytes, object]:
    """Load ``pdf`` and return ``(raw_body, length_entry)`` of object 3."""
    doc = Loader.load_pdf(pdf)
    try:
        obj = doc.get_object_from_pool(COSObjectKey(3, 0)).get_object()
        assert isinstance(obj, COSStream)
        return obj.get_raw_data(), obj.get_item(COSName.LENGTH)
    finally:
        doc.close()


def _stream_obj(length_field: bytes, body: bytes, sep: bytes = b"\n") -> bytes:
    """``3 0 obj << /Length <length_field> >> stream\\n<body><sep>endstream
    endobj`` — ``sep`` is the bytes between body and ``endstream``."""
    return (
        b"3 0 obj\n<< /Length "
        + length_field
        + b" >>\nstream\n"
        + body
        + sep
        + b"endstream\nendobj\n"
    )


# ---------- fast path: correct /Length ----------


def test_correct_length_ascii_body() -> None:
    raw, length = _load_stream(_build_pdf(_stream_obj(b"11", b"hello world")))
    assert raw == b"hello world"
    assert length == COSInteger.get(11)


def test_correct_length_binary_body() -> None:
    body = bytes(range(0, 20))
    raw, length = _load_stream(_build_pdf(_stream_obj(b"20", body)))
    assert raw == body
    assert length == COSInteger.get(20)


def test_correct_length_endstream_immediately_after_body_no_eol() -> None:
    # /Length lands exactly on 'endstream' with no preceding EOL — valid.
    so = b"3 0 obj\n<< /Length 11 >>\nstream\nhello worldendstream\nendobj\n"
    raw, length = _load_stream(_build_pdf(so))
    assert raw == b"hello world"
    assert length == COSInteger.get(11)


def test_correct_length_multiple_whitespace_before_endstream() -> None:
    # validateStreamLength's skipSpaces tolerates blank lines / spaces.
    so = b"3 0 obj\n<< /Length 5 >>\nstream\nABCDE\n\n   \nendstream\nendobj\n"
    raw, length = _load_stream(_build_pdf(so))
    assert raw == b"ABCDE"
    assert length == COSInteger.get(5)


def test_correct_length_crlf_eol_after_stream_keyword() -> None:
    so = b"3 0 obj\n<< /Length 5 >>\nstream\r\nABCDE\nendstream\nendobj\n"
    raw, length = _load_stream(_build_pdf(so))
    assert raw == b"ABCDE"
    assert length == COSInteger.get(5)


# ---------- false 'endstream' inside binary data must NOT be matched ----------


def test_valid_length_preserves_internal_endstream_bytes() -> None:
    # Body of exactly 13 bytes literally contains 'endstream'. A correct
    # /Length must skip wholesale; the inner keyword is body, not terminator.
    body = b"\x00\x01endstream\x02\x03"
    assert len(body) == 13
    raw, length = _load_stream(_build_pdf(_stream_obj(b"13", body)))
    assert raw == body
    assert length == COSInteger.get(13)


def test_valid_length_preserves_multiple_internal_endstream_bytes() -> None:
    body = b"endstream endstream endobj endstream"
    raw, length = _load_stream(
        _build_pdf(_stream_obj(str(len(body)).encode("ascii"), body))
    )
    assert raw == body
    assert length == COSInteger.get(len(body))


# ---------- too-small /Length → recovery scans forward ----------


def test_too_small_length_recovers_ascii_body() -> None:
    # ASCII body: PDFBOX-2120 keeps the trailing newline that precedes
    # endstream (leading bytes look like text → filtering disabled).
    raw, length = _load_stream(_build_pdf(_stream_obj(b"3", b"hello world")))
    assert raw == b"hello world\n"
    assert length == COSInteger.get(12)


def test_too_small_length_recovers_binary_body_strips_lf() -> None:
    body = b"\x00\x01\x02\x03\xff\xfe"
    raw, length = _load_stream(_build_pdf(_stream_obj(b"2", body)))
    assert raw == body
    assert length == COSInteger.get(len(body))


def test_too_small_length_recovers_binary_body_strips_crlf() -> None:
    body = b"\x00\x01\x02\x03\xff\xfe"
    raw, length = _load_stream(_build_pdf(_stream_obj(b"2", body, sep=b"\r\n")))
    assert raw == body
    assert length == COSInteger.get(len(body))


def test_too_small_length_zero_offset_recovers() -> None:
    raw, length = _load_stream(_build_pdf(_stream_obj(b"1", b"ABCDEFGHIJ")))
    assert raw == b"ABCDEFGHIJ\n"
    assert length == COSInteger.get(11)


# ---------- too-large /Length → recovery ----------


def test_too_large_length_within_file_recovers() -> None:
    raw, length = _load_stream(_build_pdf(_stream_obj(b"50", b"ABCDE")))
    assert raw == b"ABCDE"
    assert length == COSInteger.get(5)


def test_too_large_length_far_overrun_recovers() -> None:
    raw, length = _load_stream(_build_pdf(_stream_obj(b"99999", b"data")))
    assert raw == b"data"
    assert length == COSInteger.get(4)


def test_too_large_binary_length_recovers() -> None:
    body = b"\x10\x20\x30\x40"
    raw, length = _load_stream(_build_pdf(_stream_obj(b"4096", body)))
    assert raw == body
    assert length == COSInteger.get(len(body))


# ---------- negative /Length → recovery (never read directly) ----------


def test_negative_length_recovers() -> None:
    raw, length = _load_stream(_build_pdf(_stream_obj(b"-1", b"ABCDE")))
    assert raw == b"ABCDE"
    assert length == COSInteger.get(5)


# ---------- zero /Length (PDFBOX-5880/5954: validateStreamLength → false) --


def test_zero_length_with_body_recovers() -> None:
    # validateStreamLength returns false for length 0 → scan to endstream.
    raw, length = _load_stream(_build_pdf(_stream_obj(b"0", b"actual body here")))
    assert raw == b"actual body here\n"
    assert length == COSInteger.get(17)


def test_zero_length_empty_body_stays_empty() -> None:
    so = b"3 0 obj\n<< /Length 0 >>\nstream\nendstream\nendobj\n"
    raw, length = _load_stream(_build_pdf(so))
    assert raw == b""
    assert length == COSInteger.get(0)


# ---------- missing /Length → pure scan-to-endstream ----------


def test_missing_length_recovers_binary_body() -> None:
    so = b"3 0 obj\n<< >>\nstream\n\x00\x01\x02\x03binary\xff\nendstream\nendobj\n"
    raw, length = _load_stream(_build_pdf(so))
    assert raw == b"\x00\x01\x02\x03binary\xff"
    assert length == COSInteger.get(11)


def test_missing_length_empty_body() -> None:
    so = b"3 0 obj\n<< >>\nstream\nendstream\nendobj\n"
    raw, length = _load_stream(_build_pdf(so))
    assert raw == b""
    assert length == COSInteger.get(0)


def test_missing_length_ascii_body_keeps_trailing_newline() -> None:
    so = b"3 0 obj\n<< >>\nstream\nhello world here\nendstream\nendobj\n"
    raw, length = _load_stream(_build_pdf(so))
    assert raw == b"hello world here\n"
    assert length == COSInteger.get(17)


# ---------- indirect /Length (N G R) resolution ----------


def test_indirect_length_correct_keeps_indirect_reference() -> None:
    # A correct indirect /Length is trusted; the trusted path does NOT
    # rewrite /Length, so the indirect COSObject reference survives.
    so = b"3 0 obj\n<< /Length 4 0 R >>\nstream\nhello world\nendstream\nendobj\n"
    ext = b"4 0 obj\n11\nendobj\n"
    raw, length = _load_stream(_build_pdf(so, ext))
    assert raw == b"hello world"
    assert isinstance(length, COSObject)
    assert length.object_number == 4


def test_indirect_length_correct_binary_body() -> None:
    body = bytes(range(0, 32))
    so = (
        b"3 0 obj\n<< /Length 4 0 R >>\nstream\n"
        + body
        + b"\nendstream\nendobj\n"
    )
    ext = b"4 0 obj\n32\nendobj\n"
    raw, length = _load_stream(_build_pdf(so, ext))
    assert raw == body
    assert isinstance(length, COSObject)


def test_indirect_length_wrong_recovers_and_rewrites_direct() -> None:
    # Wrong indirect length triggers recovery; recovery rewrites /Length to
    # a direct COSInteger (orphaning the indirect ref), matching upstream
    # dic.setLong(LENGTH, streamLength).
    so = b"3 0 obj\n<< /Length 4 0 R >>\nstream\nhello world\nendstream\nendobj\n"
    ext = b"4 0 obj\n3\nendobj\n"
    raw, length = _load_stream(_build_pdf(so, ext))
    assert raw == b"hello world\n"
    assert length == COSInteger.get(12)


def test_indirect_length_null_target_recovers() -> None:
    # /Length 4 0 R where object 4 is null → getLength returns None →
    # fallback scan (lenient).
    so = b"3 0 obj\n<< /Length 4 0 R >>\nstream\nhello world\nendstream\nendobj\n"
    ext = b"4 0 obj\nnull\nendobj\n"
    raw, length = _load_stream(_build_pdf(so, ext))
    assert raw == b"hello world\n"
    assert length == COSInteger.get(12)


# ---------- endobj reached before endstream (omitted endstream) ----------


def test_endobj_before_endstream_recovers() -> None:
    # Producer omitted 'endstream' entirely; recovery stops at 'endobj'.
    so = b"3 0 obj\n<< >>\nstream\n\x00\x01\x02binary\nendobj\n"
    raw, length = _load_stream(_build_pdf(so))
    assert raw == b"\x00\x01\x02binary"
    assert length == COSInteger.get(9)


def test_endstream_chosen_over_later_endobj() -> None:
    # Both keywords present, endstream first → stop at endstream, the
    # trailing 'endobj' is the object terminator.
    body = b"\x00\x01\x02\x03payload"
    so = (
        b"3 0 obj\n<< /Length 1 >>\nstream\n"
        + body
        + b"\nendstream\nendobj\n"
    )
    raw, length = _load_stream(_build_pdf(so))
    assert raw == body
    assert length == COSInteger.get(len(body))


# ---------- EOL-before-endstream variants under recovery ----------


@pytest.mark.parametrize(
    ("sep", "expected_tail"),
    [
        (b"\n", b""),  # LF stripped (binary)
        (b"\r\n", b""),  # CRLF stripped
        (b"\r", b"\r"),  # lone CR is significant — kept
        (b"", b""),  # no separator at all
    ],
    ids=["lf", "crlf", "lone_cr", "none"],
)
def test_recovery_eol_handling_binary(sep: bytes, expected_tail: bytes) -> None:
    body = b"\x01\x02\x03\x04\x05\x06"
    so = (
        b"3 0 obj\n<< /Length 1 >>\nstream\n"
        + body
        + sep
        + b"endstream\nendobj\n"
    )
    raw, _length = _load_stream(_build_pdf(so))
    assert raw == body + expected_tail


# ---------- /Length boundary: exactly EOF / off by one ----------


def test_length_exactly_to_endstream_offset_is_trusted() -> None:
    # Length that lands precisely on the 'e' of endstream (after its EOL is
    # part of the body? no — endstream immediately follows the body bytes).
    body = b"\xaa\xbb\xcc\xdd"
    so = (
        b"3 0 obj\n<< /Length 4 >>\nstream\n"
        + body
        + b"endstream\nendobj\n"
    )
    raw, length = _load_stream(_build_pdf(so))
    assert raw == body
    assert length == COSInteger.get(4)


def test_length_off_by_one_too_short_recovers() -> None:
    body = b"\x11\x22\x33\x44\x55"
    so = (
        b"3 0 obj\n<< /Length 4 >>\nstream\n"
        + body
        + b"endstream\nendobj\n"
    )
    raw, length = _load_stream(_build_pdf(so))
    assert raw == body
    assert length == COSInteger.get(5)


def test_length_off_by_one_too_long_recovers() -> None:
    body = b"\x11\x22\x33\x44\x55"
    so = (
        b"3 0 obj\n<< /Length 6 >>\nstream\n"
        + body
        + b"endstream\nendobj\n"
    )
    raw, length = _load_stream(_build_pdf(so))
    assert raw == body
    assert length == COSInteger.get(5)
