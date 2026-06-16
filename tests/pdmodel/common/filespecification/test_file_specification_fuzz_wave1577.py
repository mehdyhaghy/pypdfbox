"""Fuzz / parity tests for file specifications (wave 1577).

Hammers PDComplexFileSpecification, PDEmbeddedFile and PDSimpleFileSpecification
against PDFBox 3.0.7 behaviour:

* get_file / get_file_unicode read only their own key (/F, /UF) — no cascade.
* get_filename cascade prefers /UF, then /DOS, /Mac, /Unix, then /F.
* set_file writes only /F, set_file_unicode only /UF (upstream
  PDComplexFileSpecification.setFile/setFileUnicode write a single key each in
  3.0.7 — verified against upstream source).
* /EF embedded-file accessors per-platform (/F /UF /DOS /Mac /Unix).
* PDEmbeddedFile /Params: get_size (default -1), get_creation_date /
  get_mod_date (datetime), get_check_sum (bytes), get_subtype, /Params/Mac
  sub-dictionary subtype/creator.
* PDSimpleFileSpecification (string-only) vs complex (dict) dispatch.
* missing keys -> None / -1; set round-trips.
"""

from __future__ import annotations

import datetime as dt

import pytest

from pypdfbox.cos import (
    COSDictionary,
    COSName,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.common.filespecification import (
    PDComplexFileSpecification,
    PDEmbeddedFile,
    PDFileSpecification,
    PDSimpleFileSpecification,
)

_F = COSName.get_pdf_name("F")
_UF = COSName.get_pdf_name("UF")
_DOS = COSName.get_pdf_name("DOS")
_MAC = COSName.get_pdf_name("Mac")
_UNIX = COSName.get_pdf_name("Unix")
_EF = COSName.get_pdf_name("EF")
_PARAMS = COSName.get_pdf_name("Params")


# ---------------------------------------------------------------------------
# get_file / get_file_unicode read a single key — no cascade
# ---------------------------------------------------------------------------


def test_get_file_reads_only_f() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file("ascii.pdf")
    assert spec.get_file() == "ascii.pdf"
    # /UF absent -> get_file_unicode is None (no fallback to /F)
    assert spec.get_file_unicode() is None


def test_get_file_unicode_reads_only_uf() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file_unicode("uni.pdf")
    assert spec.get_file_unicode() == "uni.pdf"
    # /F absent -> get_file is None (no fallback to /UF)
    assert spec.get_file() is None


def test_set_file_writes_only_f_key() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file("only-f.pdf")
    cos = spec.get_cos_object()
    assert cos.get_string(_F) == "only-f.pdf"
    # upstream 3.0.7 setFile writes ONLY /F, not /UF
    assert not cos.contains_key(_UF)


def test_set_file_unicode_writes_only_uf_key() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file_unicode("only-uf.pdf")
    cos = spec.get_cos_object()
    assert cos.get_string(_UF) == "only-uf.pdf"
    assert not cos.contains_key(_F)


# ---------------------------------------------------------------------------
# get_filename cascade: /UF then /DOS /Mac /Unix then /F
# ---------------------------------------------------------------------------


def test_get_filename_prefers_unicode() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file("f.pdf")
    spec.set_file_unicode("uf.pdf")
    spec.set_file_dos("dos.pdf")
    spec.set_file_mac("mac.pdf")
    spec.set_file_unix("unix.pdf")
    assert spec.get_filename() == "uf.pdf"


def test_get_filename_falls_to_dos_when_no_unicode() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file("f.pdf")
    spec.set_file_dos("dos.pdf")
    spec.set_file_mac("mac.pdf")
    assert spec.get_filename() == "dos.pdf"


def test_get_filename_falls_to_mac_when_no_unicode_dos() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file("f.pdf")
    spec.set_file_mac("mac.pdf")
    spec.set_file_unix("unix.pdf")
    assert spec.get_filename() == "mac.pdf"


def test_get_filename_falls_to_unix_when_no_unicode_dos_mac() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file("f.pdf")
    spec.set_file_unix("unix.pdf")
    assert spec.get_filename() == "unix.pdf"


def test_get_filename_falls_to_f_last() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file("only-f.pdf")
    assert spec.get_filename() == "only-f.pdf"


def test_get_filename_none_when_empty() -> None:
    spec = PDComplexFileSpecification()
    assert spec.get_filename() is None


# ---------------------------------------------------------------------------
# missing keys -> None
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "getter",
    [
        "get_file",
        "get_file_unicode",
        "get_file_dos",
        "get_file_mac",
        "get_file_unix",
        "get_file_description",
        "get_af_relationship",
    ],
)
def test_missing_string_keys_return_none(getter: str) -> None:
    spec = PDComplexFileSpecification()
    assert getattr(spec, getter)() is None


