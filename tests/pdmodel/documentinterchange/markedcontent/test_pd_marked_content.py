from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.markedcontent.pd_marked_content import (
    PDMarkedContent,
)


def test_tag_stored_as_plain_name_string() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("Span"), COSDictionary())
    assert mc.get_tag() == "Span"


def test_tag_none_passes_through_as_none() -> None:
    mc = PDMarkedContent(None, COSDictionary())
    assert mc.get_tag() is None


def test_properties_round_trip() -> None:
    props = COSDictionary()
    mc = PDMarkedContent(COSName.get_pdf_name("P"), props)
    assert mc.get_properties() is props


def test_mcid_minus_one_when_properties_none() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), None)
    assert mc.get_mcid() == -1


def test_mcid_minus_one_when_absent() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), COSDictionary())
    assert mc.get_mcid() == -1


def test_mcid_returns_value_when_present() -> None:
    props = COSDictionary()
    props.set_int(COSName.get_pdf_name("MCID"), 42)
    mc = PDMarkedContent(COSName.get_pdf_name("P"), props)
    assert mc.get_mcid() == 42


def test_language_actual_text_alt_expanded_default_to_none() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), None)
    assert mc.get_language() is None
    assert mc.get_actual_text() is None
    assert mc.get_alternate_description() is None
    assert mc.get_expanded_form() is None


def test_language_returned_when_present() -> None:
    props = COSDictionary()
    props.set_name(COSName.get_pdf_name("Lang"), "fr-CA")
    mc = PDMarkedContent(COSName.get_pdf_name("P"), props)
    assert mc.get_language() == "fr-CA"


def test_actual_text_alt_expanded_returned_when_present() -> None:
    props = COSDictionary()
    props.set_string(COSName.get_pdf_name("ActualText"), "real")
    props.set_string(COSName.get_pdf_name("Alt"), "alt")
    props.set_string(COSName.get_pdf_name("E"), "Etc.")
    mc = PDMarkedContent(COSName.get_pdf_name("P"), props)
    assert mc.get_actual_text() == "real"
    assert mc.get_alternate_description() == "alt"
    assert mc.get_expanded_form() == "Etc."


def test_contents_starts_empty_and_accepts_mixed_items() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), COSDictionary())
    assert mc.get_contents() == []
    mc.add_text("stub-text-position")
    child = PDMarkedContent(COSName.get_pdf_name("Span"), COSDictionary())
    mc.add_marked_content(child)
    mc.add_x_object("stub-xobject")
    assert mc.get_contents() == ["stub-text-position", child, "stub-xobject"]


def test_create_returns_plain_marked_content_for_non_artifact() -> None:
    mc = PDMarkedContent.create(COSName.get_pdf_name("Span"), COSDictionary())
    assert type(mc) is PDMarkedContent
    assert mc.get_tag() == "Span"


def test_create_dispatches_artifact_to_subclass() -> None:
    # Local import to confirm the subclass branch.
    from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
        PDArtifactMarkedContent,
    )

    mc = PDMarkedContent.create(COSName.get_pdf_name("Artifact"), COSDictionary())
    assert isinstance(mc, PDArtifactMarkedContent)


# ---------- MCID linkage with PDStructureElement / PDMarkedContentReference ----------


def test_mcid_round_trips_via_marked_content_reference() -> None:
    """The MCID stored on a BDC's properties must round-trip through a
    ``PDMarkedContentReference`` so the structure tree can resolve a
    structure element back to its on-page marked-content sequence.

    Mirrors the PDF/UA invariant: ``PDMarkedContent.get_mcid()`` and
    ``PDMarkedContentReference.get_mcid()`` agree for the same MCID.
    """
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_marked_content_reference import (
        PDMarkedContentReference,
    )

    props = COSDictionary()
    props.set_int(COSName.get_pdf_name("MCID"), 12)
    mc = PDMarkedContent(COSName.get_pdf_name("P"), props)

    mcr = PDMarkedContentReference()
    mcr.set_mcid(mc.get_mcid())

    assert mcr.get_mcid() == mc.get_mcid() == 12


def test_pd_marked_content_str_alias_matches_repr() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("Span"), COSDictionary())
    # ``__str__`` mirrors ``toString`` — delegates to ``__repr__``.
    assert str(mc) == repr(mc)
