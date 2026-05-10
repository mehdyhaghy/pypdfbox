from __future__ import annotations

import io

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream, COSString
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


def test_embedded_fd_fs_strict_alias() -> None:
    """``get_embedded_fd_fs`` is the strict mechanical translation of
    upstream ``getEmbeddedFDFs`` and must round-trip with the pythonic
    ``get_embedded_fdfs`` form.
    """
    fdf = FDFDictionary()
    arr = COSArray()
    fdf.set_embedded_fd_fs(arr)
    assert fdf.get_embedded_fd_fs() is arr
    assert fdf.get_embedded_fdfs() is arr
    fdf.set_embedded_fd_fs(None)
    assert fdf.get_embedded_fd_fs() is None
    assert fdf.get_embedded_fdfs() is None


def test_pages_round_trip() -> None:
    fdf = FDFDictionary()
    assert fdf.get_pages() is None
    arr = COSArray()
    arr.add(COSDictionary())
    arr.add(COSDictionary())
    fdf.set_pages(arr)
    assert fdf.get_pages() is arr
    fdf.set_pages(None)
    assert fdf.get_pages() is None


def test_differences_round_trip() -> None:
    fdf = FDFDictionary()
    assert fdf.get_differences() is None
    diff = COSStream()
    fdf.set_differences(diff)
    assert fdf.get_differences() is diff
    fdf.set_differences(None)
    assert fdf.get_differences() is None


def test_javascript_round_trip() -> None:
    fdf = FDFDictionary()
    assert fdf.get_javascript() is None
    js = COSDictionary()
    fdf.set_javascript(js)
    assert fdf.get_javascript() is js
    fdf.set_javascript(None)
    assert fdf.get_javascript() is None


def test_java_script_strict_alias() -> None:
    """``get_java_script`` is the strict mechanical translation of upstream
    ``getJavaScript`` and must round-trip with the pythonic
    ``get_javascript`` form."""
    fdf = FDFDictionary()
    js = COSDictionary()
    fdf.set_java_script(js)
    assert fdf.get_java_script() is js
    assert fdf.get_javascript() is js


def test_write_xml_empty_dictionary_emits_nothing() -> None:
    fdf = FDFDictionary()
    out = io.StringIO()
    fdf.write_xml(out)
    assert out.getvalue() == ""


def test_write_xml_with_file_id_and_fields() -> None:
    fdf = FDFDictionary()
    fdf.set_file("source.pdf")
    ids = COSArray()
    ids.add(COSString(b"\x01\x02"))
    ids.add(COSString(b"\x03\x04"))
    fdf.set_id(ids)
    field = FDFField()
    field.set_partial_field_name("alpha")
    fdf.set_fields([field])

    out = io.StringIO()
    fdf.write_xml(out)
    text = out.getvalue()
    assert '<f href="source.pdf" />' in text
    # Hex emission is uppercase per COSString.to_hex_string.
    assert '<ids original="0102" modified="0304" />' in text
    assert "<fields>" in text and "</fields>" in text
    assert 'name="alpha"' in text
