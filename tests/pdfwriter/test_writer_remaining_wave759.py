from __future__ import annotations

import io

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObjectKey,
)
from pypdfbox.pdfwriter import COSWriter
from pypdfbox.pdfwriter.content_stream_writer import ContentStreamWriter
from pypdfbox.pdfwriter.cos_standard_output_stream import COSStandardOutputStream
from pypdfbox.pdfwriter.cos_writer_xref_entry import COSWriterXRefEntry


def test_write_object_alias_emits_indirect_object_frame() -> None:
    sink = io.BytesIO()
    writer = COSWriter(sink)

    writer.write_object(COSInteger.get(7))

    assert b"1 0 obj\n7\nendobj\n" in sink.getvalue()


def test_reject_signed_placeholder_skips_non_array_byte_range() -> None:
    doc = COSDocument()
    sig = COSDictionary()
    sig.set_name(COSName.TYPE, "Sig")  # type: ignore[attr-defined]
    sig.set_int("ByteRange", 1)
    doc.get_object_from_pool(COSObjectKey(7, 0)).set_object(sig)

    COSWriter(io.BytesIO())._reject_signed_with_byterange_placeholder(doc)


def test_fill_gaps_adds_null_entry_when_no_free_numbers() -> None:
    writer = COSWriter(io.BytesIO())

    writer._fill_gaps_with_free_entries()

    assert writer.get_xref_entries() == [COSWriterXRefEntry.get_null_entry()]


def test_format_float_expands_scientific_to_plain_notation() -> None:
    # format_float mirrors PDFBox COSFloat.formatString: a value whose
    # Float.toString carries an exponent is expanded to plain notation via
    # BigDecimal.stripTrailingZeros().toPlainString() — never scientific,
    # never an empty/"-" fallback. 1e-20 round-trips to a long plain string.
    assert COSWriter.format_float(1e-20) == b"0.00000000000000000001"
    # Whole numbers in the [1e-3, 1e7) window keep Float.toString's trailing
    # ".0"; outside it (>= 1e7) the exponent branch strips it.
    assert COSWriter.format_float(1.0) == b"1.0"
    assert COSWriter.format_float(1e7) == b"10000000"


def test_content_stream_inline_image_without_parameters_uses_empty_dict() -> None:
    sink = io.BytesIO()
    writer = ContentStreamWriter(sink)
    from pypdfbox.contentstream import Operator, OperatorName

    writer.write_token(Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE))

    assert sink.getvalue() == b"BI\nID\n\nEI\n"


def test_content_stream_array_none_entry_writes_null() -> None:
    arr = COSArray()
    arr.grow_to_size(1)
    sink = io.BytesIO()

    ContentStreamWriter(sink).write_token(arr)

    assert sink.getvalue() == b"[null ] "


def test_content_stream_dictionary_none_value_is_skipped() -> None:
    dictionary = COSDictionary()
    dictionary.set_int("A", 1)
    dictionary._items[COSName.get_pdf_name("Skip")] = None  # type: ignore[assignment]  # noqa: SLF001
    sink = io.BytesIO()

    ContentStreamWriter(sink).write_token(dictionary)

    assert sink.getvalue() == b"<</A 1 >> "


def test_content_stream_unknown_cosbase_subclass_raises() -> None:
    class UnknownCOS(COSBase):
        def accept(self, visitor: object) -> object:
            return None

    with pytest.raises(OSError, match="Unknown type"):
        ContentStreamWriter(io.BytesIO()).write_token(UnknownCOS())


def test_content_stream_rejects_sink_without_write_methods() -> None:
    with pytest.raises(TypeError, match="write or write_bytes"):
        ContentStreamWriter(object()).write_token(COSInteger.get(1))  # type: ignore[arg-type]


def test_xref_entry_rich_comparisons_return_not_implemented_for_other_type() -> None:
    entry = COSWriterXRefEntry(0, COSObjectKey(1, 0))

    assert entry.__le__(object()) is NotImplemented
    assert entry.__ge__(object()) is NotImplemented


def test_standard_output_stream_rejects_out_of_range_slice() -> None:
    stream = COSStandardOutputStream(io.BytesIO())

    with pytest.raises(ValueError, match="offset/length out of range"):
        stream.write(b"abc", offset=2, length=2)
