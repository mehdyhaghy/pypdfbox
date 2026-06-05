"""Hand-written parity pins for the AcroForm orphan-widget rebuild +
appearance-generation arm of ``AcroFormDefaultFixup`` (PDFBOX-4985).

These mirror the expectations the live oracle
(``tests/pdmodel/oracle/test_acro_form_orphan_fixup_oracle.py``) pins against
Apache PDFBox 3.0.7, but as static expected values so the arm stays covered on
machines without the Java oracle. Each fixture is byte-identical raw PDF: an
``/AcroForm`` with ``/NeedAppearances true`` and an empty ``/Fields`` array but
widget annotations on the page. The no-arg ``get_acro_form()`` must:

1. rebuild the field tree from the orphan widgets,
2. generate appearance streams for terminal variable-text fields,
3. clear ``/NeedAppearances``,
4. leave ``ZaDb`` injected into ``/DR`` by the defaults processor.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument

_AP = COSName.get_pdf_name("AP")


def _build(objs: list[tuple[int, bytes]]) -> bytes:
    out = bytearray(b"%PDF-1.6\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for num, body in objs:
        offsets[num] = len(out)
        out += f"{num} 0 obj\n".encode("utf-8") + body + b"\nendobj\n"
    xref_pos = len(out)
    size = max(offsets) + 1
    out += f"xref\n0 {size}\n".encode("utf-8")
    out += b"0000000000 65535 f \n"
    for i in range(1, size):
        out += f"{offsets.get(i, 0):010d} 00000 n \n".encode("utf-8")
    out += b"trailer\n<< /Size " + str(size).encode("utf-8")
    out += b" /Root 1 0 R >>\nstartxref\n"
    out += str(xref_pos).encode("utf-8") + b"\n%%EOF\n"
    return bytes(out)


_SINGLE = [
    (1, b"<< /Type /Catalog /Pages 2 0 R /AcroForm 6 0 R >>"),
    (2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
    (
        3,
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Annots [4 0 R] /Resources << >> >>",
    ),
    (
        4,
        b"<< /Type /Annot /Subtype /Widget /FT /Tx /T (field1) "
        b"/DA (/Helv 12 Tf 0 g) /Rect [10 10 110 30] /V (hello) /P 3 0 R >>",
    ),
    (
        6,
        b"<< /Fields [] /NeedAppearances true /DR << /Font << "
        b"/Helv 7 0 R >> >> /DA (/Helv 0 Tf 0 g) >>",
    ),
    (
        7,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
    ),
]

_HIERARCHICAL = [
    (1, b"<< /Type /Catalog /Pages 2 0 R /AcroForm 6 0 R >>"),
    (2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
    (
        3,
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Annots [4 0 R 5 0 R] /Resources << >> >>",
    ),
    (
        4,
        b"<< /Type /Annot /Subtype /Widget /T (child0) /Parent 9 0 R "
        b"/DA (/Helv 12 Tf 0 g) /Rect [10 10 110 30] /V (a) /P 3 0 R >>",
    ),
    (
        5,
        b"<< /Type /Annot /Subtype /Widget /T (child1) /Parent 9 0 R "
        b"/DA (/Helv 12 Tf 0 g) /Rect [10 40 110 60] /V (b) /P 3 0 R >>",
    ),
    (
        6,
        b"<< /Fields [] /NeedAppearances true /DR << /Font << "
        b"/Helv 7 0 R >> >> /DA (/Helv 0 Tf 0 g) >>",
    ),
    (
        7,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
    ),
    (9, b"<< /T (root) /FT /Tx >>"),
]

_NO_DA = [
    (1, b"<< /Type /Catalog /Pages 2 0 R /AcroForm 6 0 R >>"),
    (2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
    (
        3,
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Annots [4 0 R] /Resources << >> >>",
    ),
    (
        4,
        b"<< /Type /Annot /Subtype /Widget /FT /Tx /T (nodaf) "
        b"/Rect [10 10 110 30] /V (x) /P 3 0 R >>",
    ),
    (
        6,
        b"<< /Fields [] /NeedAppearances true /DR << /Font << "
        b"/Helv 7 0 R >> >> /DA (/Helv 0 Tf 0 g) >>",
    ),
    (
        7,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
    ),
]


def _load(objs: list[tuple[int, bytes]], tmp_path: Path) -> PDDocument:
    pdf = tmp_path / "orphan.pdf"
    pdf.write_bytes(_build(objs))
    return PDDocument.load(str(pdf))


def _dr_fonts(form: object) -> set[str]:
    dr = form.get_default_resources()
    return {n.get_name() for n in dr.get_font_names()} if dr is not None else set()


def _widget_ap_counts(doc: PDDocument) -> tuple[int, int]:
    total = 0
    with_ap = 0
    for page in doc.get_pages():
        for annot in page.get_annotations():
            if annot.get_subtype() == "Widget":
                total += 1
                if annot.get_cos_object().get_dictionary_object(_AP) is not None:
                    with_ap += 1
    return with_ap, total


def test_single_terminal_widget_rebuilds_field(tmp_path: Path) -> None:
    doc = _load(_SINGLE, tmp_path)
    try:
        form = doc.get_document_catalog().get_acro_form()
        assert form is not None
        fields = form.get_fields()
        assert len(fields) == 1
        assert fields[0].get_fully_qualified_name() == "field1"
        assert type(fields[0]).__name__ == "PDTextField"
        # appearance generated, NeedAppearances cleared
        assert form.get_need_appearances() is False
        assert _widget_ap_counts(doc) == (1, 1)
        # defaults processor injected ZaDb; original Helv preserved
        assert _dr_fonts(form) == {"Helv", "ZaDb"}
    finally:
        doc.close()


def test_hierarchical_parent_chain_collapses_to_root(tmp_path: Path) -> None:
    doc = _load(_HIERARCHICAL, tmp_path)
    try:
        form = doc.get_document_catalog().get_acro_form()
        assert form is not None
        # two widgets share one /Parent root -> dedup to a single root field
        fields = form.get_fields()
        assert len(fields) == 1
        tree = sorted(
            f"{f.get_fully_qualified_name()}:{type(f).__name__}"
            for f in form.get_field_tree()
        )
        assert tree == ["root:PDTextField"]
        assert form.get_need_appearances() is False
        assert _dr_fonts(form) == {"Helv", "ZaDb"}
    finally:
        doc.close()


def test_widget_missing_da_still_rebuilds(tmp_path: Path) -> None:
    doc = _load(_NO_DA, tmp_path)
    try:
        form = doc.get_document_catalog().get_acro_form()
        assert form is not None
        fields = form.get_fields()
        assert len(fields) == 1
        assert fields[0].get_fully_qualified_name() == "nodaf"
        assert type(fields[0]).__name__ == "PDTextField"
        assert form.get_need_appearances() is False
        assert _widget_ap_counts(doc) == (1, 1)
        assert _dr_fonts(form) == {"Helv", "ZaDb"}
    finally:
        doc.close()
