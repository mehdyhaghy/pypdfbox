from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.filespecification import (
    PDComplexFileSpecification,
    PDSimpleFileSpecification,
)
from pypdfbox.pdmodel.fdf import FDFAnnotation, FDFDictionary, FDFField


def test_default_constructor_is_empty() -> None:
    fdf = FDFDictionary()
    assert isinstance(fdf.get_cos_object(), COSDictionary)
    assert fdf.get_fields() is None
    assert fdf.get_annotations() is None
    assert fdf.get_file() is None
    assert fdf.get_file_path() is None


def test_fields_round_trip() -> None:
    fdf = FDFDictionary()
    a = FDFField()
    a.set_partial_field_name("alpha")
    b = FDFField()
    b.set_partial_field_name("beta")
    fdf.set_fields([a, b])
    fields = fdf.get_fields()
    assert fields is not None and len(fields) == 2
    assert [f.get_partial_field_name() for f in fields] == ["alpha", "beta"]


def test_fields_clear() -> None:
    fdf = FDFDictionary()
    fdf.set_fields([FDFField()])
    fdf.set_fields(None)
    assert fdf.get_fields() is None


def test_file_round_trip_via_simple_file_spec_and_string_conveniences() -> None:
    fdf = FDFDictionary()
    fdf.set_file("source.pdf")

    fs = fdf.get_file()
    assert isinstance(fs, PDSimpleFileSpecification)
    assert fs.get_file() == "source.pdf"
    assert fdf.get_file_path() == "source.pdf"
    assert fdf.get_f() == "source.pdf"

    fdf.set_f("other.pdf")
    assert fdf.get_file_path() == "other.pdf"


def test_file_round_trip_via_complex_file_spec() -> None:
    fdf = FDFDictionary()
    fs = PDComplexFileSpecification()
    fs.set_file("complex.pdf")

    fdf.set_file(fs)

    got = fdf.get_file()
    assert isinstance(got, PDComplexFileSpecification)
    assert got.get_file() == "complex.pdf"
    assert fdf.get_file_path() == "complex.pdf"


def test_status_round_trip() -> None:
    fdf = FDFDictionary()
    assert fdf.get_status() is None
    fdf.set_status("OK")
    assert fdf.get_status() == "OK"


def test_id_round_trip() -> None:
    fdf = FDFDictionary()
    assert fdf.get_id() is None
    arr = COSArray()
    arr.add(COSString(b"abc"))
    arr.add(COSString(b"def"))
    fdf.set_id(arr)
    got = fdf.get_id()
    assert got is arr
    fdf.set_id(None)
    assert fdf.get_id() is None


def test_encoding_round_trip() -> None:
    fdf = FDFDictionary()
    fdf.set_encoding("UTF-8")
    assert fdf.get_encoding() == "UTF-8"
    raw = fdf.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Encoding"))
    assert isinstance(raw, COSName)
    fdf.set_encoding(None)
    assert fdf.get_encoding() is None


def test_annotations_round_trip() -> None:
    fdf = FDFDictionary()
    a = FDFAnnotation()
    a.set_subtype("Text")
    fdf.set_annotations([a])
    got = fdf.get_annotations()
    assert got is not None and len(got) == 1
    assert got[0].get_subtype() == "Text"


def test_target_round_trip() -> None:
    fdf = FDFDictionary()
    fdf.set_target("destination")
    assert fdf.get_target() == "destination"


def test_embedded_fdfs_round_trip() -> None:
    fdf = FDFDictionary()
    assert fdf.get_embedded_fdfs() is None
    arr = COSArray()
    fdf.set_embedded_fdfs(arr)
    assert fdf.get_embedded_fdfs() is arr
