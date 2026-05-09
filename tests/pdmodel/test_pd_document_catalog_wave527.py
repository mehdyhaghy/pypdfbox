from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.common.filespecification import (
    PDComplexFileSpecification,
    PDSimpleFileSpecification,
)
from pypdfbox.pdmodel.page_layout import PageLayout
from pypdfbox.pdmodel.page_mode import PageMode


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def test_wave527_acro_form_fixup_applies_once_and_refreshes_cache() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        first_form = COSDictionary()
        second_form = COSDictionary()

        class Fixup:
            def __init__(self, form: COSDictionary) -> None:
                self.form = form
                self.calls = 0

            def apply(self) -> None:
                self.calls += 1
                catalog.get_cos_object().set_item(_name("AcroForm"), self.form)

        first_fixup = Fixup(first_form)
        first = catalog.get_acro_form(first_fixup)
        again = catalog.get_acro_form(first_fixup)

        assert first is again
        assert first.get_cos_object() is first_form
        assert first_fixup.calls == 1

        second_fixup = Fixup(second_form)
        second = catalog.get_acro_form(second_fixup)

        assert second is not first
        assert second.get_cos_object() is second_form
        assert second_fixup.calls == 1


def test_wave527_page_layout_and_mode_string_values_use_defaults() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        cos = catalog.get_cos_object()

        cos.set_item(_name("PageLayout"), COSString("TwoColumnRight"))
        cos.set_item(_name("PageMode"), COSString("UseAttachments"))

        assert catalog.get_page_layout() is PageLayout.TWO_COLUMN_RIGHT
        assert catalog.get_page_mode() is PageMode.USE_ATTACHMENTS
        assert catalog.has_page_layout() is True
        assert catalog.has_page_mode() is True

        cos.set_item(_name("PageLayout"), COSString("BogusLayout"))
        cos.set_item(_name("PageMode"), COSString("BogusMode"))

        assert catalog.get_page_layout() is None
        assert catalog.get_page_mode() is None
        assert catalog.get_page_layout_or_default() is PageLayout.SINGLE_PAGE
        assert catalog.get_page_mode_or_default() is PageMode.USE_NONE
        assert catalog.has_page_layout() is False
        assert catalog.has_page_mode() is False


def test_wave527_associated_files_skip_bad_entries_and_accept_simple_specs() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        arr = COSArray()
        arr.add(COSArray())
        arr.add(COSString("readme.txt"))
        complex_spec = PDComplexFileSpecification()
        complex_spec.set_file("data.bin")
        arr.add(complex_spec.get_cos_object())
        catalog.get_cos_object().set_item(_name("AF"), arr)

        files = catalog.get_associated_files()

        assert catalog.has_associated_files() is True
        assert len(files) == 2
        assert isinstance(files[0], PDSimpleFileSpecification)
        assert files[0].get_file() == "readme.txt"
        assert files[1].get_file() == "data.bin"


def test_wave527_associated_files_malformed_array_reads_absent() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        arr = COSArray()
        arr.add(COSArray())
        catalog.get_cos_object().set_item(_name("AF"), arr)

        assert catalog.get_associated_files() == []
        assert catalog.has_associated_files() is False


def test_wave527_needs_rendering_presence_and_clear() -> None:
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()

        assert catalog.is_needs_rendering() is False
        assert catalog.has_needs_rendering() is False

        catalog.set_needs_rendering(True)
        assert catalog.is_needs_rendering() is True
        assert catalog.has_needs_rendering() is True

        catalog.set_needs_rendering(False)
        assert catalog.is_needs_rendering() is False
        assert catalog.has_needs_rendering() is True

        catalog.clear_needs_rendering()
        assert catalog.is_needs_rendering() is False
        assert catalog.has_needs_rendering() is False