@pytest.mark.parametrize(
    "getter",
    [
        "get_embedded_file",
        "get_embedded_file_unicode",
        "get_embedded_file_dos",
        "get_embedded_file_mac",
        "get_embedded_file_unix",
    ],
)
def test_missing_embedded_keys_return_none(getter: str) -> None:
    spec = PDComplexFileSpecification()
    assert getattr(spec, getter)() is None


# ---------------------------------------------------------------------------
# platform path round trips
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("setter", "getter"),
    [
        ("set_file", "get_file"),
        ("set_file_unicode", "get_file_unicode"),
        ("set_file_dos", "get_file_dos"),
        ("set_file_mac", "get_file_mac"),
        ("set_file_unix", "get_file_unix"),
        ("set_file_description", "get_file_description"),
    ],
)
def test_string_round_trip(setter: str, getter: str) -> None:
    spec = PDComplexFileSpecification()
    getattr(spec, setter)("valueé.bin")
    assert getattr(spec, getter)() == "valueé.bin"


def test_description_round_trip_and_clear() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file_description("a description")
    assert spec.get_file_description() == "a description"
    assert spec.has_file_description()
    spec.clear_file_description()
    assert spec.get_file_description() is None
    assert not spec.has_file_description()


# ---------------------------------------------------------------------------
# embedded-file accessors per platform key
# ---------------------------------------------------------------------------


def test_set_embedded_file_creates_ef_dictionary() -> None:
    spec = PDComplexFileSpecification()
    assert not spec.has_embedded_files()
    ef = PDEmbeddedFile()
    spec.set_embedded_file(ef)
    assert spec.has_embedded_files()
    assert spec.has_embedded_file()
    got = spec.get_embedded_file()
    assert got is not None
    assert got.get_cos_object() is ef.get_cos_object()


@pytest.mark.parametrize(
    ("setter", "getter", "key"),
    [
        ("set_embedded_file", "get_embedded_file", _F),
        ("set_embedded_file_unicode", "get_embedded_file_unicode", _UF),
        ("set_embedded_file_dos", "get_embedded_file_dos", _DOS),
        ("set_embedded_file_mac", "get_embedded_file_mac", _MAC),
        ("set_embedded_file_unix", "get_embedded_file_unix", _UNIX),
    ],
)
def test_embedded_file_round_trip_each_key(
    setter: str, getter: str, key: COSName
) -> None:
    spec = PDComplexFileSpecification()
    ef = PDEmbeddedFile()
    getattr(spec, setter)(ef)
    ef_dict = spec.get_cos_object().get_dictionary_object(_EF)
    assert isinstance(ef_dict, COSDictionary)
    assert isinstance(ef_dict.get_dictionary_object(key), COSStream)
    got = getattr(spec, getter)()
    assert got is not None
    assert got.get_cos_object() is ef.get_cos_object()


def test_embedded_uf_does_not_fall_back_to_f() -> None:
    # /EF/F set, /EF/UF absent -> unicode embedded accessor must be None
    spec = PDComplexFileSpecification()
    spec.set_embedded_file(PDEmbeddedFile())
    assert spec.get_embedded_file() is not None
    assert spec.get_embedded_file_unicode() is None


def test_set_embedded_file_none_clears_slot() -> None:
    spec = PDComplexFileSpecification()
    spec.set_embedded_file(PDEmbeddedFile())
    assert spec.has_embedded_file()
    spec.set_embedded_file(None)
    assert not spec.has_embedded_file()


def test_clear_embedded_files_drops_ef() -> None:
    spec = PDComplexFileSpecification()
    spec.set_embedded_file(PDEmbeddedFile())
    spec.set_embedded_file_unicode(PDEmbeddedFile())
    spec.clear_embedded_files()
    assert not spec.has_embedded_files()
    # cached ref cleared -> a fresh set rebuilds /EF
    spec.set_embedded_file(PDEmbeddedFile())
    assert spec.has_embedded_file()


# ---------------------------------------------------------------------------
# PDEmbeddedFile /Params accessors
# ---------------------------------------------------------------------------


