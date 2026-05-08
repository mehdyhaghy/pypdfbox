from __future__ import annotations

import io

import pytest

from pypdfbox.pdfwriter.cos_standard_output_stream import COSStandardOutputStream


def test_wave320_write_rejects_bool_offset_without_writing() -> None:
    sink = io.BytesIO()
    out = COSStandardOutputStream(sink)

    with pytest.raises(TypeError, match="offset must be an int"):
        out.write(b"abc", offset=True)

    assert sink.getvalue() == b""
    assert out.get_position() == 0


def test_wave320_write_rejects_bool_length_without_writing() -> None:
    sink = io.BytesIO()
    out = COSStandardOutputStream(sink)

    with pytest.raises(TypeError, match="length must be an int"):
        out.write(b"abc", length=False)

    assert sink.getvalue() == b""
    assert out.get_position() == 0


def test_wave320_constructor_rejects_bool_position() -> None:
    with pytest.raises(TypeError, match="position must be an int"):
        COSStandardOutputStream(io.BytesIO(), position=True)
