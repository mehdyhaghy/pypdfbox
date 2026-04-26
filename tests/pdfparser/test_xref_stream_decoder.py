"""Tests for the PDF 1.5+ xref-stream entry decoder (PDF 32000-1 §7.5.8).

Synthesises minimal PDFs with hand-built xref streams. Each fixture is
small enough to reason about end-to-end so a parser regression is easy
to localise.
"""

from __future__ import annotations

import zlib

import pytest

from pypdfbox.cos import COSObjectKey, COSStream, COSString
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParser
from pypdfbox.pdfparser.parse_error import PDFParseError

# --------------------------------------------------------------- helpers


def _pack_record(type_byte: int, field2: int, field3: int, w2: int, w3: int = 2) -> bytes:
    """Pack one xref-stream record under /W [1 w2 w3]."""
    return (
        type_byte.to_bytes(1, "big")
        + field2.to_bytes(w2, "big")
        + field3.to_bytes(w3, "big")
    )


def _build_xref_stream_pdf(
    objects: list[bytes],
    xref_records: bytes,
    *,
    extra_dict_entries: bytes = b"",
    index_array: bytes | None = None,
    encode: bool = False,
    w: tuple[int, int, int] = (1, 4, 2),
    version: bytes = b"1.5",
) -> bytes:
    """Build a tiny PDF whose xref is a single xref stream object.

    ``objects`` are the indirect-object bodies in order (object numbers
    1..N). ``xref_records`` is the raw entry-stream bytes already packed
    per ``/W``. ``index_array`` overrides the default ``[0 size]``.
    """
    out = bytearray()
    out += b"%PDF-" + version + b"\n"
    offsets: list[int] = [0]  # object 0 is the free root
    for body in objects:
        offsets.append(len(out))
        out += body
        if not body.endswith(b"\n"):
            out += b"\n"
    # Object N+1 is the xref stream itself.
    xref_obj_num = len(offsets)
    xref_obj_offset = len(out)
    body = zlib.compress(xref_records) if encode else xref_records
    size = xref_obj_num + 1  # objects 0..N + xref-stream object
    if index_array is None:
        index_bytes = f"[ 0 {size} ]".encode("ascii")
    else:
        index_bytes = index_array
    dict_lines = [
        b"<< /Type /XRef",
        f"/Size {size}".encode("ascii"),
        b"/Index " + index_bytes,
        f"/W [ {w[0]} {w[1]} {w[2]} ]".encode("ascii"),
        f"/Length {len(body)}".encode("ascii"),
    ]
    if encode:
        dict_lines.append(b"/Filter /FlateDecode")
    if extra_dict_entries:
        dict_lines.append(extra_dict_entries)
    dict_lines.append(b">>")
    obj_header = f"{xref_obj_num} 0 obj\n".encode("ascii")
    out += obj_header + b"\n".join(dict_lines)
    out += b"\nstream\n"
    out += body
    out += b"\nendstream\nendobj\n"
    out += b"startxref\n"
    out += str(xref_obj_offset).encode("ascii")
    out += b"\n%%EOF"
    return bytes(out)


# --------------------------------------------------------------- basic decode


def test_xref_stream_with_uncompressed_in_use_entries() -> None:
    """Two objects pointed at by /W [1 4 2] in-use records."""
    obj1 = b"1 0 obj\n42\nendobj"
    obj2 = b"2 0 obj\n(hello)\nendobj"
    # Compute object offsets manually so we can pack them into the xref.
    header_len = len(b"%PDF-1.5\n")
    obj1_off = header_len
    obj2_off = obj1_off + len(obj1) + 1  # +1 for the trailing newline
    records = (
        _pack_record(0, 0, 65535, w2=4)  # object 0 free
        + _pack_record(1, obj1_off, 0, w2=4)
        + _pack_record(1, obj2_off, 0, w2=4)
        + _pack_record(1, 0, 0, w2=4)  # placeholder for the xref-stream itself
    )
    pdf = _build_xref_stream_pdf([obj1, obj2], records)
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    assert doc.has_object(COSObjectKey(1, 0))
    assert doc.has_object(COSObjectKey(2, 0))
    body1 = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
    body2 = doc.get_object_from_pool(COSObjectKey(2, 0)).get_object()
    from pypdfbox.cos import COSInteger  # noqa: PLC0415

    assert isinstance(body1, COSInteger) and body1.value == 42
    assert isinstance(body2, COSString) and body2.get_bytes() == b"hello"


