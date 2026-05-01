from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSObject, COSStream, COSString
from pypdfbox.pdmodel.common.filespecification import (
    PDComplexFileSpecification,
    PDEmbeddedFile,
    PDFileSpecification,
    PDSimpleFileSpecification,
)


# ---------- PDSimpleFileSpecification ----------


def test_simple_round_trip() -> None:
    spec = PDSimpleFileSpecification(COSString("alpha.pdf"))
    assert spec.get_file() == "alpha.pdf"
    spec.set_file("beta.pdf")
    assert spec.get_file() == "beta.pdf"


def test_simple_get_cos_object_is_cos_string() -> None:
    spec = PDSimpleFileSpecification(COSString("gamma.pdf"))
    cos = spec.get_cos_object()
    assert isinstance(cos, COSString)
    assert cos.get_string() == "gamma.pdf"


def test_simple_set_file_none_yields_empty_string() -> None:
    spec = PDSimpleFileSpecification(COSString("present.pdf"))
    spec.set_file(None)
    assert spec.get_file() == ""


# ---------- PDComplexFileSpecification ----------


def test_complex_round_trip_all_platform_variants() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file("ascii.pdf")
    spec.set_file_unicode("unicode.pdf")
    spec.set_file_dos("dos.pdf")
    spec.set_file_mac("mac.pdf")
    spec.set_file_unix("unix.pdf")
    spec.set_file_description("a description")

    assert spec.get_file() == "ascii.pdf"
    assert spec.get_file_unicode() == "unicode.pdf"
    assert spec.get_file_dos() == "dos.pdf"
    assert spec.get_file_mac() == "mac.pdf"
    assert spec.get_file_unix() == "unix.pdf"
    assert spec.get_file_description() == "a description"


def test_complex_default_type_is_filespec() -> None:
    spec = PDComplexFileSpecification()
    cos = spec.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.get_name(COSName.TYPE) == "Filespec"  # type: ignore[attr-defined]


def test_complex_setters_clear_via_none() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file("present.pdf")
    spec.set_file_unicode("present-u.pdf")
    spec.set_file_dos("present-dos.pdf")
    spec.set_file_mac("present-mac.pdf")
    spec.set_file_unix("present-unix.pdf")
    spec.set_file_description("desc")

    spec.set_file(None)
    spec.set_file_unicode(None)
    spec.set_file_dos(None)
    spec.set_file_mac(None)
    spec.set_file_unix(None)
    spec.set_file_description(None)

    assert spec.get_file() is None
    assert spec.get_file_unicode() is None
    assert spec.get_file_dos() is None
    assert spec.get_file_mac() is None
    assert spec.get_file_unix() is None
    assert spec.get_file_description() is None


def test_complex_get_filename_prefers_unicode_then_dos_then_mac_then_unix_then_f() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file("only-f.pdf")
    assert spec.get_filename() == "only-f.pdf"
    spec.set_file_unix("unix.pdf")
    assert spec.get_filename() == "unix.pdf"
    spec.set_file_mac("mac.pdf")
    assert spec.get_filename() == "mac.pdf"
    spec.set_file_dos("dos.pdf")
    assert spec.get_filename() == "dos.pdf"
    spec.set_file_unicode("uni.pdf")
    assert spec.get_filename() == "uni.pdf"


# ---------- /EF embedded files ----------


def test_complex_get_embedded_file_wraps_pdembeddedfile() -> None:
    spec = PDComplexFileSpecification()
    embedded = PDEmbeddedFile()
    embedded.set_subtype("application/pdf")
    spec.set_embedded_file(embedded)

    fetched = spec.get_embedded_file()
    assert isinstance(fetched, PDEmbeddedFile)
    assert fetched.get_cos_object() is embedded.get_cos_object()
    assert fetched.get_subtype() == "application/pdf"


def test_complex_get_embedded_file_unicode_wraps_pdembeddedfile() -> None:
    spec = PDComplexFileSpecification()
    embedded = PDEmbeddedFile()
    embedded.set_subtype("text/plain")
    spec.set_embedded_file_unicode(embedded)

    fetched = spec.get_embedded_file_unicode()
    assert isinstance(fetched, PDEmbeddedFile)
    assert fetched.get_cos_object() is embedded.get_cos_object()
    assert fetched.get_subtype() == "text/plain"


def test_complex_get_embedded_file_default_none() -> None:
    spec = PDComplexFileSpecification()
    assert spec.get_embedded_file() is None
    assert spec.get_embedded_file_unicode() is None


# ---------- /V volatile ----------


def test_complex_is_volatile_default_false() -> None:
    spec = PDComplexFileSpecification()
    assert spec.is_volatile() is False


def test_complex_volatile_round_trip() -> None:
    spec = PDComplexFileSpecification()
    spec.set_volatile(True)
    assert spec.is_volatile() is True
    spec.set_volatile(False)
    assert spec.is_volatile() is False


def test_complex_constructor_none_creates_typed_dict() -> None:
    spec = PDComplexFileSpecification(None)
    cos = spec.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.get_name(COSName.TYPE) == "Filespec"  # type: ignore[attr-defined]


def test_complex_get_filename_none_when_no_entries_set() -> None:
    spec = PDComplexFileSpecification()
    assert spec.get_filename() is None


# ---------- create_fs(COSObject) — indirect-reference auto-deref ----------


def test_create_fs_with_indirect_cos_string_returns_simple() -> None:
    inner = COSString("indirect.pdf")
    ref = COSObject(1, 0, resolved=inner)
    spec = PDFileSpecification.create_fs(ref)
    assert isinstance(spec, PDSimpleFileSpecification)
    assert spec.get_file() == "indirect.pdf"


def test_create_fs_with_indirect_cos_dictionary_returns_complex() -> None:
    inner = COSDictionary()
    inner.set_string(COSName.get_pdf_name("F"), "wrapped.pdf")
    ref = COSObject(2, 0, resolved=inner)
    spec = PDFileSpecification.create_fs(ref)
    assert isinstance(spec, PDComplexFileSpecification)
    assert spec.get_file() == "wrapped.pdf"


def test_create_fs_with_unresolved_indirect_returns_none() -> None:
    # COSObject without a resolved value and without a loader stays unresolved.
    ref = COSObject(3, 0)
    assert PDFileSpecification.create_fs(ref) is None


# ---------- PDEmbeddedFile mac-res-fork mechanical-name aliases ----------


def test_embedded_file_mac_res_fork_aliases_round_trip() -> None:
    embedded = PDEmbeddedFile()
    rf = COSStream()
    embedded.set_mac_res_fork(rf)
    fetched = embedded.get_mac_res_fork()
    assert fetched is rf
    # The pythonic-named accessor should see the same stream.
    assert embedded.get_mac_resource_fork() is rf
    embedded.set_mac_res_fork(None)
    assert embedded.get_mac_res_fork() is None
    assert embedded.get_mac_resource_fork() is None


def test_embedded_file_mac_res_fork_alias_default_none() -> None:
    embedded = PDEmbeddedFile()
    assert embedded.get_mac_res_fork() is None