def test_embedded_file_size_default_is_minus_one() -> None:
    ef = PDEmbeddedFile()
    assert ef.get_size() == -1
    assert not ef.has_size()


def test_embedded_file_size_round_trip() -> None:
    ef = PDEmbeddedFile()
    ef.set_size(4096)
    assert ef.get_size() == 4096
    assert ef.has_size()
    ef.set_size(0)
    assert ef.get_size() == 0


def test_embedded_file_size_clear() -> None:
    ef = PDEmbeddedFile()
    ef.set_size(99)
    ef.clear_size()
    assert ef.get_size() == -1


def test_embedded_file_creation_date_round_trip() -> None:
    ef = PDEmbeddedFile()
    when = dt.datetime(2021, 5, 6, 7, 8, 9, tzinfo=dt.UTC)
    ef.set_creation_date(when)
    got = ef.get_creation_date()
    assert got is not None
    assert got == when


def test_embedded_file_mod_date_round_trip() -> None:
    ef = PDEmbeddedFile()
    when = dt.datetime(1999, 12, 31, 23, 59, 58, tzinfo=dt.timezone(dt.timedelta(hours=-5)))
    ef.set_mod_date(when)
    got = ef.get_mod_date()
    assert got is not None
    assert got == when


def test_embedded_file_dates_missing_are_none() -> None:
    ef = PDEmbeddedFile()
    assert ef.get_creation_date() is None
    assert ef.get_mod_date() is None
    assert not ef.has_creation_date()
    assert not ef.has_mod_date()


def test_embedded_file_date_string_written_verbatim() -> None:
    ef = PDEmbeddedFile()
    ef.set_creation_date("D:20100203040506Z")
    params = ef.get_cos_object().get_dictionary_object(_PARAMS)
    assert params.get_string(COSName.get_pdf_name("CreationDate")) == "D:20100203040506Z"


def test_embedded_file_date_clear() -> None:
    ef = PDEmbeddedFile()
    ef.set_creation_date(dt.datetime(2020, 1, 1, tzinfo=dt.UTC))
    ef.clear_creation_date()
    assert ef.get_creation_date() is None


def test_embedded_file_check_sum_bytes_round_trip() -> None:
    ef = PDEmbeddedFile()
    digest = bytes(range(16))  # 16-byte MD5-shaped value with non-printables
    ef.set_check_sum(digest)
    assert ef.get_check_sum() == digest
    assert ef.has_check_sum()


def test_embedded_file_check_sum_forces_hex_form() -> None:
    ef = PDEmbeddedFile()
    ef.set_check_sum(b"\x00\x01\x02\xff")
    params = ef.get_cos_object().get_dictionary_object(_PARAMS)
    cs = params.get_dictionary_object(COSName.get_pdf_name("CheckSum"))
    assert isinstance(cs, COSString)
    assert cs.get_force_hex_form() is True


def test_embedded_file_check_sum_missing_is_none() -> None:
    ef = PDEmbeddedFile()
    assert ef.get_check_sum() is None
    assert not ef.has_check_sum()


def test_embedded_file_check_sum_clear() -> None:
    ef = PDEmbeddedFile()
    ef.set_check_sum(b"abcd")
    ef.clear_check_sum()
    assert ef.get_check_sum() is None


def test_embedded_file_check_sum_string_alias_round_trip() -> None:
    # the verbatim Java-surface String alias round-trips printable text
    ef = PDEmbeddedFile()
    ef.set_check_sum_string("plainsum")
    assert ef.get_check_sum_string() == "plainsum"


# ---------------------------------------------------------------------------
# /Subtype (mime type)
# ---------------------------------------------------------------------------


def test_embedded_file_subtype_round_trip() -> None:
    ef = PDEmbeddedFile()
    ef.set_subtype("application/pdf")
    assert ef.get_subtype() == "application/pdf"
    assert ef.has_subtype()
    assert ef.is_subtype("APPLICATION/PDF")  # case-insensitive
    assert not ef.is_subtype("text/plain")


def test_embedded_file_subtype_missing_is_none() -> None:
    ef = PDEmbeddedFile()
    assert ef.get_subtype() is None
    assert not ef.has_subtype()
    assert not ef.is_subtype("application/pdf")


def test_embedded_file_subtype_clear() -> None:
    ef = PDEmbeddedFile()
    ef.set_subtype("image/png")
    ef.clear_subtype()
    assert ef.get_subtype() is None


