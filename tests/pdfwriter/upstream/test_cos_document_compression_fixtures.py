"""Tests ported from PDFBox 3.0 ``COSDocumentCompressionTest`` (fixture slice).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdfwriter/COSDocumentCompressionTest.java``
on the apache/pdfbox 3.0 branch.

The skip-tagged surrogates in :mod:`test_cos_document_compression`
were placed before the in-tree fixtures
(``acroform.pdf``, ``attachment.pdf``, ``unencrypted.pdf``) were
bundled. This file ports the fixture-driven scenarios against those
bundled fixtures so we exercise the real compression round-trip
contracts.

The ``testCompressEncryptedDoc`` scenario stays skipped — it depends
on the encrypt-on-save path (StandardProtectionPolicy round-trip)
which is still a work-in-progress slice in pypdfbox.
``testPDFBox5927`` stays skipped — its fixture lives under
``target/pdfs/`` (Maven-downloaded), not in the source tree.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "pdfwriter"


def test_compress_acroform_doc(tmp_path: Path) -> None:
    """Port of ``COSDocumentCompressionTest#testCompressAcroformDoc``.

    Loads the AcroForm fixture, saves it (which exercises compression /
    object-stream layout), reloads, and walks the 13-annotation grid
    upstream pins each row of.
    """
    source = _FIXTURE_DIR / "acroform.pdf"
    target = tmp_path / "acroform.pdf"

    with PDDocument.load(str(source)) as document:
        document.save(str(target))

    name_key = COSName.get_pdf_name("T")

    with PDDocument.load(str(target)) as document:
        assert document.get_number_of_pages() == 1, (
            "The number of pages should not have changed during compression."
        )
        page = document.get_page(0)
        annotations = page.get_annotations()
        assert len(annotations) == 13, (
            "The number of annotations should not have changed"
        )
        assert (
            annotations[0].get_cos_object().get_name_as_string(name_key) == "TextField"
        ), "The 1. annotation should have been a text field."
        assert annotations[1].get_cos_object().get_name_as_string(name_key) == "Button"
        assert (
            annotations[2].get_cos_object().get_name_as_string(name_key) == "CheckBox1"
        )
        assert (
            annotations[3].get_cos_object().get_name_as_string(name_key) == "CheckBox2"
        )
        assert (
            annotations[4].get_cos_object().get_name_as_string(name_key)
            == "TextFieldMultiLine"
        )
        assert (
            annotations[5].get_cos_object().get_name_as_string(name_key)
            == "TextFieldMultiLineRT"
        )

        parent_key = COSName.get_pdf_name("Parent")
        assert annotations[6].get_cos_object().get_item(parent_key) is not None, (
            "The 7. annotation should have had a parent entry."
        )
        assert (
            annotations[6]
            .get_cos_object()
            .get_cos_dictionary(parent_key)
            .get_name_as_string(name_key)
            == "GroupOption"
        )
        assert annotations[7].get_cos_object().get_item(parent_key) is not None
        assert (
            annotations[7]
            .get_cos_object()
            .get_cos_dictionary(parent_key)
            .get_name_as_string(name_key)
            == "GroupOption"
        )
        assert annotations[8].get_cos_object().get_name_as_string(name_key) == "ListBox"
        assert (
            annotations[9].get_cos_object().get_name_as_string(name_key)
            == "ListBoxMultiSelect"
        )
        assert (
            annotations[10].get_cos_object().get_name_as_string(name_key) == "ComboBox"
        )
        assert (
            annotations[11].get_cos_object().get_name_as_string(name_key)
            == "ComboBoxEditable"
        )
        assert (
            annotations[12].get_cos_object().get_name_as_string(name_key) == "Signature"
        )


def test_compress_attachments_doc(tmp_path: Path) -> None:
    """Port of ``COSDocumentCompressionTest#testCompressAttachmentsDoc``.

    Round-trips the embedded-files fixture and asserts the embedded
    ``A4Unicode.pdf`` attachment survives compression byte-exact.
    """
    source = _FIXTURE_DIR / "attachment.pdf"
    target = tmp_path / "attachment.pdf"

    with PDDocument.load(str(source)) as document:
        document.save(str(target))

    with PDDocument.load(str(target)) as document:
        assert document.get_number_of_pages() == 2
        embedded_files = (
            document.get_document_catalog().get_names().get_embedded_files().get_names()
        )
        assert len(embedded_files) == 1
        attachment = embedded_files.get("A4Unicode.pdf")
        assert attachment is not None, (
            "The document should have contained 'A4Unicode.pdf'."
        )
        embedded = attachment.get_embedded_file()
        assert embedded is not None
        assert embedded.get_length() == 14997, (
            "The attachment's length is not as expected."
        )


def test_compress_encrypted_doc(tmp_path: Path) -> None:
    """Port of ``COSDocumentCompressionTest#testCompressEncryptedDoc``.

    Loads the password-protected source under user password ``"user"``,
    re-protects it with a fresh :class:`StandardProtectionPolicy`, saves
    (which goes through the compression + encryption write path), then
    reloads under the same password and confirms the page count.
    """
    from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
    from pypdfbox.pdmodel.encryption.standard_protection_policy import (
        StandardProtectionPolicy,
    )

    source = _FIXTURE_DIR / "unencrypted.pdf"
    target = tmp_path / "encrypted.pdf"

    with PDDocument.load(str(source), "user") as document:
        document.protect(StandardProtectionPolicy("owner", "user", AccessPermission(0)))
        document.save(str(target))

    with PDDocument.load(str(target), "user") as document:
        # If the encryption dictionary writing failed the load would
        # raise; getting two pages back is the upstream invariant.
        assert document.get_number_of_pages() == 2


def test_altered_doc(tmp_path: Path) -> None:
    """Port of ``COSDocumentCompressionTest#testAlteredDoc``.

    Loads ``unencrypted.pdf`` (a 2-page source), adds a page with a
    short content stream, saves compressed, reloads, and confirms the
    page is present. Upstream asserts the new page's content stream is
    exactly 43 bytes; that figure depends on the Java
    ``PDPageContentStream`` whitespace/operator layout (the structural
    surrogate in :mod:`test_cos_document_compression` documents the
    departure), so here we only assert the page count and the presence
    of a non-empty content stream — the byte-length assertion is left
    to the structural surrogate.
    """
    from pypdfbox.cos import COSName
    from pypdfbox.pdmodel import PDPage
    from pypdfbox.pdmodel.common import PDRectangle
    from pypdfbox.pdmodel.font import PDType1Font
    from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream

    source = _FIXTURE_DIR / "unencrypted.pdf"
    target = tmp_path / "altered.pdf"

    with PDDocument.load(str(source)) as document:
        page = PDPage(PDRectangle(100, 100))
        document.add_page(page)

        font = PDType1Font()
        font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")

        with PDPageContentStream(document, page) as cs:
            cs.begin_text()
            cs.new_line_at_offset(20, 80)
            cs.set_font(font, 12)
            cs.show_text("Test")
            cs.end_text()

        document.save(str(target))

    with PDDocument.load(str(target)) as document:
        assert document.get_number_of_pages() == 3
        page = document.get_page(2)
        streams = page.get_content_streams()
        assert len(streams) >= 1
        assert streams[0].get_length() > 0
