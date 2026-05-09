"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDDocumentInformation.java

Upstream baseline: PDFBox 3.0.
"""

from __future__ import annotations

import datetime as dt

from pypdfbox.pdmodel import PDDocument


def _build_pdf_with_info(info_body: bytes, extra_objects: list[tuple[int, bytes]]) -> bytes:
    objects = [
        (1, b"<< /Type /Catalog /Pages 2 0 R >>"),
        (2, b"<< /Type /Pages /Count 0 /Kids [] >>"),
        (3, info_body),
        *extra_objects,
    ]
    size = max(number for number, _ in objects) + 1
    data = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = [0] * size
    for number, body in objects:
        offsets[number] = len(data)
        data += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"

    xref_offset = len(data)
    data += f"xref\n0 {size}\n".encode("ascii")
    data += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        data += f"{offset:010d} 00000 n \n".encode("ascii")
    data += (
        b"trailer\n"
        + f"<< /Size {size} /Root 1 0 R /Info 3 0 R >>\n".encode("ascii")
        + b"startxref\n"
        + str(xref_offset).encode("ascii")
        + b"\n%%EOF\n"
    )
    return data


def test_metadata_extraction() -> None:
    pdf = _build_pdf_with_info(
        b"<< "
        b"/Author (Ben Litchfield) "
        b"/CreationDate (D:20060804162233+01'00') "
        b"/Creator (Acrobat PDFMaker 7.0.7 for Word) "
        b"/Producer (Acrobat Distiller 7.0.5) "
        b"/ModDate (D:20060804162233+01'00') "
        b"/Company (Apache Software Foundation) "
        b"/SourceModified (D:20060804152233) "
        b"/Title (Hello World) "
        b">>",
        [],
    )

    with PDDocument.load(pdf) as document:
        info = document.get_document_information()

        assert info.get_author() == "Ben Litchfield"
        assert info.get_creation_date() == dt.datetime(
            2006, 8, 4, 16, 22, 33, tzinfo=dt.timezone(dt.timedelta(hours=1))
        )
        assert info.get_creator() == "Acrobat PDFMaker 7.0.7 for Word"
        assert info.get_producer() == "Acrobat Distiller 7.0.5"
        assert info.get_modification_date() == dt.datetime(
            2006, 8, 4, 16, 22, 33, tzinfo=dt.timezone(dt.timedelta(hours=1))
        )
        assert info.get_custom_metadata_value("Company") == (
            "Apache Software Foundation"
        )
        assert info.get_custom_metadata_value("SourceModified") == (
            "D:20060804152233"
        )
        assert info.get_title() == "Hello World"
        assert info.get_keywords() is None
        assert info.get_subject() is None
        assert info.get_trapped() is None


def test_pdfbox_3068() -> None:
    pdf = _build_pdf_with_info(b"<< /Title 4 0 R >>", [(4, b"(Title)")])

    with PDDocument.load(pdf) as document:
        assert document.get_document_information().get_title() == "Title"
