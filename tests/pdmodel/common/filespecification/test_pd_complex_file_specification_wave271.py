"""Wave 271 — round-out AFRelationship constants, presence predicates,
clearers, and emptiness check for ``PDComplexFileSpecification``.

Targets enrichment surface added on top of upstream PDFBox 3.0
``PDComplexFileSpecification``:

- ``AF_RELATIONSHIP_*`` constants for the seven ISO 32000-2 §14.13
  registered values
- ``is_standard_af_relationship`` classifier
- ``has_*`` presence predicates for every optional entry
- ``clear_*`` shortcuts for ``/V``, ``/Desc``, ``/AFRelationship``,
  and the ``/EF`` sub-dictionary
- ``is_empty`` structural-emptiness predicate
"""
from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.common.filespecification import (
    PDComplexFileSpecification,
    PDEmbeddedFile,
)

# ---------- AFRelationship constants ----------


def test_af_relationship_constants_match_iso_32000_2_spelling() -> None:
    # Spelled exactly as they round-trip into /AFRelationship.
    assert PDComplexFileSpecification.AF_RELATIONSHIP_SOURCE == "Source"
    assert PDComplexFileSpecification.AF_RELATIONSHIP_DATA == "Data"
    assert PDComplexFileSpecification.AF_RELATIONSHIP_ALTERNATIVE == "Alternative"
    assert PDComplexFileSpecification.AF_RELATIONSHIP_SUPPLEMENT == "Supplement"
    assert (
        PDComplexFileSpecification.AF_RELATIONSHIP_ENCRYPTED_PAYLOAD
        == "EncryptedPayload"
    )
    assert PDComplexFileSpecification.AF_RELATIONSHIP_FORM_DATA == "FormData"
    assert PDComplexFileSpecification.AF_RELATIONSHIP_UNSPECIFIED == "Unspecified"


def test_af_relationship_constants_are_strings() -> None:
    # Plain str (matching the value written into /AFRelationship) so
    # callers can compare get_af_relationship() against them directly.
    for name in (
        "AF_RELATIONSHIP_SOURCE",
        "AF_RELATIONSHIP_DATA",
        "AF_RELATIONSHIP_ALTERNATIVE",
        "AF_RELATIONSHIP_SUPPLEMENT",
        "AF_RELATIONSHIP_ENCRYPTED_PAYLOAD",
        "AF_RELATIONSHIP_FORM_DATA",
        "AF_RELATIONSHIP_UNSPECIFIED",
    ):
        assert isinstance(getattr(PDComplexFileSpecification, name), str)


def test_af_relationship_constants_round_trip_through_setter() -> None:
    spec = PDComplexFileSpecification()
    spec.set_af_relationship(PDComplexFileSpecification.AF_RELATIONSHIP_DATA)
    assert spec.get_af_relationship() == "Data"


# ---------- is_standard_af_relationship ----------


def test_is_standard_af_relationship_accepts_registered_set() -> None:
    for value in (
        "Source",
        "Data",
        "Alternative",
        "Supplement",
        "EncryptedPayload",
        "FormData",
        "Unspecified",
    ):
        assert PDComplexFileSpecification.is_standard_af_relationship(value)


def test_is_standard_af_relationship_rejects_unknown_value() -> None:
    assert (
        PDComplexFileSpecification.is_standard_af_relationship("VendorCustom")
        is False
    )


def test_is_standard_af_relationship_rejects_none() -> None:
    # The absence of /AFRelationship is legal but it isn't a "standard
    # value", so the classifier rejects it.
    assert PDComplexFileSpecification.is_standard_af_relationship(None) is False


def test_is_standard_af_relationship_is_case_sensitive() -> None:
    # /AFRelationship is a PDF Name — case-sensitive per PDF 32000-1
    # §7.3.5.
    assert (
        PDComplexFileSpecification.is_standard_af_relationship("data") is False
    )


# ---------- has_* presence predicates ----------


def test_has_file_round_trip() -> None:
    spec = PDComplexFileSpecification()
    assert spec.has_file() is False
    spec.set_file("doc.pdf")
    assert spec.has_file() is True


