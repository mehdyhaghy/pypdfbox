from __future__ import annotations

from pypdfbox.cos import COSString
from pypdfbox.io import RandomAccessWriteBuffer
from pypdfbox.pdfwriter import ContentStreamWriter


def test_string_token_writes_to_random_access_write_buffer() -> None:
    sink = RandomAccessWriteBuffer()

    ContentStreamWriter(sink).write_token(COSString(b"a(b)c"))

    assert sink.to_bytes() == b"(a\\(b\\)c) "
