from __future__ import annotations

import io

import pytest

from pypdfbox.pdfwriter.cos_standard_output_stream import COSStandardOutputStream


def test_write_int_rejects_bool_and_non_int_values() -> None:
    out = COSStandardOutputStream(io.BytesIO())

    with pytest.raises(TypeError, match="integer value must be an int"):
        out.write_int(True)
    with pytest.raises(TypeError, match="integer value must be an int"):
        out.write_int("12")  # type: ignore[arg-type]

    assert out.get_position() == 0


def test_write_byte_rejects_bool_without_writing() -> None:
    sink = io.BytesIO()
    out = COSStandardOutputStream(sink)

    with pytest.raises(TypeError, match="byte value must be an int"):
        out.write_byte(False)

    assert sink.getvalue() == b""
    assert out.get_position() == 0