# ---------------------------------------------------------------------------
# /Params/Mac sub-dictionary
# ---------------------------------------------------------------------------


def test_embedded_file_mac_subtype_round_trip() -> None:
    ef = PDEmbeddedFile()
    ef.set_mac_subtype("PDF ")
    assert ef.get_mac_subtype() == "PDF "
    assert ef.has_mac_subtype()
    assert ef.has_mac_info()


def test_embedded_file_mac_subtype_missing_is_none() -> None:
    ef = PDEmbeddedFile()
    assert ef.get_mac_subtype() is None
    assert not ef.has_mac_subtype()
    assert not ef.has_mac_info()


def test_embedded_file_mac_creator_round_trip() -> None:
    ef = PDEmbeddedFile()
    ef.set_mac_creator("prvw")
    assert ef.get_mac_creator() == "prvw"
    assert ef.has_mac_creator()


def test_embedded_file_mac_clear() -> None:
    ef = PDEmbeddedFile()
    ef.set_mac_subtype("PDF ")
    ef.set_mac_creator("prvw")
    ef.clear_mac_info()
    assert ef.get_mac_subtype() is None
    assert ef.get_mac_creator() is None
    assert not ef.has_mac_info()


# ---------------------------------------------------------------------------
# PDSimpleFileSpecification (string) vs complex (dict) dispatch
# ---------------------------------------------------------------------------


def test_create_fs_string_yields_simple() -> None:
    fs = PDFileSpecification.create_fs(COSString("simple.pdf"))
    assert isinstance(fs, PDSimpleFileSpecification)
    assert fs.get_file() == "simple.pdf"


def test_create_fs_dict_yields_complex() -> None:
    d = COSDictionary()
    d.set_string(_F, "complex.pdf")
    fs = PDFileSpecification.create_fs(d)
    assert isinstance(fs, PDComplexFileSpecification)
    assert fs.get_file() == "complex.pdf"


def test_create_fs_none_yields_none() -> None:
    assert PDFileSpecification.create_fs(None) is None


def test_create_fs_unknown_type_raises() -> None:
    with pytest.raises(OSError):
        PDFileSpecification.create_fs(COSName.get_pdf_name("Bogus"))


def test_create_fs_dereferences_cos_object() -> None:
    d = COSDictionary()
    d.set_string(_F, "ref.pdf")
    ref = COSObject(1, 0, resolved=d)
    fs = PDFileSpecification.create_fs(ref)
    assert isinstance(fs, PDComplexFileSpecification)
    assert fs.get_file() == "ref.pdf"


def test_simple_spec_set_none_yields_empty_string() -> None:
    spec = PDSimpleFileSpecification(COSString("x.pdf"))
    spec.set_file(None)
    assert spec.get_file() == ""


def test_simple_spec_default_is_empty() -> None:
    spec = PDSimpleFileSpecification()
    assert spec.get_file() == ""
    assert isinstance(spec.get_cos_object(), COSString)


# ---------------------------------------------------------------------------
# /V volatile
# ---------------------------------------------------------------------------


def test_volatile_round_trip() -> None:
    spec = PDComplexFileSpecification()
    assert spec.is_volatile() is False  # spec default
    assert not spec.has_volatile()
    spec.set_volatile(True)
    assert spec.is_volatile() is True
    assert spec.has_volatile()
    spec.clear_volatile()
    assert spec.is_volatile() is False
    assert not spec.has_volatile()


# ---------------------------------------------------------------------------
# /AFRelationship
# ---------------------------------------------------------------------------


def test_af_relationship_round_trip() -> None:
    spec = PDComplexFileSpecification()
    spec.set_af_relationship("Source")
    assert spec.get_af_relationship() == "Source"
    assert PDComplexFileSpecification.is_standard_af_relationship("Source")
    assert not PDComplexFileSpecification.is_standard_af_relationship("Vendor")
    spec.set_af_relationship(None)
    assert spec.get_af_relationship() is None


# ---------------------------------------------------------------------------
# is_empty
# ---------------------------------------------------------------------------


def test_is_empty_fresh_spec() -> None:
    assert PDComplexFileSpecification().is_empty()


def test_is_empty_false_with_file() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file("x.pdf")
    assert not spec.is_empty()


def test_is_empty_ignores_volatile() -> None:
    spec = PDComplexFileSpecification()
    spec.set_volatile(False)
    assert spec.is_empty()
