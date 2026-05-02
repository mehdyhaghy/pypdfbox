"""Upstream-equivalent parity tests for ``PDArtifactMarkedContent``.

Apache PDFBox 3.0.x ships no dedicated JUnit unit-test class for
``PDArtifactMarkedContent``. This file captures the upstream behavioural
contract for the artifact-tagged subclass: the ``Artifact`` BMC tag, ``/Type``
/ ``/Subtype`` accessors, ``/BBox`` parsing, and ``/Attached`` edge probes.

If upstream ever adds a dedicated ``PDArtifactMarkedContentTest.java``, port
those tests here.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.markedcontent import (
    PDArtifactMarkedContent,
    PDMarkedContent,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def test_subclass_of_pd_marked_content() -> None:
    assert issubclass(PDArtifactMarkedContent, PDMarkedContent)


def test_constructor_sets_artifact_tag_automatically() -> None:
    artifact = PDArtifactMarkedContent(COSDictionary())
    assert artifact.get_tag() == "Artifact"


def test_create_factory_returns_artifact_subclass() -> None:
    mc = PDMarkedContent.create(COSName.get_pdf_name("Artifact"), COSDictionary())
    assert isinstance(mc, PDArtifactMarkedContent)


def test_get_type_round_trip() -> None:
    props = COSDictionary()
    props.set_name(COSName.TYPE, "Pagination")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_type() == "Pagination"


def test_get_subtype_round_trip() -> None:
    props = COSDictionary()
    props.set_name(COSName.SUBTYPE, "Header")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_subtype() == "Header"


def test_get_b_box_parses_four_element_array() -> None:
    props = COSDictionary()
    bbox = COSArray()
    bbox.set_int(0, 0)
    bbox.set_int(1, 0)
    bbox.set_int(2, 612)
    bbox.set_int(3, 792)
    props.set_item(COSName.get_pdf_name("BBox"), bbox)
    artifact = PDArtifactMarkedContent(props)
    rect = artifact.get_b_box()
    assert isinstance(rect, PDRectangle)
    assert rect.get_lower_left_x() == 0
    assert rect.get_lower_left_y() == 0
    assert rect.get_upper_right_x() == 612
    assert rect.get_upper_right_y() == 792


def test_get_b_box_returns_none_when_absent() -> None:
    artifact = PDArtifactMarkedContent(COSDictionary())
    assert artifact.get_b_box() is None


def test_attached_edges_recognised() -> None:
    props = COSDictionary()
    arr = COSArray()
    arr.set_name(0, "Top")
    arr.set_name(1, "Left")
    props.set_item(COSName.get_pdf_name("Attached"), arr)
    artifact = PDArtifactMarkedContent(props)
    assert artifact.is_top_attached() is True
    assert artifact.is_left_attached() is True
    assert artifact.is_bottom_attached() is False
    assert artifact.is_right_attached() is False


def test_attached_absent_returns_false_for_all_edges() -> None:
    artifact = PDArtifactMarkedContent(COSDictionary())
    assert artifact.is_top_attached() is False
    assert artifact.is_bottom_attached() is False
    assert artifact.is_left_attached() is False
    assert artifact.is_right_attached() is False


def test_null_properties_is_safe() -> None:
    artifact = PDArtifactMarkedContent(None)
    assert artifact.get_type() is None
    assert artifact.get_subtype() is None
    assert artifact.get_b_box() is None
    assert artifact.is_top_attached() is False


def test_get_type_resolves_string_operand_like_get_name_as_string() -> None:
    """Upstream ``getNameAsString`` (called by ``getType``) accepts both
    ``COSName`` and ``COSString``. Mirror that contract: a ``COSString``
    operand on ``/Type`` resolves to its decoded value."""
    props = COSDictionary()
    props.set_string(COSName.TYPE, "Pagination")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_type() == "Pagination"


def test_get_subtype_resolves_string_operand_like_get_name_as_string() -> None:
    """Mirror of the ``/Type`` parity test above for ``/Subtype``."""
    props = COSDictionary()
    props.set_string(COSName.SUBTYPE, "Header")
    artifact = PDArtifactMarkedContent(props)
    assert artifact.get_subtype() == "Header"
