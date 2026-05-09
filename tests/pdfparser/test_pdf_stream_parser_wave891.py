from __future__ import annotations

import io

import tests.pdfparser.test_pdf_stream_parser_wave430 as wave430
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdmodel import PDRectangle, PDResources


def test_wave891_bytes_content_stream_helper_accessors() -> None:
    resources = PDResources()
    stream = wave430._BytesContentStream(b"q 1 2 m", resources)

    contents = stream.get_contents()
    assert isinstance(contents, io.BytesIO)
    assert contents.read() == b"q 1 2 m"

    random_access = stream.get_contents_for_random_access()
    assert isinstance(random_access, RandomAccessReadBuffer)
    assert random_access.read() == ord("q")

    bbox = stream.get_bbox()
    assert isinstance(bbox, PDRectangle)
    assert bbox.lower_left_x == 0.0
    assert bbox.upper_right_y == 1.0

    assert stream.get_matrix() is None

