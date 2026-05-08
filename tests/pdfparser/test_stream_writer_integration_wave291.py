from typing import Any, cast

from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_stream_parser import PDFStreamParser
from pypdfbox.pdfwriter import ContentStreamWriter


class _WriteBytesOnlySink:
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


def test_pdf_stream_parser_tokens_write_to_write_bytes_sink() -> None:
    tokens = PDFStreamParser(
        RandomAccessReadBuffer(b"q 1 0 0 1 72 72 cm (Hi) Tj Q")
    ).parse()
    sink = _WriteBytesOnlySink()

    ContentStreamWriter(cast(Any, sink)).write_tokens(tokens)

    assert bytes(sink.buf) == b"q\n1 0 0 1 72 72 cm\n(Hi) Tj\nQ\n"
