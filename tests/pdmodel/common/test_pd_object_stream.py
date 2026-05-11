from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.common import PDObjectStream
from pypdfbox.pdmodel.pd_document import PDDocument


def test_wrap_existing_cos_stream() -> None:
    cs = COSStream()
    obj = PDObjectStream(cs)
    assert obj.get_cos_object() is cs


def test_create_stream_via_document() -> None:
    with PDDocument() as doc:
        obj = PDObjectStream.create_stream(doc)
        assert obj.get_type() == "ObjStm"


def test_number_of_objects_roundtrip() -> None:
    obj = PDObjectStream(COSStream())
    assert obj.get_number_of_objects() == 0
    obj.set_number_of_objects(7)
    assert obj.get_number_of_objects() == 7


def test_first_byte_offset_roundtrip() -> None:
    obj = PDObjectStream(COSStream())
    assert obj.get_first_byte_offset() == 0
    obj.set_first_byte_offset(42)
    assert obj.get_first_byte_offset() == 42


def test_get_extends_when_absent() -> None:
    obj = PDObjectStream(COSStream())
    assert obj.get_extends() is None


def test_set_extends_roundtrip() -> None:
    obj = PDObjectStream(COSStream())
    parent = PDObjectStream(COSStream())
    obj.set_extends(parent)
    extends = obj.get_extends()
    assert extends is not None
    assert extends.get_cos_object() is parent.get_cos_object()


def test_set_extends_none_clears() -> None:
    obj = PDObjectStream(COSStream())
    parent = PDObjectStream(COSStream())
    obj.set_extends(parent)
    obj.set_extends(None)
    assert obj.get_extends() is None


def test_get_type_when_unset() -> None:
    obj = PDObjectStream(COSStream())
    assert obj.get_type() is None