def test_xref_stream_index_subsection_split() -> None:
    """/Index lets the table cover non-contiguous object-number ranges
    (e.g. ``[0 1 5 2]`` = object 0, then objects 5 and 6)."""
    # Build objects with gaps.
    obj5 = b"5 0 obj\n(five)\nendobj"
    obj6 = b"6 0 obj\n(six)\nendobj"
    header_len = len(b"%PDF-1.5\n")
    obj5_off = header_len
    obj6_off = obj5_off + len(obj5) + 1
    records = (
        _pack_record(0, 0, 65535, w2=4)
        + _pack_record(1, obj5_off, 0, w2=4)
        + _pack_record(1, obj6_off, 0, w2=4)
    )
    pdf = _build_xref_stream_pdf(
        [obj5, obj6],
        records,
        index_array=b"[ 0 1 5 2 ]",
    )
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    assert not doc.has_object(COSObjectKey(0, 65535))  # free entry skipped
    assert doc.has_object(COSObjectKey(5, 0))
    assert doc.has_object(COSObjectKey(6, 0))
    body5 = doc.get_object_from_pool(COSObjectKey(5, 0)).get_object()
    body6 = doc.get_object_from_pool(COSObjectKey(6, 0)).get_object()
    assert isinstance(body5, COSString) and body5.get_bytes() == b"five"
    assert isinstance(body6, COSString) and body6.get_bytes() == b"six"


def test_xref_stream_w1_zero_defaults_to_in_use() -> None:
    """When ``w1 == 0`` the type field is implicit (= 1, in-use)."""
    obj1 = b"1 0 obj\n7\nendobj"
    header_len = len(b"%PDF-1.5\n")
    obj1_off = header_len
    # /W [0 4 2] — no type byte; field2 width 4, field3 width 2.
    records = (
        b"\x00" * 6  # object 0 (offset+gen all zeros)
        + obj1_off.to_bytes(4, "big") + b"\x00\x00"
        + b"\x00" * 6  # placeholder for xref-stream object itself
    )
    pdf = _build_xref_stream_pdf([obj1], records, w=(0, 4, 2))
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    # Object 1 is in-use — the implicit type 1 must apply.
    assert doc.has_object(COSObjectKey(1, 0))
    from pypdfbox.cos import COSInteger  # noqa: PLC0415

    body = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
    assert isinstance(body, COSInteger) and body.value == 7


def test_xref_stream_with_flate_filter_decodes_body() -> None:
    """Real-world xref streams are nearly always /FlateDecode-compressed."""
    obj1 = b"1 0 obj\n123\nendobj"
    header_len = len(b"%PDF-1.5\n")
    obj1_off = header_len
    records = (
        _pack_record(0, 0, 65535, w2=4)
        + _pack_record(1, obj1_off, 0, w2=4)
        + _pack_record(1, 0, 0, w2=4)  # placeholder for the xref-stream itself
    )
    pdf = _build_xref_stream_pdf([obj1], records, encode=True)
    doc = PDFParser(RandomAccessReadBuffer(pdf)).parse()
    assert doc.has_object(COSObjectKey(1, 0))


# --------------------------------------------------------------- /Prev chain


