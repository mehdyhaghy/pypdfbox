"""Wave 1275 — PDArtifactMarkedContent.is_attached public helper."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.markedcontent import (
    PDArtifactMarkedContent,
)


def _props_with_attached(*edges: str) -> COSDictionary:
    props = COSDictionary()
    arr = COSArray()
    for edge in edges:
        arr.add(COSName.get_pdf_name(edge))
    props.set_item(COSName.get_pdf_name("Attached"), arr)
    return props


def test_is_attached_returns_true_for_listed_edge() -> None:
    artifact = PDArtifactMarkedContent(_props_with_attached("Top", "Right"))
    assert artifact.is_attached("Top") is True
    assert artifact.is_attached("Right") is True


def test_is_attached_returns_false_for_unlisted_edge() -> None:
    artifact = PDArtifactMarkedContent(_props_with_attached("Top"))
    assert artifact.is_attached("Bottom") is False
    assert artifact.is_attached("Left") is False


def test_is_attached_when_attached_absent() -> None:
    artifact = PDArtifactMarkedContent(COSDictionary())
    assert artifact.is_attached("Top") is False


def test_is_attached_when_properties_none() -> None:
    artifact = PDArtifactMarkedContent(None)
    assert artifact.is_attached("Top") is False


def test_is_attached_matches_named_predicates() -> None:
    artifact = PDArtifactMarkedContent(
        _props_with_attached("Top", "Bottom", "Left", "Right")
    )
    assert artifact.is_attached("Top") == artifact.is_top_attached()
    assert artifact.is_attached("Bottom") == artifact.is_bottom_attached()
    assert artifact.is_attached("Left") == artifact.is_left_attached()
    assert artifact.is_attached("Right") == artifact.is_right_attached()
