from __future__ import annotations

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.common import PDStream
from pypdfbox.pdmodel.graphics import PDXObject


def test_xobject_stamps_type_and_subtype_on_cos_stream() -> None:
    stream = COSStream()
    xobject = PDXObject(stream, COSName.get_pdf_name("Custom"))

    assert xobject.get_cos_object() is stream
    assert xobject.get_stream().get_cos_object() is stream
    assert stream.get_name(COSName.TYPE) == "XObject"  # type: ignore[attr-defined]
    assert stream.get_name(COSName.SUBTYPE) == "Custom"  # type: ignore[attr-defined]


def test_xobject_accepts_pd_stream_wrapper() -> None:
    pd_stream = PDStream(input_data=b"body")
    xobject = PDXObject(pd_stream, COSName.get_pdf_name("Image"))
    assert xobject.get_stream() is pd_stream