def test_xref_stream_prev_chain_walks_to_older_section() -> None:
    """Two xref streams chained via /Prev — the newer must override the
    older for the shared key while older-only entries remain visible."""
    out = bytearray(b"%PDF-1.5\n")
    # Old section: object 1 -> "(old)"
    obj1_v1 = b"1 0 obj\n(old)\nendobj"
    obj1_v1_off = len(out)
    out += obj1_v1 + b"\n"
    # First xref stream describes objects 0..2 where object 2 is the
    # xref stream itself (object 1 is the only payload).
    xref1_obj_num = 2
    xref1_off = len(out)
    records1 = (
        _pack_record(0, 0, 65535, w2=4)
        + _pack_record(1, obj1_v1_off, 0, w2=4)
        + _pack_record(1, 0, 0, w2=4)
    )
    dict1 = (
        b"2 0 obj\n<< /Type /XRef /Size 3 /Index [ 0 3 ]"
        b" /W [ 1 4 2 ] /Length "
        + str(len(records1)).encode("ascii")
        + b" >>\nstream\n"
        + records1
        + b"\nendstream\nendobj\n"
    )
    out += dict1
    out += b"startxref\n" + str(xref1_off).encode("ascii") + b"\n%%EOF\n"
    # New incremental section: object 1 -> "(new)" + a new xref stream
    # that points at the new body and chains /Prev to the old xref.
    obj1_v2_off = len(out)
    out += b"1 0 obj\n(new)\nendobj\n"
    xref2_obj_num = 3
    xref2_off = len(out)
    records2 = (
        _pack_record(0, 0, 65535, w2=4)
        + _pack_record(1, obj1_v2_off, 0, w2=4)
        + _pack_record(1, xref1_off, 0, w2=4)
        + _pack_record(1, 0, 0, w2=4)
    )
    dict2 = (
        b"3 0 obj\n<< /Type /XRef /Size 4 /Index [ 0 4 ]"
        b" /W [ 1 4 2 ] /Prev "
        + str(xref1_off).encode("ascii")
        + b" /Length "
        + str(len(records2)).encode("ascii")
        + b" >>\nstream\n"
        + records2
        + b"\nendstream\nendobj\n"
    )
    out += dict2
    out += b"startxref\n" + str(xref2_off).encode("ascii") + b"\n%%EOF"
    doc = PDFParser(RandomAccessReadBuffer(bytes(out))).parse()
    body = doc.get_object_from_pool(COSObjectKey(1, 0)).get_object()
    assert isinstance(body, COSString) and body.get_bytes() == b"new"
    # The /Prev chain must have introduced the older xref-stream object
    # (number 2 above) into the pool too.
    assert doc.has_object(COSObjectKey(2, 0))


# --------------------------------------------------------------- encryption


