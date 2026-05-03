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


# ---------- Class-level Type-name constants ----------


def test_complex_filespec_type_constant_matches_dict_entry() -> None:
    spec = PDComplexFileSpecification()
    cos = spec.get_cos_object()
    assert PDComplexFileSpecification.FILESPEC == "Filespec"
    assert cos.get_name(COSName.TYPE) == PDComplexFileSpecification.FILESPEC  # type: ignore[attr-defined]


def test_embedded_file_type_constant_matches_stream_entry() -> None:
    embedded = PDEmbeddedFile()
    assert PDEmbeddedFile.EMBEDDED_FILE == "EmbeddedFile"
    assert (
        embedded.get_cos_object().get_name(COSName.TYPE)  # type: ignore[attr-defined]
        == PDEmbeddedFile.EMBEDDED_FILE
    )


# ---------- PDEmbeddedFile string-form check sum (upstream-typed) ----------


def test_embedded_file_check_sum_string_round_trip() -> None:
    embedded = PDEmbeddedFile()
    assert embedded.get_check_sum_string() is None
    embedded.set_check_sum_string("abcdef0123456789")
    assert embedded.get_check_sum_string() == "abcdef0123456789"


def test_embedded_file_check_sum_string_clear() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_check_sum_string("deadbeef")
    embedded.set_check_sum_string(None)
    assert embedded.get_check_sum_string() is None
    assert embedded.get_check_sum() is None


def test_embedded_file_check_sum_string_clear_when_no_params_is_noop() -> None:
    embedded = PDEmbeddedFile()
    # No /Params dict yet — clearing should not raise nor create one.
    embedded.set_check_sum_string(None)
    assert embedded.get_check_sum_string() is None


# ---------- /EF embedded file None-removal (parity with upstream Java
# ----------  setItem(name, null) → remove behavior) ----------


def test_complex_set_embedded_file_none_removes_f_entry() -> None:
    spec = PDComplexFileSpecification()
    embedded = PDEmbeddedFile()
    spec.set_embedded_file(embedded)
    assert spec.get_embedded_file() is not None
    # Clearing must not raise and must remove the /F entry from the /EF dict.
    spec.set_embedded_file(None)
    assert spec.get_embedded_file() is None


def test_complex_set_embedded_file_unicode_none_removes_uf_entry() -> None:
    spec = PDComplexFileSpecification()
    embedded = PDEmbeddedFile()
    spec.set_embedded_file_unicode(embedded)
    assert spec.get_embedded_file_unicode() is not None
    spec.set_embedded_file_unicode(None)
    assert spec.get_embedded_file_unicode() is None


def test_complex_set_embedded_file_none_when_no_ef_dict_is_noop() -> None:
    # Pristine spec — no /EF at all. Setting None must not create an /EF dict
    # and must not raise.
    spec = PDComplexFileSpecification()
    spec.set_embedded_file(None)
    spec.set_embedded_file_unicode(None)
    cos = spec.get_cos_object()
    ef = cos.get_dictionary_object(COSName.get_pdf_name("EF"))
    assert ef is None


def test_complex_set_embedded_file_none_leaves_other_keys_intact() -> None:
    # Setting one key to None must NOT collaterally remove sibling /EF entries.
    spec = PDComplexFileSpecification()
    f_embed = PDEmbeddedFile()
    uf_embed = PDEmbeddedFile()
    spec.set_embedded_file(f_embed)
    spec.set_embedded_file_unicode(uf_embed)
    spec.set_embedded_file(None)
    assert spec.get_embedded_file() is None
    fetched_uf = spec.get_embedded_file_unicode()
    assert fetched_uf is not None
    assert fetched_uf.get_cos_object() is uf_embed.get_cos_object()


def test_complex_get_embedded_file_after_clear_round_trip_to_set_again() -> None:
    spec = PDComplexFileSpecification()
    first = PDEmbeddedFile()
    spec.set_embedded_file(first)
    spec.set_embedded_file(None)
    assert spec.get_embedded_file() is None
    second = PDEmbeddedFile()
    spec.set_embedded_file(second)
    fetched = spec.get_embedded_file()
    assert fetched is not None
    assert fetched.get_cos_object() is second.get_cos_object()


