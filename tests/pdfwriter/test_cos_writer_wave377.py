from __future__ import annotations

import io
from typing import Any, cast

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObjectKey,
    COSStream,
)
from pypdfbox.io import RandomAccessWriteBuffer
from pypdfbox.pdfwriter import COSWriter, COSWriterXRefEntry
from pypdfbox.pdfwriter.cos_writer import _ceil_log256, _pack_unsigned


def test_wave377_writer_accepts_random_access_write_buffer_sink() -> None:
    sink = RandomAccessWriteBuffer()

    with COSWriter(sink) as writer:
        writer.write_header("1.6")

    assert sink.to_bytes().startswith(b"%PDF-1.6\n%\xf6\xe4\xfc\xdf\n")


def test_wave377_write_trailer_requires_document() -> None:
    with COSWriter(io.BytesIO()) as writer, pytest.raises(ValueError):
        writer.write_trailer()


def test_wave377_write_trailer_strips_stale_incremental_keys() -> None:
    doc = COSDocument()
    trailer = COSDictionary()
    trailer.set_int(COSName.PREV, 123)  # type: ignore[attr-defined]
    trailer.set_int(COSName.get_pdf_name("XRefStm"), 456)
    doc.set_trailer(trailer)

    sink = io.BytesIO()
    with COSWriter(sink) as writer:
        writer.write_trailer(doc)

    out = sink.getvalue()
    assert b"trailer\n" in out
    assert b"/Size 1" in out
    assert b"/Prev" not in out
    assert b"/XRefStm" not in out
    assert out.endswith(b"startxref\n0\n%%EOF\n")


def test_wave377_xref_gap_fill_links_sparse_free_entries() -> None:
    sink = io.BytesIO()
    with COSWriter(sink) as writer:
        writer.add_xref_entry(
            COSWriterXRefEntry(
                offset=20,
                key=COSObjectKey(2, 0),
                obj=COSDictionary(),
            )
        )
        writer.add_xref_entry(
            COSWriterXRefEntry(
                offset=50,
                key=COSObjectKey(5, 0),
                obj=COSDictionary(),
            )
        )
        writer.write_xref()

    out = sink.getvalue()
    assert out.startswith(b"xref\n0 6\n")
    assert b"0000000001 65535 f\r\n" in out
    assert b"0000000003 65535 f\r\n" in out
    assert b"0000000020 00000 n\r\n" in out
    assert b"0000000004 65535 f\r\n" in out
    assert b"0000000000 65535 f\r\n" in out
    assert b"0000000050 00000 n\r\n" in out


def test_wave377_unsigned_xref_stream_helpers_cover_boundaries() -> None:
    assert _ceil_log256(-1) == 1
    assert _ceil_log256(0) == 1
    assert _ceil_log256(255) == 1
    assert _ceil_log256(256) == 2
    assert _ceil_log256(65535) == 2
    assert _ceil_log256(65536) == 3

    assert _pack_unsigned(0, 1) == b"\x00"
    assert _pack_unsigned(255, 1) == b"\xff"
    assert _pack_unsigned(256, 2) == b"\x01\x00"
    with pytest.raises(ValueError):
        _pack_unsigned(-1, 1)
    with pytest.raises(ValueError):
        _pack_unsigned(1, 0)


def test_wave377_build_int_ranges_sorts_and_deduplicates() -> None:
    assert COSWriter._build_int_ranges([5, 2, 4, 2, 3, 10]) == [
        (2, 4),
        (10, 1),
    ]
    assert COSWriter._build_int_ranges([]) == []


def test_wave377_array_emits_eol_after_every_tenth_item() -> None:
    arr = COSArray(COSInteger.get(i) for i in range(11))
    sink = io.BytesIO()

    with COSWriter(sink) as writer:
        writer.visit_from_array(arr)

    assert sink.getvalue() == b"[0 1 2 3 4 5 6 7 8 9\n10]\n"


def test_wave377_dictionary_visitor_skips_none_entries() -> None:
    dictionary = COSDictionary()
    dictionary.set_int("Present", 7)
    cast(Any, dictionary)._items[COSName.get_pdf_name("Missing")] = None
    sink = io.BytesIO()

    with COSWriter(sink) as writer:
        writer.visit_from_dictionary(dictionary)

    out = sink.getvalue()
    assert b"/Present 7" in out
    assert b"/Missing" not in out


def test_wave377_is_packable_excludes_special_objects() -> None:
    with COSWriter(io.BytesIO()) as writer:
        stream = COSStream()
        assert writer._is_packable(stream, COSObjectKey(1, 0)) is False

        encrypt = COSDictionary()
        writer._encrypt_dict_id = id(encrypt)
        assert writer._is_packable(encrypt, COSObjectKey(2, 0)) is False

        signature = COSDictionary()
        signature.set_item(COSName.TYPE, COSName.get_pdf_name("Sig"))  # type: ignore[attr-defined]
        assert writer._is_packable(signature, COSObjectKey(3, 0)) is False

        timestamp = COSDictionary()
        timestamp.set_item(COSName.TYPE, COSName.get_pdf_name("DocTimeStamp"))  # type: ignore[attr-defined]
        assert writer._is_packable(timestamp, COSObjectKey(4, 0)) is False

        regular = COSDictionary()
        assert writer._is_packable(regular, COSObjectKey(5, 0)) is True
