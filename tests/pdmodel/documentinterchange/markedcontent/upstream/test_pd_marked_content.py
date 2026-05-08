"""Upstream-equivalent parity tests for ``PDMarkedContent``.

Apache PDFBox 3.0.x ships no dedicated JUnit unit-test class for
``PDMarkedContent`` — the class is exercised indirectly through
``PDFMarkedContentExtractor`` integration tests against sample PDFs. This file
captures the upstream behavioural contract by exercising the public API
surface (constructor, ``create`` factory, accessors, mutators) the way
upstream callers do.

If upstream ever adds a dedicated ``PDMarkedContentTest.java``, port those
tests here.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.markedcontent import (
    PDArtifactMarkedContent,
    PDMarkedContent,
)


def test_constructor_records_tag_name_string() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("Span"), COSDictionary())
    assert mc.get_tag() == "Span"


def test_constructor_accepts_null_tag() -> None:
    mc = PDMarkedContent(None, COSDictionary())
    assert mc.get_tag() is None


def test_constructor_accepts_null_properties() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), None)
    assert mc.get_properties() is None


def test_get_mcid_returns_minus_one_when_properties_are_null() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), None)
    assert mc.get_mcid() == -1


def test_get_mcid_returns_minus_one_when_property_absent() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), COSDictionary())
    assert mc.get_mcid() == -1


def test_get_mcid_returns_value_when_present() -> None:
    props = COSDictionary()
    props.set_int(COSName.get_pdf_name("MCID"), 17)
    mc = PDMarkedContent(COSName.get_pdf_name("P"), props)
    assert mc.get_mcid() == 17


def test_get_language_returns_lang_value() -> None:
    props = COSDictionary()
    props.set_name(COSName.get_pdf_name("Lang"), "en-GB")
    mc = PDMarkedContent(COSName.get_pdf_name("P"), props)
    assert mc.get_language() == "en-GB"


def test_get_language_resolves_string_operand_like_get_name_as_string() -> None:
    props = COSDictionary()
    props.set_string(COSName.get_pdf_name("Lang"), "en-US")
    mc = PDMarkedContent(COSName.get_pdf_name("P"), props)
    assert mc.get_language() == "en-US"


def test_get_actual_text_returns_string_value() -> None:
    props = COSDictionary()
    props.set_string(COSName.get_pdf_name("ActualText"), "actual")
    mc = PDMarkedContent(COSName.get_pdf_name("P"), props)
    assert mc.get_actual_text() == "actual"


def test_get_alternate_description_returns_alt_value() -> None:
    props = COSDictionary()
    props.set_string(COSName.get_pdf_name("Alt"), "alt")
    mc = PDMarkedContent(COSName.get_pdf_name("P"), props)
    assert mc.get_alternate_description() == "alt"


def test_get_expanded_form_returns_e_value() -> None:
    props = COSDictionary()
    props.set_string(COSName.get_pdf_name("E"), "expansion")
    mc = PDMarkedContent(COSName.get_pdf_name("P"), props)
    assert mc.get_expanded_form() == "expansion"


def test_contents_starts_empty() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), COSDictionary())
    assert mc.get_contents() == []


def test_add_text_appends_to_contents() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), COSDictionary())
    mc.add_text("text-position-stub")
    assert mc.get_contents() == ["text-position-stub"]


def test_add_marked_content_appends_to_contents() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), COSDictionary())
    child = PDMarkedContent(COSName.get_pdf_name("Span"), COSDictionary())
    mc.add_marked_content(child)
    assert mc.get_contents() == [child]


def test_add_x_object_appends_to_contents() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), COSDictionary())
    mc.add_x_object("xobject-stub")
    assert mc.get_contents() == ["xobject-stub"]


def test_create_returns_plain_marked_content_for_non_artifact_tag() -> None:
    mc = PDMarkedContent.create(COSName.get_pdf_name("Span"), COSDictionary())
    assert type(mc) is PDMarkedContent
    assert mc.get_tag() == "Span"


def test_create_returns_artifact_subclass_for_artifact_tag() -> None:
    props = COSDictionary()
    mc = PDMarkedContent.create(COSName.get_pdf_name("Artifact"), props)
    assert isinstance(mc, PDArtifactMarkedContent)
    assert mc.get_tag() == "Artifact"
    assert mc.get_properties() is props


def test_repr_contains_tag_properties_and_contents() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("Span"), COSDictionary())
    rendered = repr(mc)
    assert "tag=Span" in rendered
    assert "properties=" in rendered
    assert "contents=" in rendered


def test_str_matches_repr_mirrors_to_string() -> None:
    # Upstream's ``toString`` is reachable in Python via ``str(obj)``.
    # ``__str__`` delegates to ``__repr__`` so both paths return the same
    # upstream-formatted string.
    mc = PDMarkedContent(COSName.get_pdf_name("Span"), COSDictionary())
    assert str(mc) == repr(mc)
    assert "tag=Span" in str(mc)