# ---------- PDEmbeddedFile new sub-dict name constants ----------


def test_embedded_file_params_constant_value() -> None:
    assert PDEmbeddedFile.PARAMS == "Params"


def test_embedded_file_mac_constant_value() -> None:
    assert PDEmbeddedFile.MAC == "Mac"


def test_embedded_file_type_constant_distinct_from_params_constant() -> None:
    # Defensive check: the three name constants must not collide.
    assert PDEmbeddedFile.EMBEDDED_FILE != PDEmbeddedFile.PARAMS
    assert PDEmbeddedFile.PARAMS != PDEmbeddedFile.MAC
    assert PDEmbeddedFile.EMBEDDED_FILE != PDEmbeddedFile.MAC


# ---------- PDEmbeddedFile.has_params ----------


def test_embedded_file_has_params_default_false() -> None:
    embedded = PDEmbeddedFile()
    # A pristine embedded file has only /Type — no /Params yet.
    assert embedded.has_params() is False


def test_embedded_file_has_params_true_after_size_set() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_size(99)
    assert embedded.has_params() is True


def test_embedded_file_has_params_true_after_check_sum_set() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_check_sum(b"\x00" * 16)
    assert embedded.has_params() is True


def test_embedded_file_has_params_true_after_creator_set() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_creator("pypdfbox-test")
    assert embedded.has_params() is True


# ---------- PDEmbeddedFile.has_mac_info ----------


def test_embedded_file_has_mac_info_default_false() -> None:
    embedded = PDEmbeddedFile()
    assert embedded.has_mac_info() is False


def test_embedded_file_has_mac_info_false_when_only_size_set() -> None:
    # /Params exists but no /Params/Mac sub-dict yet.
    embedded = PDEmbeddedFile()
    embedded.set_size(1)
    assert embedded.has_params() is True
    assert embedded.has_mac_info() is False


def test_embedded_file_has_mac_info_true_after_mac_subtype_set() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_mac_subtype("PDF ")
    assert embedded.has_mac_info() is True


def test_embedded_file_has_mac_info_true_after_mac_creator_set() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_mac_creator("PRVW")
    assert embedded.has_mac_info() is True


def test_embedded_file_has_mac_info_true_after_mac_resource_fork_set() -> None:
    embedded = PDEmbeddedFile()
    rf = COSStream()
    embedded.set_mac_resource_fork(rf)
    assert embedded.has_mac_info() is True


# ---------- PDEmbeddedFile.is_subtype ----------


def test_embedded_file_is_subtype_default_false_for_any_mime() -> None:
    embedded = PDEmbeddedFile()
    assert embedded.is_subtype("application/pdf") is False
    assert embedded.is_subtype("text/plain") is False


def test_embedded_file_is_subtype_none_returns_false() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_subtype("application/pdf")
    assert embedded.is_subtype(None) is False


def test_embedded_file_is_subtype_exact_match() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_subtype("application/pdf")
    assert embedded.is_subtype("application/pdf") is True


def test_embedded_file_is_subtype_case_insensitive() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_subtype("application/pdf")
    assert embedded.is_subtype("Application/PDF") is True
    assert embedded.is_subtype("APPLICATION/PDF") is True
    assert embedded.is_subtype("application/PDF") is True


def test_embedded_file_is_subtype_mismatch() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_subtype("text/plain")
    assert embedded.is_subtype("application/pdf") is False


def test_embedded_file_is_subtype_after_clear_returns_false() -> None:
    embedded = PDEmbeddedFile()
    embedded.set_subtype("text/plain")
    embedded.set_subtype(None)
    assert embedded.is_subtype("text/plain") is False


def test_embedded_file_is_subtype_when_subtype_unset_with_none_arg() -> None:
    embedded = PDEmbeddedFile()
    assert embedded.is_subtype(None) is False