def test_encrypted_xref_stream_with_handler_decodes_body() -> None:
    """Hybrid layout: a traditional xref TABLE (newest section, parsed
    first) carries /Encrypt + the entry for the /Encrypt object; its
    trailer chains /Prev to an older xref STREAM whose body is encrypted
    on disk. By the time the xref-stream body is decoded the early
    handler is in place — so the cipher pass must run BEFORE the entries
    are unpacked.

    This is the wave-10 ``set_password`` surface in action: without it
    the records would be deciphered as garbage and the second-section
    pool entries would never appear.
    """
    pytest.importorskip("pypdfbox.pdmodel.encryption.standard_security_handler")
    from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption  # noqa: PLC0415
    from pypdfbox.pdmodel.encryption.standard_protection_policy import (  # noqa: PLC0415
        StandardProtectionPolicy,
    )
    from pypdfbox.pdmodel.encryption.standard_security_handler import (  # noqa: PLC0415
        StandardSecurityHandler,
    )
    from pypdfbox.pdmodel.encryption.access_permission import (  # noqa: PLC0415
        AccessPermission,
    )

    # Build the standard handler so we can encrypt the xref-stream body.
    policy = StandardProtectionPolicy(
        owner_password="hunter2",
        user_password="hunter2",
        permissions=AccessPermission(),
    )
    policy.set_encryption_key_length(128)
    policy.set_prefer_aes(False)
    handler = StandardSecurityHandler(policy)
    captured: dict[str, PDEncryption] = {}

    class _Capture:
        def set_encryption_dictionary(self, e: PDEncryption) -> None:
            captured["enc"] = e

    handler.prepare_document(_Capture())
    enc = captured["enc"]

    out = bytearray(b"%PDF-1.5\n")
    # Object 1: a payload string referenced from the older xref stream.
    obj1_off = len(out)
    out += b"1 0 obj\n(payload)\nendobj\n"
    # Object 2: the encrypted xref stream (older section).
    records = (
        _pack_record(0, 0, 65535, w2=4)
        + _pack_record(1, obj1_off, 0, w2=4)
        + _pack_record(1, 0, 0, w2=4)  # the xref stream itself, offset filled below
    )
    # Encrypt records under the handler's key for (2, 0).
    enc_records = handler.encrypt_stream(records, 2, 0)
    xref_stream_off = len(out)
    out += (
        b"2 0 obj\n<< /Type /XRef /Size 3 /Index [ 0 3 ]"
        b" /W [ 1 4 2 ] /Length "
        + str(len(enc_records)).encode("ascii")
        + b" >>\nstream\n"
        + enc_records
        + b"\nendstream\nendobj\n"
    )
    out += b"startxref\n" + str(xref_stream_off).encode("ascii") + b"\n%%EOF\n"
    # Object 3: /Encrypt dict (newest section — appears in incremental
    # update so the traditional xref table can advertise its offset
    # before the older encrypted xref stream is reached via /Prev).
    enc_obj_off = len(out)
    enc_lines = [b"3 0 obj\n<<"]
    enc_lines.append(b"/Filter /Standard")
    enc_lines.append(f"/V {enc.get_v()}".encode("ascii"))
    enc_lines.append(f"/R {enc.get_revision()}".encode("ascii"))
    enc_lines.append(f"/Length {enc.get_length()}".encode("ascii"))
    enc_lines.append(f"/P {enc.get_p()}".encode("ascii"))
    enc_lines.append(b"/O <" + (enc.get_o() or b"").hex().upper().encode("ascii") + b">")
    enc_lines.append(b"/U <" + (enc.get_u() or b"").hex().upper().encode("ascii") + b">")
    enc_lines.append(b">>\nendobj\n")
    out += b"\n".join(enc_lines)
    # Traditional xref table — newest section. Lists object 3 and chains
    # /Prev to the encrypted xref-stream offset above.
    table_off = len(out)
    out += b"xref\n0 4\n0000000000 65535 f \n"
    out += b"0000000000 00000 f \n"  # object 1 free in this section (older holds it)
    out += b"0000000000 00000 f \n"  # object 2 free in this section (older holds it)
    out += f"{enc_obj_off:010d} 00000 n \n".encode("ascii")
    out += (
        b"trailer\n<< /Size 4 /Root 1 0 R /Encrypt 3 0 R"
        b" /ID [<"
        + (b"00" * 16)
        + b"> <"
        + (b"00" * 16)
        + b">] /Prev "
        + str(xref_stream_off).encode("ascii")
        + b" >>\n"
    )
    out += b"startxref\n" + str(table_off).encode("ascii") + b"\n%%EOF"

    parser = PDFParser(RandomAccessReadBuffer(bytes(out)))
    parser.set_password("hunter2")
    doc = parser.parse()
    assert parser.get_security_handler() is not None
    # Object 1 lived only in the encrypted xref-stream section. If the
    # body was deciphered correctly its entry now exists in the pool.
    assert doc.has_object(COSObjectKey(1, 0))


# --------------------------------------------------------------- malformed


def test_xref_stream_w_field_widths_must_sum_above_zero() -> None:
    """``/W [0 0 0]`` is nonsensical — must surface as PDFParseError."""
    pdf = (
        b"%PDF-1.5\n"
        b"1 0 obj\n<< /Type /XRef /Size 1 /W [ 0 0 0 ] /Length 0 >>\n"
        b"stream\n\nendstream\nendobj\n"
        b"startxref\n9\n%%EOF"
    )
    with pytest.raises(PDFParseError):
        PDFParser(RandomAccessReadBuffer(pdf)).parse()


def test_xref_stream_records_truncated_relative_to_index() -> None:
    """If the body is shorter than ``/Index`` declares, fail loudly."""
    pdf = (
        b"%PDF-1.5\n"
        b"1 0 obj\n<< /Type /XRef /Size 5 /Index [ 0 5 ] "
        b"/W [ 1 4 2 ] /Length 7 >>\nstream\n"
        + b"\x01\x00\x00\x00\x09\x00\x00"
        + b"\nendstream\nendobj\n"
        b"startxref\n9\n%%EOF"
    )
    with pytest.raises(PDFParseError):
        PDFParser(RandomAccessReadBuffer(pdf)).parse()
