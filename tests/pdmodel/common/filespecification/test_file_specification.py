from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSStream, COSString
from pypdfbox.pdmodel.common.filespecification import (
    PDComplexFileSpecification,
    PDEmbeddedFile,
    PDFileSpecification,
    PDSimpleFileSpecification,
)


def test_create_fs_with_cos_string_returns_simple() -> None:
    spec = PDFileSpecification.create_fs(COSString("hello.pdf"))
    assert isinstance(spec, PDSimpleFileSpecification)
    assert spec.get_file() == "hello.pdf"


def test_create_fs_with_cos_dictionary_returns_complex() -> None:
    raw = COSDictionary()
    spec = PDFileSpecification.create_fs(raw)
    assert isinstance(spec, PDComplexFileSpecification)
    assert spec.get_cos_object() is raw


def test_create_fs_with_none_returns_none() -> None:
    assert PDFileSpecification.create_fs(None) is None


def test_create_fs_with_unknown_type_raises() -> None:
    with pytest.raises(OSError):
        PDFileSpecification.create_fs(COSInteger.get(7))


def test_complex_default_sets_type_filespec() -> None:
    spec = PDComplexFileSpecification()
    assert spec.get_cos_object().get_name(COSName.TYPE) == "Filespec"  # type: ignore[attr-defined]


def test_complex_round_trip_file_unicode_and_description() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file("ascii.pdf")
    spec.set_file_unicode("unicode.pdf")
    spec.set_file_description("a unit test attachment")
    assert spec.get_file() == "ascii.pdf"
    assert spec.get_file_unicode() == "unicode.pdf"
    assert spec.get_file_description() == "a unit test attachment"


def test_complex_get_filename_prefers_unicode() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file("ascii.pdf")
    spec.set_file_unicode("unicode.pdf")
    assert spec.get_filename() == "unicode.pdf"


def test_complex_get_filename_falls_back_to_f() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file("only.pdf")
    assert spec.get_filename() == "only.pdf"


def test_complex_volatile_round_trip() -> None:
    spec = PDComplexFileSpecification()
    assert spec.is_volatile() is False
    spec.set_volatile(True)
    assert spec.is_volatile() is True


def test_complex_embedded_file_round_trip() -> None:
    spec = PDComplexFileSpecification()
    embedded = PDEmbeddedFile()
    embedded.set_subtype("application/pdf")
    spec.set_embedded_file(embedded)
    fetched = spec.get_embedded_file()
    assert isinstance(fetched, PDEmbeddedFile)
    assert fetched.get_cos_object() is embedded.get_cos_object()
    assert fetched.get_subtype() == "application/pdf"


def test_complex_embedded_file_unicode_round_trip() -> None:
    spec = PDComplexFileSpecification()
    embedded = PDEmbeddedFile()
    spec.set_embedded_file_unicode(embedded)
    fetched = spec.get_embedded_file_unicode()
    assert isinstance(fetched, PDEmbeddedFile)
    assert fetched.get_cos_object() is embedded.get_cos_object()


def test_simple_default_constructor_yields_empty_string() -> None:
    spec = PDSimpleFileSpecification()
    assert spec.get_file() == ""


def test_simple_round_trip_file() -> None:
    spec = PDSimpleFileSpecification(COSString("first.pdf"))
    assert spec.get_file() == "first.pdf"
    spec.set_file("second.pdf")
    assert spec.get_file() == "second.pdf"
    assert isinstance(spec.get_cos_object(), COSString)


def test_embedded_file_subtype_and_size() -> None:
    embedded = PDEmbeddedFile()
    assert isinstance(embedded.get_cos_object(), COSStream)
    assert embedded.get_cos_object().get_name(COSName.TYPE) == "EmbeddedFile"  # type: ignore[attr-defined]
    embedded.set_subtype("text/plain")
    embedded.set_size(1234)
    assert embedded.get_subtype() == "text/plain"
    assert embedded.get_size() == 1234


def test_embedded_file_dates_and_checksum() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_creation_date("D:20260101000000Z")
    embedded.set_mod_date("D:20260201000000Z")
    embedded.set_check_sum("abc123")
    assert embedded.get_creation_date() == "D:20260101000000Z"
    assert embedded.get_mod_date() == "D:20260201000000Z"
    assert embedded.get_check_sum() == "abc123"


def test_embedded_file_mac_metadata() -> None:
    embedded = PDEmbeddedFile()
    assert embedded.get_mac_subtype() is None
    embedded.set_mac_subtype("PDF ")
    embedded.set_mac_creator("PRVW")
    embedded.set_mac_resource_fork("rsrc")
    assert embedded.get_mac_subtype() == "PDF "
    assert embedded.get_mac_creator() == "PRVW"
    assert embedded.get_mac_resource_fork() == "rsrc"


def test_embedded_file_wraps_existing_cos_stream() -> None:
    raw = COSStream()
    embedded = PDEmbeddedFile(raw)
    assert embedded.get_cos_object() is raw
