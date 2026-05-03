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


# ---------- Wave 225: predicate helpers + container protocol ----------


def test_is_artifact_true_for_artifact_tag() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("Artifact"), COSDictionary())
    assert mc.is_artifact() is True


def test_is_artifact_false_for_other_tags() -> None:
    for tag in ("Span", "P", "H1", "Document", "Figure"):
        mc = PDMarkedContent(COSName.get_pdf_name(tag), COSDictionary())
        assert mc.is_artifact() is False, tag


def test_is_artifact_false_for_none_tag() -> None:
    mc = PDMarkedContent(None, COSDictionary())
    assert mc.is_artifact() is False


def test_is_artifact_true_on_pd_artifact_marked_content_subclass() -> None:
    """The dispatched subclass returned by :meth:`create` must agree with the
    predicate — the subclass sets its tag to ``"Artifact"`` via super()."""
    mc = PDMarkedContent.create(COSName.get_pdf_name("Artifact"), COSDictionary())
    assert mc.is_artifact() is True


def test_has_mcid_false_when_properties_none() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), None)
    assert mc.has_mcid() is False


def test_has_mcid_false_when_mcid_absent() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), COSDictionary())
    assert mc.has_mcid() is False


def test_has_mcid_true_when_mcid_zero() -> None:
    """``/MCID 0`` is a perfectly valid identifier — must not collide with the
    ``-1`` sentinel from :meth:`get_mcid`."""
    props = COSDictionary()
    props.set_int(COSName.get_pdf_name("MCID"), 0)
    mc = PDMarkedContent(COSName.get_pdf_name("P"), props)
    assert mc.has_mcid() is True
    assert mc.get_mcid() == 0


def test_has_mcid_true_when_positive() -> None:
    props = COSDictionary()
    props.set_int(COSName.get_pdf_name("MCID"), 7)
    mc = PDMarkedContent(COSName.get_pdf_name("P"), props)
    assert mc.has_mcid() is True


def test_len_empty_contents() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), COSDictionary())
    assert len(mc) == 0


def test_len_tracks_added_items() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), COSDictionary())
    mc.add_text("a")
    mc.add_text("b")
    mc.add_x_object("xo")
    assert len(mc) == 3
    assert len(mc) == len(mc.get_contents())


def test_iter_yields_contents_in_order() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), COSDictionary())
    child = PDMarkedContent(COSName.get_pdf_name("Span"), COSDictionary())
    mc.add_text("t1")
    mc.add_marked_content(child)
    mc.add_x_object("xo")
    assert list(mc) == ["t1", child, "xo"]


def test_iter_empty_when_no_contents() -> None:
    mc = PDMarkedContent(COSName.get_pdf_name("P"), COSDictionary())
    assert list(mc) == []


def test_iter_independent_from_get_contents_mutation_after_iter_start() -> None:
    """``__iter__`` returns a fresh iterator each call so callers can iterate
    twice without rewinding."""
    mc = PDMarkedContent(COSName.get_pdf_name("P"), COSDictionary())
    mc.add_text("only")
    assert list(mc) == ["only"]
    assert list(mc) == ["only"]
