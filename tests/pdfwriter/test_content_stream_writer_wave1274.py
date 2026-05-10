from __future__ import annotations

import io

import pytest

from pypdfbox.contentstream import Operator
from pypdfbox.cos import COSFloat, COSInteger, COSName
from pypdfbox.pdfwriter.content_stream_writer import ContentStreamWriter


def test_write_object_dispatches_cos_integer() -> None:
    """A ``COSBase`` operand goes through the COS serializer — integer
    operand emits ``"<value> "`` (digits + trailing space)."""
    buf = io.BytesIO()
    writer = ContentStreamWriter(buf)
    writer.write_object(COSInteger.get(42))
    assert buf.getvalue() == b"42 "


def test_write_object_dispatches_cos_float() -> None:
    """``COSFloat`` operand uses the writer's float formatter."""
    buf = io.BytesIO()
    writer = ContentStreamWriter(buf)
    writer.write_object(COSFloat(1.5))
    out = buf.getvalue()
    # Trailing space mirrors upstream's ``output.write(SPACE)`` post-amble.
    assert out.endswith(b" ")
    assert b"1.5" in out


def test_write_object_dispatches_operator() -> None:
    """An ``Operator`` argument goes through the operator serializer —
    emits the operator name followed by LF."""
    buf = io.BytesIO()
    writer = ContentStreamWriter(buf)
    writer.write_object(Operator.get_operator("q"))
    assert buf.getvalue() == b"q\n"


def test_write_object_dispatches_cos_name() -> None:
    """A ``COSName`` operand is emitted with the leading ``/`` and a
    trailing space."""
    buf = io.BytesIO()
    writer = ContentStreamWriter(buf)
    writer.write_object(COSName.get_pdf_name("Foo"))
    assert buf.getvalue() == b"/Foo "


def test_write_object_rejects_unknown_type() -> None:
    """Anything other than ``COSBase`` / ``Operator`` raises
    ``OSError`` — same message upstream emits."""
    buf = io.BytesIO()
    writer = ContentStreamWriter(buf)
    with pytest.raises(OSError, match="Unknown type in content stream"):
        writer.write_object(object())
