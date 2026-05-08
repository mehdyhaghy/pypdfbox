from __future__ import annotations

import io
from typing import Any, cast

from pypdfbox.contentstream import Operator, OperatorName
from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.io import RandomAccessWriteBuffer
from pypdfbox.pdfwriter import ContentStreamWriter, COSWriter


def test_content_stream_writer_skips_value_less_inline_image_parameter() -> None:
    op = Operator.get_operator(OperatorName.BEGIN_INLINE_IMAGE)
    params = COSDictionary()
    params.set_int("W", 1)
    params.set_int("H", 1)
    cast(Any, params)._items[COSName.get_pdf_name("Broken")] = None
    op.set_image_parameters(params)
    op.set_image_data(b"\x00")

    sink = io.BytesIO()
    ContentStreamWriter(sink).write_token(op)

    out = sink.getvalue()
    assert b"/W 1 \n" in out
    assert b"/H 1 \n" in out
    assert b"/Broken" not in out


def test_content_stream_writer_accepts_random_access_write_sink() -> None:
    sink = RandomAccessWriteBuffer()

    ContentStreamWriter(sink).write_token(COSInteger.get(7))

    assert sink.to_bytes() == b"7 "


def test_cos_writer_started_stream_clear_and_has_helpers() -> None:
    with COSWriter(io.BytesIO()) as writer:
        started = writer.get_started_streams()
        assert writer.has_started_streams() is False

        started.add(object())
        assert writer.has_started_streams() is True

        writer.clear_started_streams()
        assert writer.has_started_streams() is False
        assert started == set()
