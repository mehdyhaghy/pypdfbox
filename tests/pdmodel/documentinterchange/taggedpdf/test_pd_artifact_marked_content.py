from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.markedcontent.pd_marked_content import (
    PDMarkedContent,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDArtifactMarkedContent,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

# ---------- construction ----------


def test_tag_is_artifact_when_built_directly() -> None:
    artifact = PDArtifactMarkedContent(COSDictionary())
    assert artifact.get_tag() == "Artifact"


def test_create_dispatches_artifact_tag_to_subclass() -> None:
    props = COSDictionary()
    mc = PDMarkedContent.create(COSName.get_pdf_name("Artifact"), props)
    assert isinstance(mc, PDArtifactMarkedContent)
    assert mc.get_properties() is props


def test_create_does_not_dispatch_for_other_tag() -> None:
    mc = PDMarkedContent.create(COSName.get_pdf_name("P"), COSDictionary())
    assert not isinstance(mc, PDArtifactMarkedContent)
    assert type(mc) is PDMarkedContent
    assert mc.get_tag() == "P"


def test_constructor_accepts_none_properties() -> None:
    artifact = PDArtifactMarkedContent(None)
    assert artifact.get_properties() is None
    assert artifact.get_type() is None
    assert artifact.get_subtype() is None
    assert artifact.get_b_box() is None
    assert artifact.is_top_attached() is False


# ---------- /Type and /Subtype ----------


def test_get_type_returns_name_when_present() -> None:
    props = COSDictionary()
    props.set_name(COSName.TYPE, "Pagination")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_type() == "Pagination"


def test_get_type_returns_none_when_absent() -> None:
    artifact = PDArtifactMarkedContent(COSDictionary())
    assert artifact.get_type() is None


def test_get_subtype_returns_name_when_present() -> None:
    props = COSDictionary()
    props.set_name(COSName.SUBTYPE, "Header")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_subtype() == "Header"


def test_get_subtype_returns_none_when_absent() -> None:
    artifact = PDArtifactMarkedContent(COSDictionary())
    assert artifact.get_subtype() is None


# ---------- /BBox ----------


def test_get_b_box_returns_rectangle_when_present() -> None:
    props = COSDictionary()
    bbox = COSArray()
    bbox.set_int(0, 10)
    bbox.set_int(1, 20)
    bbox.set_int(2, 110)
    bbox.set_int(3, 220)
    props.set_item(COSName.get_pdf_name("BBox"), bbox)

    artifact = PDArtifactMarkedContent(props)
    rect = artifact.get_b_box()

    assert isinstance(rect, PDRectangle)
    assert rect.get_lower_left_x() == 10
    assert rect.get_lower_left_y() == 20
    assert rect.get_upper_right_x() == 110
    assert rect.get_upper_right_y() == 220


def test_get_b_box_returns_none_when_absent() -> None:
    artifact = PDArtifactMarkedContent(COSDictionary())
    assert artifact.get_b_box() is None


def test_get_b_box_returns_none_when_not_an_array() -> None:
    props = COSDictionary()
    props.set_name(COSName.get_pdf_name("BBox"), "Bogus")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_b_box() is None


def test_get_bbox_alias_matches_get_b_box() -> None:
    """``get_bbox`` is the spelling used by sibling pypdfbox wrappers
    (e.g. :meth:`PDPage.get_bbox`); it must return the same object as
    the mechanical-translation form ``get_b_box``."""
    props = COSDictionary()
    bbox = COSArray()
    bbox.set_int(0, 1)
    bbox.set_int(1, 2)
    bbox.set_int(2, 3)
    bbox.set_int(3, 4)
    props.set_item(COSName.get_pdf_name("BBox"), bbox)
    artifact = PDArtifactMarkedContent(props)

    rect_a = artifact.get_b_box()
    rect_b = artifact.get_bbox()

    assert isinstance(rect_b, PDRectangle)
    # PDRectangle wraps the same backing array — the four corners must
    # match across both spellings.
    assert (
        rect_a.get_lower_left_x(),
        rect_a.get_lower_left_y(),
        rect_a.get_upper_right_x(),
        rect_a.get_upper_right_y(),
    ) == (
        rect_b.get_lower_left_x(),
        rect_b.get_lower_left_y(),
        rect_b.get_upper_right_x(),
        rect_b.get_upper_right_y(),
    )


def test_get_bbox_alias_returns_none_when_absent() -> None:
    artifact = PDArtifactMarkedContent(COSDictionary())
    assert artifact.get_bbox() is None


def test_get_bbox_alias_returns_none_when_properties_none() -> None:
    artifact = PDArtifactMarkedContent(None)
    assert artifact.get_bbox() is None


# ---------- /Type and /Subtype as COSString (upstream getNameAsString parity) ----------


def test_get_type_accepts_cos_string_value() -> None:
    """Upstream ``COSDictionary.getNameAsString`` accepts both ``COSName``
    and ``COSString`` operands. PDFs in the wild encode ``/Type`` as a
    string literal in some authoring tools; pypdfbox must read those
    correctly rather than silently returning ``None``.
    """
    props = COSDictionary()
    # Stored as a COSString rather than a COSName.
    props.set_string(COSName.TYPE, "Pagination")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_type() == "Pagination"


def test_get_subtype_accepts_cos_string_value() -> None:
    """Mirror of ``test_get_type_accepts_cos_string_value`` for
    ``/Subtype``."""
    props = COSDictionary()
    props.set_string(COSName.SUBTYPE, "Header")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_subtype() == "Header"


def test_get_type_returns_none_for_unrelated_value_type() -> None:
    """``getNameAsString`` only resolves ``COSName``/``COSString`` —
    other operand types (integers, arrays, etc.) yield ``None``.
    """
    from pypdfbox.cos import COSArray as _COSArray

    props = COSDictionary()
    props.set_item(COSName.TYPE, _COSArray())
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_type() is None


# ---------- /Attached ----------


def _props_with_attached(*edges: str) -> COSDictionary:
    props = COSDictionary()
    arr = COSArray()
    for i, edge in enumerate(edges):
        arr.set_name(i, edge)
    props.set_item(COSName.get_pdf_name("Attached"), arr)
    return props


def test_is_top_attached_true_when_listed() -> None:
    artifact = PDArtifactMarkedContent(_props_with_attached("Top"))
    assert artifact.is_top_attached() is True
    assert artifact.is_bottom_attached() is False
    assert artifact.is_left_attached() is False
    assert artifact.is_right_attached() is False


def test_is_bottom_attached_true_when_listed() -> None:
    artifact = PDArtifactMarkedContent(_props_with_attached("Bottom"))
    assert artifact.is_bottom_attached() is True


def test_is_left_attached_true_when_listed() -> None:
    artifact = PDArtifactMarkedContent(_props_with_attached("Left"))
    assert artifact.is_left_attached() is True


def test_is_right_attached_true_when_listed() -> None:
    artifact = PDArtifactMarkedContent(_props_with_attached("Right"))
    assert artifact.is_right_attached() is True


def test_multiple_edges_attached_all_report_true() -> None:
    artifact = PDArtifactMarkedContent(
        _props_with_attached("Top", "Bottom", "Left", "Right")
    )
    assert artifact.is_top_attached() is True
    assert artifact.is_bottom_attached() is True
    assert artifact.is_left_attached() is True
    assert artifact.is_right_attached() is True


def test_attached_missing_returns_false_for_all_edges() -> None:
    artifact = PDArtifactMarkedContent(COSDictionary())
    assert artifact.is_top_attached() is False
    assert artifact.is_bottom_attached() is False
    assert artifact.is_left_attached() is False
    assert artifact.is_right_attached() is False


def test_attached_not_an_array_returns_false() -> None:
    props = COSDictionary()
    props.set_name(COSName.get_pdf_name("Attached"), "NotAnArray")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.is_top_attached() is False


def test_attached_unknown_edge_does_not_match_any_side() -> None:
    artifact = PDArtifactMarkedContent(_props_with_attached("Center"))
    assert artifact.is_top_attached() is False
    assert artifact.is_bottom_attached() is False
    assert artifact.is_left_attached() is False
    assert artifact.is_right_attached() is False


# ---------- inheritance: PDMarkedContent surface ----------


def test_inherits_marked_content_accessors() -> None:
    props = COSDictionary()
    props.set_int(COSName.get_pdf_name("MCID"), 7)
    props.set_name(COSName.get_pdf_name("Lang"), "en-US")
    props.set_string(COSName.get_pdf_name("ActualText"), "hello")
    props.set_string(COSName.get_pdf_name("Alt"), "alt-text")
    props.set_string(COSName.get_pdf_name("E"), "Mr.")

    artifact = PDArtifactMarkedContent(props)

    assert artifact.get_mcid() == 7
    assert artifact.get_language() == "en-US"
    assert artifact.get_actual_text() == "hello"
    assert artifact.get_alternate_description() == "alt-text"
    assert artifact.get_expanded_form() == "Mr."
    # Contents list is shared with PDMarkedContent.
    assert artifact.get_contents() == []
    artifact.add_text("text-position-stub")
    assert artifact.get_contents() == ["text-position-stub"]
