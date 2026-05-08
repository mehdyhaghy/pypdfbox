from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSObject, COSStream
from pypdfbox.pdmodel.common.function import (
    PDFunction,
    PDFunctionType0,
    PDFunctionType2,
    PDFunctionTypeIdentity,
)


def test_create_dereferences_indirect_dictionary_function() -> None:
    raw = COSDictionary()
    raw.set_int("FunctionType", PDFunction.FUNCTION_TYPE_EXPONENTIAL)
    ref = COSObject(1, 0, resolved=raw)

    fn = PDFunction.create(ref)

    assert isinstance(fn, PDFunctionType2)
    assert fn.get_cos_object() is raw


def test_create_dereferences_indirect_stream_function() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", PDFunction.FUNCTION_TYPE_SAMPLED)
    ref = COSObject(2, 0, resolved=raw)

    fn = PDFunction.create(ref)

    assert isinstance(fn, PDFunctionType0)
    assert fn.get_cos_object() is raw
    assert fn.is_stream_backed() is True


def test_create_dereferences_indirect_identity_name() -> None:
    ref = COSObject(3, 0, resolved=COSName.get_pdf_name("Identity"))

    fn = PDFunction.create(ref)

    assert isinstance(fn, PDFunctionTypeIdentity)
    assert fn.eval([0.1, 0.2]) == [0.1, 0.2]


def test_create_unresolved_indirect_reference_returns_none() -> None:
    ref = COSObject(4, 0)

    assert PDFunction.create(ref) is None
