"""PDFBOX-6303: ``PDMarkedContent`` records the ``/StructParents`` key."""

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.documentinterchange.markedcontent import PDMarkedContent


def test_struct_parent_defaults_to_minus_one() -> None:
    assert PDMarkedContent(COSName.get_pdf_name("P"), None).get_struct_parent() == -1


def test_struct_parent_round_trip() -> None:
    mc = PDMarkedContent.create(COSName.get_pdf_name("Span"), None)
    mc.set_struct_parent(7)
    assert mc.get_struct_parent() == 7
    assert mc.to_string().endswith(", structParent=7")


def test_artifact_struct_parent() -> None:
    mc = PDMarkedContent.create(COSName.get_pdf_name("Artifact"), None)
    assert mc.get_struct_parent() == -1
    mc.set_struct_parent(3)
    assert mc.get_struct_parent() == 3