def test_has_file_unicode_round_trip() -> None:
    spec = PDComplexFileSpecification()
    assert spec.has_file_unicode() is False
    spec.set_file_unicode("doc.pdf")
    assert spec.has_file_unicode() is True


def test_has_file_dos_round_trip() -> None:
    spec = PDComplexFileSpecification()
    assert spec.has_file_dos() is False
    spec.set_file_dos("DOC.PDF")
    assert spec.has_file_dos() is True


def test_has_file_mac_round_trip() -> None:
    spec = PDComplexFileSpecification()
    assert spec.has_file_mac() is False
    spec.set_file_mac(":Macintosh HD:doc.pdf")
    assert spec.has_file_mac() is True


def test_has_file_unix_round_trip() -> None:
    spec = PDComplexFileSpecification()
    assert spec.has_file_unix() is False
    spec.set_file_unix("/usr/share/doc.pdf")
    assert spec.has_file_unix() is True


def test_has_volatile_distinguishes_explicit_from_default() -> None:
    spec = PDComplexFileSpecification()
    # Spec default of False is not the same as an explicit /V false.
    assert spec.has_volatile() is False
    assert spec.is_volatile() is False
    spec.set_volatile(False)
    # After explicit set, /V is present even though the value is the
    # spec default.
    assert spec.has_volatile() is True
    assert spec.is_volatile() is False


def test_has_embedded_files_round_trip() -> None:
    spec = PDComplexFileSpecification()
    assert spec.has_embedded_files() is False
    spec.set_embedded_file(PDEmbeddedFile())
    assert spec.has_embedded_files() is True


def test_has_file_description_round_trip() -> None:
    spec = PDComplexFileSpecification()
    assert spec.has_file_description() is False
    spec.set_file_description("attachment description")
    assert spec.has_file_description() is True


def test_has_af_relationship_round_trip() -> None:
    spec = PDComplexFileSpecification()
    assert spec.has_af_relationship() is False
    spec.set_af_relationship("Data")
    assert spec.has_af_relationship() is True
    spec.set_af_relationship(None)
    assert spec.has_af_relationship() is False


# ---------- clear_* ----------


def test_clear_volatile_removes_explicit_entry() -> None:
    spec = PDComplexFileSpecification()
    spec.set_volatile(True)
    assert spec.has_volatile() is True
    spec.clear_volatile()
    assert spec.has_volatile() is False
    # Effective value falls back to spec default of False.
    assert spec.is_volatile() is False


def test_clear_file_description_removes_entry() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file_description("doomed")
    assert spec.has_file_description() is True
    spec.clear_file_description()
    assert spec.has_file_description() is False
    assert spec.get_file_description() is None


def test_clear_af_relationship_removes_entry() -> None:
    spec = PDComplexFileSpecification()
    spec.set_af_relationship("Data")
    spec.clear_af_relationship()
    assert spec.has_af_relationship() is False
    assert spec.get_af_relationship() is None


def test_clear_embedded_files_drops_ef_dictionary() -> None:
    spec = PDComplexFileSpecification()
    embedded = PDEmbeddedFile()
    spec.set_embedded_file(embedded)
    spec.set_embedded_file_unicode(PDEmbeddedFile())
    assert spec.has_embedded_files() is True
    spec.clear_embedded_files()
    assert spec.has_embedded_files() is False
    assert spec.get_embedded_file() is None
    assert spec.get_embedded_file_unicode() is None


def test_clear_embedded_files_then_re_add_rebuilds_ef() -> None:
    # After clear, a subsequent set_embedded_file must rebuild the /EF
    # sub-dictionary (the cached reference was invalidated).
    spec = PDComplexFileSpecification()
    spec.set_embedded_file(PDEmbeddedFile())
    spec.clear_embedded_files()
    fresh = PDEmbeddedFile()
    spec.set_embedded_file(fresh)
    assert spec.has_embedded_files() is True
    fetched = spec.get_embedded_file()
    assert fetched is not None
    assert fetched.get_cos_object() is fresh.get_cos_object()


# ---------- is_empty ----------


def test_is_empty_true_on_fresh_spec() -> None:
    spec = PDComplexFileSpecification()
    # A fresh spec has only /Type /Filespec — that doesn't constitute
    # "content" for the purposes of emptiness.
    assert spec.is_empty() is True


