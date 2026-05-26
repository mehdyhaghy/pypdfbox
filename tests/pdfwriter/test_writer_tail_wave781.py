from __future__ import annotations

import io

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObjectKey,
)
from pypdfbox.pdfwriter import COSWriter
from pypdfbox.pdfwriter.cos_standard_output_stream import COSStandardOutputStream
from pypdfbox.pdfwriter.cos_writer_xref_entry import COSWriterXRefEntry


def test_wave781_write_object_alias_records_xref_and_body() -> None:
    sink = io.BytesIO()

    with COSWriter(sink) as writer:
        writer.write_object(COSInteger.get(781))

    assert b"1 0 obj\n781\nendobj\n" in sink.getvalue()
    assert writer.get_xref_entries()[0].key == COSObjectKey(1, 0)


def test_wave781_signature_scan_skips_malformed_byte_range() -> None:
    nonsignature = COSDictionary()
    sig = COSDictionary()
    sig.set_item(COSName.TYPE, COSName.get_pdf_name("Sig"))
    sig.set_item(COSName.get_pdf_name("ByteRange"), COSArray.of_cos_integers([0, 1, 2]))

    cos_doc = COSDocument()
    cos_doc.get_object_from_pool(COSObjectKey(7, 0)).set_object(sig)
    cos_doc.get_object_from_pool(COSObjectKey(8, 0)).set_object(nonsignature)

    COSWriter(io.BytesIO())._reject_signed_with_byterange_placeholder(cos_doc)


def test_wave781_fill_gaps_without_free_numbers_adds_null_entry() -> None:
    writer = COSWriter(io.BytesIO())

    writer._fill_gaps_with_free_entries()

    assert writer.get_xref_entries() == [COSWriterXRefEntry.get_null_entry()]


def test_wave781_float_formatter_signed_zero_round_trips() -> None:
    # PDFBox's COSFloat.formatString preserves Float.toString's signed zero:
    # +0.0 -> "0.0", -0.0 -> "-0.0". (The float32-shortest-digit path has no
    # empty/"-" fallback to guard against.)
    assert COSWriter.format_float(0.0) == b"0.0"
    assert COSWriter.format_float(-0.0) == b"-0.0"


def test_wave781_xref_entry_non_entry_rich_comparisons_return_notimplemented() -> None:
    entry = COSWriterXRefEntry(offset=0, key=COSObjectKey(1, 0))

    assert entry.__lt__(object()) is NotImplemented
    assert entry.__le__(object()) is NotImplemented
    assert entry.__gt__(object()) is NotImplemented
    assert entry.__ge__(object()) is NotImplemented


def test_wave781_standard_output_rejects_offset_length_past_buffer() -> None:
    out = COSStandardOutputStream(io.BytesIO())

    with pytest.raises(ValueError, match="offset/length out of range"):
        out.write(b"abc", offset=3, length=1)
