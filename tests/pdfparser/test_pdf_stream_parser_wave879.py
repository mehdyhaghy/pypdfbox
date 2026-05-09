from __future__ import annotations

import tests.pdfparser.test_pdf_stream_parser_wave526 as wave526
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdmodel import PDRectangle


def test_wave879_bytes_content_stream_helper_exposes_all_accessors() -> None:
    stream = wave526._BytesContentStream(b"1 2 m")

    contents = stream.get_contents()
    assert contents.read() == b"1 2 m"

    random_access = stream.get_contents_for_random_access()
    assert isinstance(random_access, RandomAccessReadBuffer)
    assert random_access.read() == ord("1")

    parsing_access = stream.get_contents_for_stream_parsing()
    assert isinstance(parsing_access, RandomAccessReadBuffer)
    assert parsing_access.read() == ord("1")

    assert stream.get_resources() is None
    assert isinstance(stream.get_bbox(), PDRectangle)
    assert stream.get_matrix() is None
