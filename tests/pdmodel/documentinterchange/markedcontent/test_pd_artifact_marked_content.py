"""Hand-written tests for ``PDArtifactMarkedContent`` at the upstream-equivalent
import path ``pypdfbox.pdmodel.documentinterchange.markedcontent``.

The canonical implementation currently lives under
:mod:`pypdfbox.pdmodel.documentinterchange.taggedpdf` (a historical placement),
but PDFBox 3.0.x exposes the class under the ``markedcontent`` package. This
file exercises it via the upstream-equivalent path and asserts identity with
the taggedpdf re-export so both import paths refer to the same class.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.markedcontent import (
    PDArtifactMarkedContent,
    PDMarkedContent,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

# ---------- import path identity ----------


def test_markedcontent_and_taggedpdf_export_same_class() -> None:
    from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
        PDArtifactMarkedContent as TaggedPDFArtifact,
    )

    assert PDArtifactMarkedContent is TaggedPDFArtifact


# ---------- construction ----------


def test_tag_is_artifact_when_built_directly() -> None:
    artifact = PDArtifactMarkedContent(COSDictionary())
    assert artifact.get_tag() == "Artifact"


def test_constructor_accepts_none_properties() -> None:
    artifact = PDArtifactMarkedContent(None)
    assert artifact.get_properties() is None
    assert artifact.get_type() is None
    assert artifact.get_subtype() is None
    assert artifact.get_b_box() is None
    assert artifact.is_top_attached() is False
    assert artifact.is_bottom_attached() is False
    assert artifact.is_left_attached() is False
    assert artifact.is_right_attached() is False


def test_create_factory_dispatches_artifact_tag_to_subclass() -> None:
    props = COSDictionary()
    mc = PDMarkedContent.create(COSName.get_pdf_name("Artifact"), props)
    assert isinstance(mc, PDArtifactMarkedContent)
    assert mc.get_properties() is props
    assert mc.get_tag() == "Artifact"


def test_create_factory_does_not_dispatch_for_non_artifact_tag() -> None:
    mc = PDMarkedContent.create(COSName.get_pdf_name("P"), COSDictionary())
    assert not isinstance(mc, PDArtifactMarkedContent)


# ---------- /Type and /Subtype ----------


def test_get_type_returns_pagination() -> None:
    props = COSDictionary()
    props.set_name(COSName.TYPE, "Pagination")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_type() == "Pagination"


def test_get_type_returns_layout() -> None:
    props = COSDictionary()
    props.set_name(COSName.TYPE, "Layout")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_type() == "Layout"


def test_get_type_returns_page() -> None:
    props = COSDictionary()
    props.set_name(COSName.TYPE, "Page")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_type() == "Page"


def test_get_type_returns_none_when_absent() -> None:
    artifact = PDArtifactMarkedContent(COSDictionary())
    assert artifact.get_type() is None


def test_get_subtype_returns_header() -> None:
    props = COSDictionary()
    props.set_name(COSName.SUBTYPE, "Header")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_subtype() == "Header"


def test_get_subtype_returns_footer() -> None:
    props = COSDictionary()
    props.set_name(COSName.SUBTYPE, "Footer")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_subtype() == "Footer"


def test_get_subtype_returns_watermark() -> None:
    props = COSDictionary()
    props.set_name(COSName.SUBTYPE, "Watermark")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_subtype() == "Watermark"


def test_get_subtype_returns_none_when_absent() -> None:
    artifact = PDArtifactMarkedContent(COSDictionary())
    assert artifact.get_subtype() is None


# ---------- /BBox ----------


def test_get_b_box_returns_rectangle_when_present() -> None:
    props = COSDictionary()
    bbox = COSArray()
    bbox.set_int(0, 5)
    bbox.set_int(1, 10)
    bbox.set_int(2, 105)
    bbox.set_int(3, 210)
    props.set_item(COSName.get_pdf_name("BBox"), bbox)
    artifact = PDArtifactMarkedContent(props)
    rect = artifact.get_b_box()
    assert isinstance(rect, PDRectangle)
    assert rect.get_lower_left_x() == 5
    assert rect.get_lower_left_y() == 10
    assert rect.get_upper_right_x() == 105
    assert rect.get_upper_right_y() == 210


def test_get_b_box_returns_none_when_absent() -> None:
    artifact = PDArtifactMarkedContent(COSDictionary())
    assert artifact.get_b_box() is None


def test_get_b_box_returns_none_when_value_is_not_an_array() -> None:
    props = COSDictionary()
    props.set_name(COSName.get_pdf_name("BBox"), "Bogus")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_b_box() is None


# ---------- /Attached ----------


def _attached(*edges: str) -> COSDictionary:
    props = COSDictionary()
    arr = COSArray()
    for i, edge in enumerate(edges):
        arr.set_name(i, edge)
    props.set_item(COSName.get_pdf_name("Attached"), arr)
    return props


def test_top_attached_only() -> None:
    artifact = PDArtifactMarkedContent(_attached("Top"))
    assert artifact.is_top_attached() is True
    assert artifact.is_bottom_attached() is False
    assert artifact.is_left_attached() is False
    assert artifact.is_right_attached() is False


def test_bottom_attached_only() -> None:
    artifact = PDArtifactMarkedContent(_attached("Bottom"))
    assert artifact.is_bottom_attached() is True


def test_left_attached_only() -> None:
    artifact = PDArtifactMarkedContent(_attached("Left"))
    assert artifact.is_left_attached() is True


def test_right_attached_only() -> None:
    artifact = PDArtifactMarkedContent(_attached("Right"))
    assert artifact.is_right_attached() is True


def test_all_edges_attached() -> None:
    artifact = PDArtifactMarkedContent(
        _attached("Top", "Bottom", "Left", "Right")
    )
    assert artifact.is_top_attached() is True
    assert artifact.is_bottom_attached() is True
    assert artifact.is_left_attached() is True
    assert artifact.is_right_attached() is True


def test_attached_unknown_edge_does_not_match_any_side() -> None:
    artifact = PDArtifactMarkedContent(_attached("Diagonal"))
    assert artifact.is_top_attached() is False
    assert artifact.is_bottom_attached() is False
    assert artifact.is_left_attached() is False
    assert artifact.is_right_attached() is False


def test_attached_is_not_an_array_returns_false() -> None:
    props = COSDictionary()
    props.set_name(COSName.get_pdf_name("Attached"), "NotAnArray")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.is_top_attached() is False


# ---------- inherited PDMarkedContent surface ----------


def test_inherits_marked_content_accessors() -> None:
    props = COSDictionary()
    props.set_int(COSName.get_pdf_name("MCID"), 3)
    props.set_name(COSName.get_pdf_name("Lang"), "de-DE")
    props.set_string(COSName.get_pdf_name("ActualText"), "echt")
    props.set_string(COSName.get_pdf_name("Alt"), "alternativ")
    props.set_string(COSName.get_pdf_name("E"), "Etwas")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_mcid() == 3
    assert artifact.get_language() == "de-DE"
    assert artifact.get_actual_text() == "echt"
    assert artifact.get_alternate_description() == "alternativ"
    assert artifact.get_expanded_form() == "Etwas"
    assert artifact.get_contents() == []
    artifact.add_text("text-position-stub")
    assert artifact.get_contents() == ["text-position-stub"]


# ---------- Wave 252: additive parity helpers ----------


def test_get_attached_edges_empty_when_properties_none() -> None:
    artifact = PDArtifactMarkedContent(None)
    assert artifact.get_attached_edges() == []


def test_get_attached_edges_empty_when_attached_absent() -> None:
    artifact = PDArtifactMarkedContent(COSDictionary())
    assert artifact.get_attached_edges() == []


def test_get_attached_edges_empty_when_attached_not_an_array() -> None:
    props = COSDictionary()
    props.set_name(COSName.get_pdf_name("Attached"), "NotAnArray")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_attached_edges() == []


def test_get_attached_edges_preserves_array_order() -> None:
    """Array order is part of the spec-visible state — preserve it
    rather than canonicalising into a sorted set or fixed Top/Bottom/Left/Right
    enumeration."""
    artifact = PDArtifactMarkedContent(_attached("Bottom", "Top", "Right"))
    assert artifact.get_attached_edges() == ["Bottom", "Top", "Right"]


def test_get_attached_edges_returns_unknown_edge_names_verbatim() -> None:
    """A spec extension may add new edges (or a producer may write a typo).
    Surface whatever name strings are in the array so callers can inspect
    them without re-walking the dict."""
    artifact = PDArtifactMarkedContent(_attached("Diagonal", "Top"))
    assert artifact.get_attached_edges() == ["Diagonal", "Top"]


def test_get_attached_edges_skips_non_name_entries() -> None:
    """A malformed array containing a non-name entry must not poison the
    result — skip it silently and surface the recognisable names."""
    props = COSDictionary()
    arr = COSArray()
    arr.set_name(0, "Top")
    arr.set_int(1, 99)  # garbage int between names
    arr.set_name(2, "Right")
    props.set_item(COSName.get_pdf_name("Attached"), arr)
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_attached_edges() == ["Top", "Right"]


def test_get_attached_edges_all_four() -> None:
    artifact = PDArtifactMarkedContent(
        _attached("Top", "Bottom", "Left", "Right")
    )
    assert artifact.get_attached_edges() == ["Top", "Bottom", "Left", "Right"]


def test_has_attached_false_when_properties_none() -> None:
    artifact = PDArtifactMarkedContent(None)
    assert artifact.has_attached() is False


def test_has_attached_false_when_attached_absent() -> None:
    artifact = PDArtifactMarkedContent(COSDictionary())
    assert artifact.has_attached() is False


def test_has_attached_false_when_attached_not_an_array() -> None:
    props = COSDictionary()
    props.set_name(COSName.get_pdf_name("Attached"), "NotAnArray")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.has_attached() is False


def test_has_attached_false_when_array_only_holds_non_name_entries() -> None:
    """Pure-int array yields no recognisable edges → ``has_attached`` is
    ``False`` even though the array exists."""
    props = COSDictionary()
    arr = COSArray()
    arr.set_int(0, 1)
    arr.set_int(1, 2)
    props.set_item(COSName.get_pdf_name("Attached"), arr)
    artifact = PDArtifactMarkedContent(props)
    assert artifact.has_attached() is False


def test_has_attached_true_when_one_edge_present() -> None:
    artifact = PDArtifactMarkedContent(_attached("Top"))
    assert artifact.has_attached() is True


def test_has_attached_true_for_unknown_edge_name() -> None:
    """Unknown edge names still count as "attached" — the spec allows
    extension and we should not discriminate the predicate against
    edges the four built-in accessors don't recognise."""
    artifact = PDArtifactMarkedContent(_attached("Diagonal"))
    assert artifact.has_attached() is True
    assert artifact.is_top_attached() is False
    assert artifact.is_bottom_attached() is False
    assert artifact.is_left_attached() is False
    assert artifact.is_right_attached() is False


def test_has_b_box_false_when_properties_none() -> None:
    artifact = PDArtifactMarkedContent(None)
    assert artifact.has_b_box() is False


def test_has_b_box_false_when_absent() -> None:
    artifact = PDArtifactMarkedContent(COSDictionary())
    assert artifact.has_b_box() is False


def test_has_b_box_false_when_value_is_not_array() -> None:
    props = COSDictionary()
    props.set_name(COSName.get_pdf_name("BBox"), "Bogus")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.has_b_box() is False


def test_has_b_box_true_when_array_present() -> None:
    props = COSDictionary()
    bbox = COSArray()
    bbox.set_int(0, 0)
    bbox.set_int(1, 0)
    bbox.set_int(2, 612)
    bbox.set_int(3, 792)
    props.set_item(COSName.get_pdf_name("BBox"), bbox)
    artifact = PDArtifactMarkedContent(props)
    assert artifact.has_b_box() is True
    rect = artifact.get_b_box()
    assert rect is not None
    assert rect.get_upper_right_x() == 612
