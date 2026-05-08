from typing import Any, cast

import pytest

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_stream_parser import PDFStreamParser
from pypdfbox.pdfwriter import ContentStreamWriter


class _WriteBytesSink:
    """Sink with a malformed ``write`` attribute and a valid ``write_bytes``."""

    write = None

    def __init__(self) -> None:
        self.buf = bytearray()

    def write_bytes(
        self,
        data: bytes | bytearray | memoryview,
        offset: int = 0,
        length: int | None = None,
    ) -> None:
        if length is None:
            length = len(data) - offset
        self.buf.extend(bytes(memoryview(data)[offset : offset + length]))


def test_content_stream_writer_string_adapter_uses_callable_write_bytes() -> None:
    tokens = PDFStreamParser(
        RandomAccessReadBuffer(b"BT (Hello) Tj ET")
    ).parse()
    sink = _WriteBytesSink()

    ContentStreamWriter(cast(Any, sink)).write_tokens(tokens)

    assert bytes(sink.buf) == b"BT\n(Hello) Tj\nET\n"


def test_content_stream_writer_string_adapter_rejects_unwritable_sink() -> None:
    class _BrokenSink:
        write = None
        write_bytes = None

    with pytest.raises(TypeError, match="write or write_bytes"):
        ContentStreamWriter(cast(Any, _BrokenSink())).write_tokens(
            PDFStreamParser(RandomAccessReadBuffer(b"(Hello) Tj")).parse()
        )
