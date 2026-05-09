from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName, COSNull, COSObject, COSStream
from pypdfbox.pdmodel.common import PDMatrix, PDMetadata
from pypdfbox.pdmodel.common.filespecification import PDFileSpecification
from pypdfbox.pdmodel.common.function import PDFunction, PDFunctionTypeIdentity
from pypdfbox.pdmodel.common.pdfdoc_encoding import PDFDocEncoding


def test_wave837_file_specification_indirect_null_returns_none() -> None:
    ref = COSObject(837, resolved=COSNull.NULL)

    assert PDFileSpecification.create_fs(ref) is None


def test_wave837_identity_function_keeps_input_and_range_noop() -> None:
    function = PDFunction.create(COSName.get_pdf_name("Identity"))

    assert isinstance(function, PDFunctionTypeIdentity)
    assert function.eval([0.25, 1.5]) == [0.25, 1.5]
    assert function.eval_function([2.0]) == [2.0]
    assert function.get_range_values() is None
    assert function.clip_to_range([-10.0, 10.0]) == [-10.0, 10.0]
    assert str(function) == "FunctionTypeIdentity"


def test_wave837_function_scalar_clip_normalizes_swapped_bounds() -> None:
    assert PDFunction.clip_value_to_range(-5.0, 10.0, 0.0) == 0.0
    assert PDFunction.clip_value_to_range(15.0, 10.0, 0.0) == 10.0
    assert PDFunction.clip_value_to_range(5.0, 10.0, 0.0) == 5.0


def test_wave837_matrix_create_matrix_falls_back_for_malformed_arrays() -> None:
    too_short = COSArray([COSFloat(1.0)])
    non_number = COSArray([COSFloat(1.0)] * 5 + [COSName.A])

    assert PDMatrix.create_matrix(too_short).is_identity() is True
    assert PDMatrix.create_matrix(non_number).is_identity() is True


def test_wave837_metadata_wrapped_stream_is_not_auto_tagged() -> None:
    stream = COSStream()
    metadata = PDMetadata(stream)

    assert metadata.get_type() is None
    assert metadata.get_subtype() is None
    assert metadata.is_metadata_stream() is False

    with pytest.raises(TypeError, match="COSStream, input_data"):
        PDMetadata(stream, b"<rdf:RDF/>")


def test_wave837_pdfdoc_encoding_static_facade_tail_values() -> None:
    assert PDFDocEncoding.to_string(bytes([0x80, 0x7F])) == "•�"
    assert PDFDocEncoding.get_bytes("A\U0001f4a9") == b"A\x00"
    assert PDFDocEncoding.contains_char("AB") is False
    assert PDFDocEncoding.get_char_code("AB") is None
