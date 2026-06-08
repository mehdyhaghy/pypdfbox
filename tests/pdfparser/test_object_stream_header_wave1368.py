"""Wave 1368 — PDF 1.5+ object stream header (``/N`` & ``/First``) edges.

An object stream (``/Type /ObjStm``) consists of:
  - A leading header of ``/N`` ``(object_number, offset)`` pairs,
  - followed by a payload region starting ``/First`` bytes in.

The pair count must agree with ``/N``; offsets must be inside the
payload; and the header must not run past ``/First``. These cases are
covered here.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDocument
from pypdfbox.pdfparser import PDFParseError
from pypdfbox.pdfparser.cos_parser import _read_object_stream_offsets


def _make_objstm(
    *,
    n: int,
    first: int,
    header: bytes,
    payload: bytes,
    type_name: str = "ObjStm",
) -> tuple[object, COSDocument]:
    """Build a tiny COSStream representing an ObjStm.

    Returns ``(stream, document)`` — the document is kept on the test
    so the scratch-file buffer backing the stream isn't garbage-
    collected mid-test."""
    from pypdfbox.cos.cos_integer import COSInteger  # noqa: PLC0415
    from pypdfbox.cos.cos_name import COSName  # noqa: PLC0415

    doc = COSDocument()
    stream = doc.create_cos_stream()
    stream.set_item(COSName.TYPE, COSName.get_pdf_name(type_name))
    stream.set_item(COSName.get_pdf_name("N"), COSInteger.get(n))
    stream.set_item(COSName.get_pdf_name("First"), COSInteger.get(first))
    body_bytes = header + payload
    stream.set_data(body_bytes)
    return stream, doc


def test_object_stream_n_and_first_consistent() -> None:
    """Two objects packed cleanly: header ``"4 0 5 7 "`` -> object 4 at
    payload offset 0, object 5 at payload offset 7. Both must decode."""
    payload = b"(payload-A)(payload-B)"
    header = b"4 0 5 11 "
    stream, doc = _make_objstm(n=2, first=len(header), header=header, payload=payload)
    try:
        decoded, pairs, first = _read_object_stream_offsets(stream, 99)
        assert first == len(header)
        assert pairs == [(4, 0), (5, 11)]
        # Payload region is everything past ``first``.
        assert decoded[first:] == payload
    finally:
        doc.close()


def test_object_stream_n_zero_is_legal_empty_stream() -> None:
    """``/N 0`` means the stream is empty (no objects packed). The
    helper must produce an empty pair list rather than raise."""
    stream, doc = _make_objstm(n=0, first=0, header=b"", payload=b"")
    try:
        _decoded, pairs, first = _read_object_stream_offsets(stream, 1)
        assert pairs == []
        assert first == 0
    finally:
        doc.close()


def test_object_stream_wrong_type_is_tolerated() -> None:
    """A wrong / non-``/ObjStm`` ``/Type`` is TOLERATED — wave 1516 aligned
    the header decoder with upstream ``PDFObjectStreamParser``, whose
    constructor (Apache PDFBox 3.0.7) validates only ``/N`` and ``/First`` and
    never inspects ``/Type``. The header pairs decode regardless (validated
    against the live oracle: ``type_wrong`` / ``type_missing`` resolve the
    packed member at parity rather than raising)."""
    stream, doc = _make_objstm(
        n=1, first=4, header=b"4 0 ", payload=b"(x)", type_name="WrongType"
    )
    try:
        _decoded, pairs, first = _read_object_stream_offsets(stream, 11)
        assert pairs == [(4, 0)]
        assert first == 4
    finally:
        doc.close()


def test_object_stream_first_beyond_decoded_length_raises() -> None:
    """``/First`` larger than the decoded body length means the header
    table can't possibly fit. Must raise rather than seek past EOF."""
    stream, doc = _make_objstm(n=1, first=128, header=b"4 0 ", payload=b"(x)")
    try:
        with pytest.raises(PDFParseError, match="/First"):
            _read_object_stream_offsets(stream, 11)
    finally:
        doc.close()


def test_object_stream_offset_outside_payload_raises() -> None:
    """A per-object byte offset that points beyond the payload region
    must surface as a parse error — not an out-of-range slice."""
    # Header claims object 4 sits at offset 999 — way past the 3-byte
    # payload. The validator must reject this before we splice anything.
    stream, doc = _make_objstm(n=1, first=8, header=b"4 999   ", payload=b"(x)")
    try:
        with pytest.raises(PDFParseError, match="outside payload"):
            _read_object_stream_offsets(stream, 11)
    finally:
        doc.close()


def test_object_stream_negative_n_raises() -> None:
    """``/N`` cannot be negative — the validator must catch it.

    Wave 1516 mirrors upstream ``PDFObjectStreamParser`` (Apache PDFBox 3.0.7),
    which reads ``/N`` via ``COSStream.getInt`` (sentinel -1 for missing). A
    literal ``/N -1`` is therefore indistinguishable from a MISSING ``/N`` and
    surfaces the same "entry missing" error upstream raises; any other negative
    value (e.g. -2) hits the "Illegal /N entry" branch."""
    stream, doc = _make_objstm(n=-1, first=0, header=b"", payload=b"")
    try:
        with pytest.raises(PDFParseError, match="/N entry missing"):
            _read_object_stream_offsets(stream, 11)
    finally:
        doc.close()

    stream2, doc2 = _make_objstm(n=-2, first=0, header=b"", payload=b"")
    try:
        with pytest.raises(PDFParseError, match="Illegal /N entry"):
            _read_object_stream_offsets(stream2, 11)
    finally:
        doc2.close()


def test_object_stream_negative_first_raises() -> None:
    """``/First`` cannot be negative either — same upstream ``getInt`` -1
    sentinel rule as ``/N``: a literal ``/First -1`` reads as MISSING, while a
    more-negative value (e.g. -2) is the "Illegal /First entry" branch."""
    stream, doc = _make_objstm(n=1, first=-1, header=b"", payload=b"")
    try:
        with pytest.raises(PDFParseError, match="/First entry missing"):
            _read_object_stream_offsets(stream, 11)
    finally:
        doc.close()

    stream2, doc2 = _make_objstm(n=1, first=-2, header=b"", payload=b"")
    try:
        with pytest.raises(PDFParseError, match="Illegal /First entry"):
            _read_object_stream_offsets(stream2, 11)
    finally:
        doc2.close()


def test_object_stream_header_truncated_relative_to_n_is_tolerated() -> None:
    """``/N`` says two pairs but the header only holds one.

    Wave 1503: aligned with upstream ``PDFObjectStreamParser`` (Java
    ``privateReadObjectOffsets``), which reads at most /N pairs but breaks at
    the /First boundary. An inflated /N is bounded by the header region instead
    of raising — only the single ``4 0`` pair is read."""
    # Header text is just "4 0 " — only one pair; /N declares 2.
    stream, doc = _make_objstm(n=2, first=4, header=b"4 0 ", payload=b"(a)(b)")
    try:
        _decoded, pairs, first = _read_object_stream_offsets(stream, 11)
        assert pairs == [(4, 0)]
        assert first == 4
    finally:
        doc.close()
