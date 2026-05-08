from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSObject, COSString
from pypdfbox.pdmodel.common.filespecification import PDComplexFileSpecification


def test_wave328_af_relationship_reads_string_form() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("AFRelationship"), COSString("Data"))

    spec = PDComplexFileSpecification(raw)

    assert spec.get_af_relationship() == "Data"


def test_wave328_af_relationship_reads_indirect_string_form() -> None:
    raw = COSDictionary()
    raw.set_item(
        COSName.get_pdf_name("AFRelationship"),
        COSObject(328, 0, resolved=COSString("Source")),
    )

    spec = PDComplexFileSpecification(raw)

    assert spec.get_af_relationship() == "Source"
