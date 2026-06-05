"""Live differential oracle: AcroForm orphan-widget rebuild + appearance
generation arm of ``AcroFormDefaultFixup`` (PDFBOX-4985).

The sibling :mod:`test_acro_form_default_fixup_oracle` only pins the *defaults*
arm (ZaDb /DR injection + /DA normalisation) on a document that already has a
field. This module pins the **rebuild path**: ``/NeedAppearances true`` with an
empty ``/Fields`` array but widget annotations present on a page. The no-arg
``getAcroForm()`` triggers ``AcroFormOrphanWidgetsProcessor`` (field-tree
rebuild from orphan widgets) followed by ``AcroFormGenerateAppearancesProcessor``
(appearance generation + ``/NeedAppearances`` cleared).

Both engines read **byte-identical** raw-PDF input (built here, not saved by
either engine) so the comparison isolates the fixup behaviour, not the writer.

Surfaces pinned (one fixture each):

- ``A`` — a single orphan widget that is itself a terminal text field
  (``/FT /Tx``, no ``/Parent``): plain rebuild + appearance generation.
- ``B`` — two orphan widgets sharing one ``/Parent`` non-terminal root field:
  the ``nonTerminalFieldsMap`` dedup must collapse them to a single root field.
- ``C`` — an orphan terminal widget with **no ``/DA``** (font-fallback path
  through ``ensureFontResources``).

The probe (``oracle/probes/AcroFormOrphanFixupProbe.java``) dumps the
post-fixup field tree (sorted ``FQN:SimpleClassName``), the ``/NeedAppearances``
flag, the sorted ``/DR`` font names, and per-page widget ``/AP`` presence.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from tests.oracle.harness import requires_oracle, run_probe_text

_AP = COSName.get_pdf_name("AP")


def _build(objs: list[tuple[int, bytes]]) -> bytes:
    """Serialise ``(obj_num, body)`` pairs into a minimal classic-xref PDF."""
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


def _fixture_a() -> bytes:
    """Single orphan widget that is itself a terminal text field."""
    return _build(
        [
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
                b"/DA (/Helv 12 Tf 0 g) /Rect [10 10 110 30] /V (hello) "
                b"/P 3 0 R >>",
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
    )


def _fixture_b() -> bytes:
    """Two orphan widgets sharing one non-terminal /Parent root field."""
    return _build(
        [
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
    )


def _fixture_c() -> bytes:
    """Single orphan terminal widget with no /DA (font-fallback path)."""
    return _build(
        [
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
    )


_FIXTURES = {"a": _fixture_a, "b": _fixture_b, "c": _fixture_c}


def _parse_probe(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "\t" in line:
            key, _, value = line.partition("\t")
            result[key] = value
    return result


def _py_dump(path: str) -> dict[str, str]:
    doc = PDDocument.load(path)
    try:
        form: PDAcroForm | None = doc.get_document_catalog().get_acro_form()
        if form is None:
            return {"FORMPRESENT": "false"}
        tree = sorted(
            f"{f.get_fully_qualified_name()}:{type(f).__name__}"
            for f in form.get_field_tree()
        )
        dr = form.get_default_resources()
        dr_fonts = (
            ",".join(sorted(n.get_name() for n in dr.get_font_names()))
            if dr is not None
            else ""
        )
        total = 0
        with_ap = 0
        for page in doc.get_pages():
            for annot in page.get_annotations():
                if annot.get_subtype() == "Widget":
                    total += 1
                    if annot.get_cos_object().get_dictionary_object(_AP) is not None:
                        with_ap += 1
        return {
            "FORMPRESENT": "true",
            "FIELDS": str(len(form.get_fields())),
            "TREE": ",".join(tree),
            "NEEDAPPEARANCES": str(form.get_need_appearances()).lower(),
            "DRFONTS": dr_fonts,
            "WIDGETAP": f"{with_ap}/{total}",
        }
    finally:
        doc.close()


_KEYS = ["FORMPRESENT", "FIELDS", "TREE", "NEEDAPPEARANCES", "DRFONTS", "WIDGETAP"]


@requires_oracle
def _check(selector: str, tmp_path: Path) -> None:
    pdf = tmp_path / f"orphan_{selector}.pdf"
    pdf.write_bytes(_FIXTURES[selector]())
    java = _parse_probe(run_probe_text("AcroFormOrphanFixupProbe", str(pdf)))
    py = _py_dump(str(pdf))
    for key in _KEYS:
        assert py.get(key) == java.get(key), (
            f"[{selector}] {key}: py={py.get(key)!r} java={java.get(key)!r}"
        )


@requires_oracle
def test_orphan_single_terminal_widget_matches_pdfbox(tmp_path: Path) -> None:
    _check("a", tmp_path)


@requires_oracle
def test_orphan_hierarchical_parent_chain_matches_pdfbox(tmp_path: Path) -> None:
    _check("b", tmp_path)


@requires_oracle
def test_orphan_widget_missing_da_matches_pdfbox(tmp_path: Path) -> None:
    _check("c", tmp_path)
