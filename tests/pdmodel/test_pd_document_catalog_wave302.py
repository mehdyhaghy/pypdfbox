from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel import PDDocument


def _name(name: str) -> COSName:
    return COSName.get_pdf_name(name)


def test_has_associated_files_ignores_malformed_array_entries() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        files = COSArray()
        files.add(COSArray())
        files.add(_name("NotAFileSpec"))
        catalog.get_cos_object().set_item(_name("AF"), files)

        assert catalog.get_associated_files() == []
        assert catalog.has_associated_files() is False

        files.add(COSString("plain-file.txt"))

        assert len(catalog.get_associated_files()) == 1
        assert catalog.has_associated_files() is True


def test_has_requirements_ignores_malformed_array_entries() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        requirements = COSArray()
        requirements.add(COSString("not-a-requirement"))
        requirements.add(COSArray())
        catalog.get_cos_object().set_item(_name("Requirements"), requirements)

        assert catalog.get_requirements() == []
        assert catalog.has_requirements() is False

        requirement = COSDictionary()
        requirement.set_item(_name("S"), _name("EnableJavaScripts"))
        requirements.add(requirement)

        assert catalog.get_requirements() == [requirement]
        assert catalog.has_requirements() is True
