from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSStream
from pypdfbox.pdmodel.fdf import FDFAnnotationStamp


def test_default_constructor_sets_subtype() -> None:
    stamp = FDFAnnotationStamp()
    assert stamp.get_cos_object().get_name_as_string("Subtype") == "Stamp"


def test_set_appearance_roundtrip() -> None:
    stamp = FDFAnnotationStamp()
    ap = COSDictionary()
    stamp.set_appearance(ap)
    assert stamp.get_appearance() is ap


def test_set_appearance_none_clears() -> None:
    stamp = FDFAnnotationStamp()
    stamp.set_appearance(COSDictionary())
    stamp.set_appearance(None)
    assert stamp.get_appearance() is None


def test_ensure_normal_appearance_creates() -> None:
    stamp = FDFAnnotationStamp()
    stream = stamp.ensure_normal_appearance()
    assert isinstance(stream, COSStream)
    ap = stamp.get_appearance()
    assert ap is not None
    assert ap.get_dictionary_object("N") is stream


def test_ensure_normal_appearance_idempotent() -> None:
    stamp = FDFAnnotationStamp()
    stream1 = stamp.ensure_normal_appearance()
    stream2 = stamp.ensure_normal_appearance()
    assert stream1 is stream2
