"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/common/TestEmbeddedFiles.java

Upstream baseline: PDFBox 3.0.x. Fixtures ``null_PDComplexFileSpecification.pdf``
and ``testPDF_multiFormatEmbFiles.pdf`` bundled under
``tests/fixtures/pdmodel/common/``.
"""
from __future__ import annotations

from pathlib import Path

from pypdfbox import PDDocument
from pypdfbox.pdmodel.common.filespecification import PDEmbeddedFile

_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "pdmodel" / "common"


def _byte_array_contains_lc(target: str, data: bytes, encoding: str) -> bool:
    return target in data.decode(encoding).lower()


def test_null_embedded_file() -> None:
    embedded_file: PDEmbeddedFile | None = None
    ok = False
    with PDDocument.load(_FIXTURES / "null_PDComplexFileSpecification.pdf") as doc:
        catalog = doc.get_document_catalog()
        names = catalog.get_names()
        embedded_files = names.get_embedded_files()
        assert len(embedded_files.get_names()) == 2, "expected two files"

        spec = embedded_files.get_names().get("non-existent-file.docx")
        if spec is not None:
            embedded_file = spec.get_embedded_file()
            ok = True

        # now test for actual attachment
        spec = embedded_files.get_names().get("My first attachment")
        assert spec is not None, "one attachment actually exists"
        assert spec.get_embedded_file().get_length() == 17660, "existing file length"

        spec = embedded_files.get_names().get("non-existent-file.docx")
        assert spec is not None
        assert spec.get_file() is None
        assert spec.get_embedded_file() is None

    assert ok, "Was able to get file without exception"
    assert embedded_file is None, "EmbeddedFile was correctly null"


def test_os_specific_attachments() -> None:
    non_os_file = None
    mac_file = None
    dos_file = None
    unix_file = None

    with PDDocument.load(_FIXTURES / "testPDF_multiFormatEmbFiles.pdf") as doc:
        catalog = doc.get_document_catalog()
        names = catalog.get_names()
        tree_node = names.get_embedded_files()
        kids = tree_node.get_kids()
        for kid in kids:
            tmp_names = kid.get_names()
            spec = tmp_names.get("My first attachment")
            non_os_file = spec.get_embedded_file()
            mac_file = spec.get_embedded_file_mac()
            dos_file = spec.get_embedded_file_dos()
            unix_file = spec.get_embedded_file_unix()

        assert _byte_array_contains_lc(
            "non os specific", non_os_file.to_byte_array(), "ISO-8859-1"
        ), "non os specific"
        assert _byte_array_contains_lc(
            "mac embedded", mac_file.to_byte_array(), "ISO-8859-1"
        ), "mac"
        assert _byte_array_contains_lc(
            "dos embedded", dos_file.to_byte_array(), "ISO-8859-1"
        ), "dos"
        assert _byte_array_contains_lc(
            "unix embedded", unix_file.to_byte_array(), "ISO-8859-1"
        ), "unix"
