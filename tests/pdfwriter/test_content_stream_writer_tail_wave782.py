from __future__ import annotations

import io

import pytest

from pypdfbox.contentstream import Operator, OperatorName
from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.io import RandomAccessWriteBuffer
from pypdfbox.pdfwriter import ContentStreamWriter


def test_wave782_inline_image_without_parameters_emits_empty_block() -> None:
    sink = io.BytesIO()
    inline = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE)

    ContentStreamWriter(sink).write_token(inline)

    assert sink.getvalue() == b"BI\nID\n\nEI\n"


def test_wave782_inline_image_skips_value_less_parameter() -> None:
    sink = io.BytesIO()
    inline = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE)
    params = COSDictionary()
    params.set_int("W", 2)
    params._items[COSName.get_pdf_name("DropMe")] = None  # noqa: SLF001
    inline.set_image_parameters(params)
    inline.set_image_data(b"\x01\x02")

    ContentStreamWriter(sink).write_token(inline)

    assert sink.getvalue() == b"BI\n/W 2 \nID\n\x01\x02\nEI\n"


def test_wave782_array_none_entry_writes_null_operand() -> None:
    arr = COSArray([COSInteger.get(1)])
    arr.grow_to_size(3)

    sink = io.BytesIO()
    ContentStreamWriter(sink).write_token(arr)

    assert sink.getvalue() == b"[1 null null ] "


def test_wave782_dictionary_value_less_entry_is_omitted() -> None:
    dictionary = COSDictionary()
    dictionary.set_string("Keep", "yes")
    dictionary._items[COSName.get_pdf_name("Drop")] = None  # noqa: SLF001

    sink = io.BytesIO()
    ContentStreamWriter(sink).write_token(dictionary)

    assert sink.getvalue() == b"<</Keep (yes) >> "


def test_wave782_unknown_cosbase_subclass_raises_ioerror() -> None:
    class UnknownCOS(COSBase):
        def accept(self, visitor: object) -> object:
            return None

    with pytest.raises(OSError, match="Unknown type"):
        ContentStreamWriter(io.BytesIO()).write_token(UnknownCOS())


def test_wave782_unwritable_sink_raises_typeerror() -> None:
    with pytest.raises(TypeError, match="write or write_bytes"):
        ContentStreamWriter(object()).write_token(COSNull.NULL)  # type: ignore[arg-type]


def test_wave782_random_access_write_buffer_handles_raw_and_string_paths() -> None:
    sink = RandomAccessWriteBuffer()
    writer = ContentStreamWriter(sink)

    writer.write_tokens(
        COSString(b"Hi"),
        COSInteger.get(2),
        Operator.get_operator(OperatorName.SHOW_TEXT),
    )

    assert sink.to_bytes() == b"(Hi) 2 Tj\n\n"