def test_is_empty_false_after_set_file() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file("doc.pdf")
    assert spec.is_empty() is False


def test_is_empty_false_after_set_file_unicode() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file_unicode("doc.pdf")
    assert spec.is_empty() is False


def test_is_empty_false_after_set_embedded_file() -> None:
    spec = PDComplexFileSpecification()
    spec.set_embedded_file(PDEmbeddedFile())
    assert spec.is_empty() is False


def test_is_empty_false_after_set_description() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file_description("attachment")
    assert spec.is_empty() is False


def test_is_empty_false_after_set_af_relationship() -> None:
    spec = PDComplexFileSpecification()
    spec.set_af_relationship("Data")
    assert spec.is_empty() is False


def test_is_empty_ignores_v_default() -> None:
    # /V default is False — even an explicit /V doesn't count toward
    # emptiness because the meaningful test is "are there any filename
    # / embedded-file / description / relationship entries".
    spec = PDComplexFileSpecification()
    spec.set_volatile(False)
    assert spec.is_empty() is True
    spec.set_volatile(True)
    # /V true alone still doesn't make the spec "non-empty" — it's
    # metadata about a file that hasn't been named yet.
    assert spec.is_empty() is True


def test_is_empty_round_trips_through_clear() -> None:
    spec = PDComplexFileSpecification()
    spec.set_file("doc.pdf")
    spec.set_file_unicode("doc.pdf")
    spec.set_file_description("description")
    spec.set_af_relationship("Data")
    spec.set_embedded_file(PDEmbeddedFile())
    assert spec.is_empty() is False
    # Drop each entry and confirm we return to empty.
    cos = spec.get_cos_object()
    cos.remove_item(COSName.get_pdf_name("F"))
    cos.remove_item(COSName.get_pdf_name("UF"))
    spec.clear_file_description()
    spec.clear_af_relationship()
    spec.clear_embedded_files()
    assert spec.is_empty() is True


def test_is_empty_wrap_existing_filled_dict() -> None:
    # Constructed-from-existing should reflect the existing state.
    raw = COSDictionary()
    raw.set_string(COSName.get_pdf_name("F"), "doc.pdf")
    spec = PDComplexFileSpecification(raw)
    assert spec.is_empty() is False


# ---------- public ``get_ef_dictionary`` / ``get_object_from_ef_dictionary``


def test_get_ef_dictionary_returns_ef_subdictionary_when_present() -> None:
    """``get_ef_dictionary`` public delegate must return the same
    ``COSDictionary`` as the private ``_get_ef_dictionary`` helper."""
    spec = PDComplexFileSpecification()
    spec.set_embedded_file(PDEmbeddedFile())
    ef = spec.get_ef_dictionary()
    assert isinstance(ef, COSDictionary)
    # ``/EF`` round-trip — the public getter reflects the same entry the
    # complex spec wrote when ``set_embedded_file`` was called.
    assert ef is spec.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("EF")
    )


def test_get_ef_dictionary_returns_none_when_no_ef_entry() -> None:
    spec = PDComplexFileSpecification()
    assert spec.get_ef_dictionary() is None


def test_get_object_from_ef_dictionary_returns_stored_stream() -> None:
    """``get_object_from_ef_dictionary`` public delegate must return the
    ``COSStream`` stored under the named slot."""
    spec = PDComplexFileSpecification()
    ef = PDEmbeddedFile()
    spec.set_embedded_file(ef)
    # ``/F`` is the slot used by ``set_embedded_file``.
    stored = spec.get_object_from_ef_dictionary(COSName.get_pdf_name("F"))
    assert stored is not None
    assert stored is ef.get_cos_object()


def test_get_object_from_ef_dictionary_returns_none_when_ef_absent() -> None:
    spec = PDComplexFileSpecification()
    assert (
        spec.get_object_from_ef_dictionary(COSName.get_pdf_name("F")) is None
    )


def test_get_object_from_ef_dictionary_returns_none_for_missing_key() -> None:
    spec = PDComplexFileSpecification()
    spec.set_embedded_file(PDEmbeddedFile())
    assert (
        spec.get_object_from_ef_dictionary(COSName.get_pdf_name("Unix"))
        is None
    )
