"""Wave 228 — round-out predicates, type accessor, and subtype constants
for ``PDOutputIntent``.

Targets the small enrichment surface added on top of upstream PDFBox 3.0
``PDOutputIntent``:

- subtype-name class constants (``GTS_PDFA1``, ``GTS_PDFX``, ``ISO_PDFE1``)
- ``get_type()`` typed ``/Type`` accessor
- ``is_pdfa()`` / ``is_pdfx()`` / ``is_pdfe()`` subtype predicates
- ``has_*()`` presence predicates for every optional entry
- ``__repr__`` for debug output
"""
from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.graphics.color import PDOutputIntent


# ---------- class-level subtype constants ----------


def test_subtype_constants_match_spec_strings() -> None:
    # Subtypes per PDF 32000-1 §14.11.5 — class constants are spelled
    # exactly as they round-trip into ``/S``.
    assert PDOutputIntent.GTS_PDFA1 == "GTS_PDFA1"
    assert PDOutputIntent.GTS_PDFX == "GTS_PDFX"
    assert PDOutputIntent.ISO_PDFE1 == "ISO_PDFE1"


def test_subtype_constants_are_strings() -> None:
    # Plain ``str`` (matching the value written into ``/S``) so callers
    # can compare ``get_subtype()`` against them directly without
    # round-tripping through ``COSName``.
    assert isinstance(PDOutputIntent.GTS_PDFA1, str)
    assert isinstance(PDOutputIntent.GTS_PDFX, str)
    assert isinstance(PDOutputIntent.ISO_PDFE1, str)


def test_subtype_constants_round_trip_through_set_subtype() -> None:
    intent = PDOutputIntent()
    intent.set_subtype(PDOutputIntent.GTS_PDFX)
    assert intent.get_subtype() == "GTS_PDFX"


# ---------- /Type accessor ----------


def test_get_type_fresh_intent_is_output_intent() -> None:
    intent = PDOutputIntent()
    assert intent.get_type() == "OutputIntent"


def test_get_type_absent_returns_none() -> None:
    # Wrap a dictionary that explicitly drops /Type after construction —
    # ensure get_type reports the absence rather than raising.
    intent = PDOutputIntent()
    intent.get_cos_object().remove_item(COSName.TYPE)  # type: ignore[attr-defined]
    assert intent.get_type() is None


def test_get_type_wrap_existing_with_type_preserves() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.get_pdf_name("OutputIntent"))  # type: ignore[attr-defined]
    intent = PDOutputIntent(raw)
    assert intent.get_type() == "OutputIntent"


# ---------- subtype predicates ----------


def test_is_pdfa_true_for_gts_pdfa1() -> None:
    intent = PDOutputIntent()
    intent.set_subtype("GTS_PDFA1")
    assert intent.is_pdfa() is True
    assert intent.is_pdfx() is False
    assert intent.is_pdfe() is False


def test_is_pdfx_true_for_gts_pdfx() -> None:
    intent = PDOutputIntent()
    intent.set_subtype("GTS_PDFX")
    assert intent.is_pdfx() is True
    assert intent.is_pdfa() is False
    assert intent.is_pdfe() is False


def test_is_pdfe_true_for_iso_pdfe1() -> None:
    intent = PDOutputIntent()
    intent.set_subtype("ISO_PDFE1")
    assert intent.is_pdfe() is True
    assert intent.is_pdfa() is False
    assert intent.is_pdfx() is False


def test_subtype_predicates_all_false_when_absent() -> None:
    # Fresh empty intent has no /S — every predicate returns False so
    # callers cannot accidentally infer a flavour from absence.
    intent = PDOutputIntent()
    assert intent.is_pdfa() is False
    assert intent.is_pdfx() is False
    assert intent.is_pdfe() is False


def test_subtype_predicates_unknown_subtype_all_false() -> None:
    # A producer-written exotic subtype should not match any registered
    # flavour predicate.
    intent = PDOutputIntent()
    intent.set_subtype("VENDOR_CUSTOM")
    assert intent.is_pdfa() is False
    assert intent.is_pdfx() is False
    assert intent.is_pdfe() is False


def test_subtype_predicates_case_sensitive() -> None:
    # ``/S`` is a PDF Name — case-sensitive per PDF 32000-1 §7.3.5.
    # The predicate compares against the canonical spelling.
    intent = PDOutputIntent()
    intent.set_subtype("gts_pdfa1")
    assert intent.is_pdfa() is False


# ---------- has_subtype ----------


def test_has_subtype_false_on_fresh_intent() -> None:
    intent = PDOutputIntent()
    assert intent.has_subtype() is False


def test_has_subtype_true_after_set() -> None:
    intent = PDOutputIntent()
    intent.set_subtype("GTS_PDFA1")
    assert intent.has_subtype() is True


def test_has_subtype_false_after_remove() -> None:
    intent = PDOutputIntent()
    intent.set_subtype("GTS_PDFA1")
    intent.set_subtype(None)
    assert intent.has_subtype() is False


# ---------- presence predicates for optional entries ----------


def test_has_info_round_trips_with_set() -> None:
    intent = PDOutputIntent()
    assert intent.has_info() is False
    intent.set_info("sRGB IEC61966-2.1")
    assert intent.has_info() is True


def test_has_output_condition_round_trips_with_set() -> None:
    intent = PDOutputIntent()
    assert intent.has_output_condition() is False
    intent.set_output_condition("sheet-fed offset")
    assert intent.has_output_condition() is True


def test_has_output_condition_identifier_round_trips() -> None:
    intent = PDOutputIntent()
    assert intent.has_output_condition_identifier() is False
    intent.set_output_condition_identifier("CGATS TR 001")
    assert intent.has_output_condition_identifier() is True


def test_has_registry_name_round_trips() -> None:
    intent = PDOutputIntent()
    assert intent.has_registry_name() is False
    intent.set_registry_name("http://www.color.org")
    assert intent.has_registry_name() is True


def test_has_dest_output_profile_round_trips() -> None:
    intent = PDOutputIntent()
    assert intent.has_dest_output_profile() is False
    intent.set_dest_output_profile(COSStream())
    assert intent.has_dest_output_profile() is True
    intent.set_dest_output_profile(None)
    assert intent.has_dest_output_profile() is False


def test_has_dest_output_profile_ref_round_trips() -> None:
    intent = PDOutputIntent()
    assert intent.has_dest_output_profile_ref() is False
    intent.set_dest_output_profile_ref(COSDictionary())
    assert intent.has_dest_output_profile_ref() is True
    intent.set_dest_output_profile_ref(None)
    assert intent.has_dest_output_profile_ref() is False


# ---------- __repr__ ----------


def test_repr_includes_subtype_and_oci() -> None:
    intent = PDOutputIntent()
    intent.set_subtype("GTS_PDFA1")
    intent.set_output_condition_identifier("sRGB IEC61966-2.1")
    out = repr(intent)
    assert "PDOutputIntent" in out
    assert "GTS_PDFA1" in out
    assert "sRGB IEC61966-2.1" in out


def test_repr_handles_missing_fields() -> None:
    # Empty intent should still produce a readable repr (no exceptions
    # on missing /S or /OutputConditionIdentifier).
    intent = PDOutputIntent()
    out = repr(intent)
    assert out.startswith("PDOutputIntent(")
    assert "None" in out
