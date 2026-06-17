"""Live Apache PDFBox parity for the FDF/XFDF import-export CLI tools, the
``DecompressObjectstreams`` CLI, and the non-printing error surfaces of the
``PrintPDF`` CLI.

Tools covered (each ``org.apache.pdfbox.tools.<X>`` vs ``pypdfbox.tools.<x>``):

* **ImportFDF / ImportXFDF** — fill an AcroForm PDF's fields with values from an
  FDF / XFDF data file, writing the imported PDF to ``-o`` (or overwriting the
  input in place when ``-o`` is omitted).
* **ExportFDF / ExportXFDF** — dump an AcroForm PDF's filled field values back
  out to an FDF / XFDF data file.
* **DecompressObjectstreams** — re-save a PDF with object streams stripped
  (``/ObjStm`` objects flattened to top-level indirect objects), useful for
  hand-debugging a file in a text editor.
* **PrintPDF** — only the *non-printing* surfaces are exercised: parameter
  validation (missing required ``-i``, an unknown ``-orientation`` / ``-duplex``
  enum token → exit 2) and the early ``call()`` failure that returns 4 before a
  printer is ever touched (a missing / unloadable input file). The success path
  is never driven on either side — it would reach a real print spooler.

The differential rig builds every fixture through pypdfbox (an AcroForm PDF, a
matching FDF + XFDF, and a Java-compressed object-stream PDF) so both libraries
operate on byte-identical inputs, then drives the **real upstream picocli CLI**
through ``FdfCliToolProbe`` / ``PrintPdfFlagProbe`` (each emitting the CLI's
exit code as JSON) and compares:

* exit codes on success, on missing input, and on bad flags;
* the post-import ``/V`` value + COS type of every AcroForm field (Java-imported
  PDF reloaded with pypdfbox vs pypdfbox-imported PDF) — element order, value,
  and the text/choice→string vs checkbox→name coercion all matter;
* the exported FDF/XFDF field tree reloaded from each side;
* the absence of ``/ObjStm`` in the decompressed output plus a preserved page
  count.

Divergences fixed in this wave (wave 1497):

* ``ImportFDF`` / ``ImportXFDF`` ``call()`` loaded the PDF via
  ``Loader.load_pdf`` (which returns a bare ``COSDocument``) and then called
  ``get_document_catalog()`` on it — an ``AttributeError`` crash that escaped
  the ``except OSError`` handler. Now wrapped via ``PDDocument.load`` (the path
  the sibling ``ExportFDF`` tool already used), matching upstream's
  ``Loader.loadPDF`` returning a ``PDDocument``.
* ``PrintPDF.main`` accepted any ``-orientation`` string and raised an uncaught
  ``KeyError`` on a bad ``-duplex`` token (``Duplex[ns.duplex]``). Both options
  are now constrained to the upstream enum values, so a bad token exits 2 —
  matching picocli's "Invalid value for option" exit code.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pypdfbox import Loader
from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.fdf import FDFDocument
from pypdfbox.pdmodel.fdf.fdf_field import FDFField
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.tools.decompress_objectstreams import DecompressObjectstreams
from pypdfbox.tools.export_fdf import ExportFDF
from pypdfbox.tools.export_xfdf import ExportXFDF
from pypdfbox.tools.import_fdf import ImportFDF
from pypdfbox.tools.import_xfdf import ImportXFDF
from pypdfbox.tools.print_pdf import PrintPDF
from tests.oracle.harness import (
    _classpath,
    requires_oracle,
    run_probe_text,
)

# --------------------------------------------------------------- fixture build


def _add_widget_rect(
    field_dict: COSDictionary,
    page: PDPage,
    rect: tuple[float, float, float, float],
) -> None:
    field_dict.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget"))
    field_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Annot"))
    arr = COSArray()
    for v in rect:
        arr.add(COSFloat(float(v)))
    field_dict.set_item(COSName.get_pdf_name("Rect"), arr)
    field_dict.set_item(COSName.get_pdf_name("P"), page.get_cos_object())
    annots = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Annots"))
    if not isinstance(annots, COSArray):
        annots = COSArray()
        page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)
    annots.add(field_dict)


def _form_xobject() -> COSStream:
    s = COSStream()
    s.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    s.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Form"))
    bbox = COSArray()
    for v in (0.0, 0.0, 20.0, 20.0):
        bbox.add(COSFloat(v))
    s.set_item(COSName.get_pdf_name("BBox"), bbox)
    s.set_raw_data(b"q Q\n")
    return s


def _build_form_pdf(path_pdf: Path) -> None:
    """An AcroForm PDF: text ``name``, combo ``color`` (choice), checkbox
    ``agree`` with real Yes/Off appearances, and a hierarchical ``address`` →
    ``city`` text child. Mirrors the import FDF's field names."""
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        doc.add_page(page)
        form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(form)

        name = PDTextField(form)
        name.set_partial_name("name")
        _add_widget_rect(name.get_cos_object(), page, (10.0, 700.0, 210.0, 720.0))

        color = PDComboBox(form)
        color.set_partial_name("color")
        color.set_options(["Red", "Green", "Blue"])
        _add_widget_rect(color.get_cos_object(), page, (10.0, 650.0, 210.0, 670.0))

        agree = PDCheckBox(form)
        agree.set_partial_name("agree")
        _add_widget_rect(agree.get_cos_object(), page, (10.0, 600.0, 30.0, 620.0))
        ap_n = COSDictionary()
        ap_n.set_item(COSName.get_pdf_name("Yes"), _form_xobject())
        ap_n.set_item(COSName.get_pdf_name("Off"), _form_xobject())
        ap = COSDictionary()
        ap.set_item(COSName.get_pdf_name("N"), ap_n)
        agree.get_cos_object().set_item(COSName.get_pdf_name("AP"), ap)
        agree.get_cos_object().set_name(COSName.get_pdf_name("AS"), "Off")

        address = PDNonTerminalField(form)
        address.set_partial_name("address")
        city = PDTextField(form, None, address)
        city.set_partial_name("city")
        _add_widget_rect(city.get_cos_object(), page, (10.0, 550.0, 210.0, 570.0))
        address.set_children([city])

        form.set_fields([name, color, agree, address])
        doc.save(str(path_pdf))
    finally:
        doc.close()


def _build_data_files(path_fdf: Path, path_xfdf: Path) -> None:
    """The FDF / XFDF whose values are imported: text, choice, checkbox name,
    and a hierarchical ``address`` → ``city`` value."""
    doc = FDFDocument()
    try:
        fdf = doc.get_catalog().get_fdf()

        f_name = FDFField()
        f_name.set_partial_field_name("name")
        f_name.set_value("Alice")

        f_color = FDFField()
        f_color.set_partial_field_name("color")
        f_color.set_value("Green")

        f_agree = FDFField()
        f_agree.set_partial_field_name("agree")
        f_agree.get_cos_object().set_item(
            COSName.get_pdf_name("V"), COSName.get_pdf_name("Yes")
        )

        f_addr = FDFField()
        f_addr.set_partial_field_name("address")
        f_city = FDFField()
        f_city.set_partial_field_name("city")
        f_city.set_value("Paris")
        f_addr.set_kids([f_city])

        fdf.set_fields([f_name, f_color, f_agree, f_addr])
        doc.save(str(path_fdf))
        doc.save_xfdf(str(path_xfdf))
    finally:
        doc.close()


def _make_objstm_pdf(path_out: Path, tmp_path: Path) -> None:
    """Build a PDF carrying compressed object streams (``/ObjStm``).

    pypdfbox (like upstream PDFBox) does not *write* compressed object
    streams, so the fixture is produced by re-saving a pypdfbox-built PDF
    through Java PDFBox, whose default save uses object streams in 3.0.x.
    """
    import os  # noqa: PLC0415 — local, test-only
    import subprocess  # noqa: PLC0415 — local, test-only

    plain = tmp_path / "_objstm_plain.pdf"
    doc = PDDocument()
    try:
        for _ in range(8):
            doc.add_page(PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0)))
        doc.save(str(plain))
    finally:
        doc.close()

    src = (
        "import java.io.File;"
        "import org.apache.pdfbox.Loader;"
        "import org.apache.pdfbox.pdmodel.PDDocument;"
        "public class _MakeObjStm {"
        " public static void main(String[] a) throws Exception {"
        "  try (PDDocument doc = Loader.loadPDF(new File(a[0]))) {"
        "   doc.save(new File(a[1]));"
        "  }"
        " }"
        "}"
    )
    java_src = tmp_path / "_MakeObjStm.java"
    java_src.write_text(src, encoding="utf-8")
    subprocess.run(
        ["javac", "-cp", _classpath(), "-d", str(tmp_path), str(java_src)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "java",
            "-cp",
            _classpath() + os.pathsep + str(tmp_path),
            "_MakeObjStm",
            str(plain),
            str(path_out),
        ],
        check=True,
        capture_output=True,
    )


# ------------------------------------------------------------ reload helpers


def _import_dump(pdf_path: Path) -> list[str]:
    """Depth-first ``<fqn> | <type> | <repr>`` of every AcroForm field's /V."""
    doc = PDDocument.load(str(pdf_path))
    try:
        form = doc.get_document_catalog().get_acro_form()
        lines: list[str] = []

        def cos_repr(v: object | None) -> str:
            if v is None:
                return "-"
            if isinstance(v, COSName):
                return v.name
            if isinstance(v, COSString):
                return v.get_string()
            return str(v)

        def walk(field: object) -> None:
            cos = field.get_cos_object()  # type: ignore[attr-defined]
            v = cos.get_dictionary_object(COSName.get_pdf_name("V"))
            type_name = "-" if v is None else type(v).__name__
            fqn = field.get_fully_qualified_name()  # type: ignore[attr-defined]
            lines.append(f"{fqn} | {type_name} | {cos_repr(v)}")
            if isinstance(field, PDNonTerminalField):
                for child in field.get_children():
                    walk(child)

        for top in form.get_fields():
            walk(top)
        return lines
    finally:
        doc.close()


def _fdf_dump(data_path: Path, *, xfdf: bool) -> list[str]:
    """Depth-first ``<fqn> | <value-repr>`` of an FDF / XFDF field tree."""
    doc = Loader.load_xfdf(str(data_path)) if xfdf else Loader.load_fdf(str(data_path))
    try:
        fdf = doc.get_catalog().get_fdf()
        lines: list[str] = []

        def emit(field: FDFField, prefix: str) -> None:
            partial = field.get_partial_field_name() or ""
            fq = f"{prefix}.{partial}" if prefix and partial else (prefix or partial)
            lines.append(f"{fq} | {field.get_value()}")
            for kid in field.get_kids() or []:
                emit(kid, fq)

        for top in fdf.get_fields() or []:
            emit(top, "")
        return lines
    finally:
        doc.close()


def _has_objstm(path: Path) -> bool:
    return b"/ObjStm" in path.read_bytes()


def _page_count(path: Path) -> int:
    doc = PDDocument.load(str(path))
    try:
        return doc.get_number_of_pages()
    finally:
        doc.close()


# --------------------------------------------------------------- import tests


@requires_oracle
def test_import_fdf_matches_pdfbox(tmp_path: Path) -> None:
    """Both CLIs fill the AcroForm from the FDF and exit 0; the post-import
    field /V values + COS types reloaded from each output PDF match line for
    line (text/choice → COSString, checkbox name → COSName, hierarchical
    ``address.city`` transferred through the kids walk)."""
    form_pdf = tmp_path / "form.pdf"
    fdf = tmp_path / "data.fdf"
    xfdf = tmp_path / "data.xfdf"
    _build_form_pdf(form_pdf)
    _build_data_files(fdf, xfdf)

    j_out = tmp_path / "j_import.pdf"
    java = json.loads(
        run_probe_text(
            "FdfCliToolProbe",
            "importfdf",
            "-i",
            str(form_pdf),
            "--data",
            str(fdf),
            "-o",
            str(j_out),
        )
    )
    assert java["exitCode"] == 0

    p_out = tmp_path / "p_import.pdf"
    rc = ImportFDF.main(["-i", str(form_pdf), "--data", str(fdf), "-o", str(p_out)])
    assert rc == 0

    assert _import_dump(p_out) == _import_dump(j_out)


@requires_oracle
def test_import_xfdf_matches_pdfbox(tmp_path: Path) -> None:
    """ImportXFDF parity: both CLIs fill the form from the XFDF data file and
    the reloaded field /V values + types match."""
    form_pdf = tmp_path / "form.pdf"
    fdf = tmp_path / "data.fdf"
    xfdf = tmp_path / "data.xfdf"
    _build_form_pdf(form_pdf)
    _build_data_files(fdf, xfdf)

    j_out = tmp_path / "j_import_x.pdf"
    java = json.loads(
        run_probe_text(
            "FdfCliToolProbe",
            "importxfdf",
            "-i",
            str(form_pdf),
            "--data",
            str(xfdf),
            "-o",
            str(j_out),
        )
    )
    assert java["exitCode"] == 0

    p_out = tmp_path / "p_import_x.pdf"
    rc = ImportXFDF.main(["-i", str(form_pdf), "--data", str(xfdf), "-o", str(p_out)])
    assert rc == 0

    assert _import_dump(p_out) == _import_dump(j_out)


@requires_oracle
def test_import_fdf_in_place_matches_pdfbox(tmp_path: Path) -> None:
    """No ``-o`` → both CLIs overwrite the input PDF in place; the in-place
    field values match."""
    form_pdf = tmp_path / "form.pdf"
    fdf = tmp_path / "data.fdf"
    xfdf = tmp_path / "data.xfdf"
    _build_form_pdf(form_pdf)
    _build_data_files(fdf, xfdf)

    j_in = tmp_path / "j_inplace.pdf"
    p_in = tmp_path / "p_inplace.pdf"
    shutil.copy(form_pdf, j_in)
    shutil.copy(form_pdf, p_in)

    java = json.loads(
        run_probe_text(
            "FdfCliToolProbe", "importfdf", "-i", str(j_in), "--data", str(fdf)
        )
    )
    assert java["exitCode"] == 0

    rc = ImportFDF.main(["-i", str(p_in), "--data", str(fdf)])
    assert rc == 0

    assert _import_dump(p_in) == _import_dump(j_in)


# --------------------------------------------------------------- export tests


@requires_oracle
def test_export_fdf_matches_pdfbox(tmp_path: Path) -> None:
    """Import then export: both CLIs dump the filled form to an FDF whose
    reloaded field tree matches. Exit 0 on both sides."""
    form_pdf = tmp_path / "form.pdf"
    fdf = tmp_path / "data.fdf"
    xfdf = tmp_path / "data.xfdf"
    _build_form_pdf(form_pdf)
    _build_data_files(fdf, xfdf)

    # First produce a filled PDF via the python import tool (byte-identical
    # input for both export CLIs).
    filled = tmp_path / "filled.pdf"
    assert ImportFDF.main(["-i", str(form_pdf), "--data", str(fdf), "-o", str(filled)]) == 0

    j_fdf = tmp_path / "j_export.fdf"
    java = json.loads(
        run_probe_text(
            "FdfCliToolProbe", "exportfdf", "-i", str(filled), "-o", str(j_fdf)
        )
    )
    assert java["exitCode"] == 0

    p_fdf = tmp_path / "p_export.fdf"
    assert ExportFDF.main(["-i", str(filled), "-o", str(p_fdf)]) == 0

    # Both must start with the %FDF- header PDFBox's FDFParser requires.
    assert j_fdf.read_bytes().startswith(b"%FDF-")
    assert p_fdf.read_bytes().startswith(b"%FDF-")
    assert _fdf_dump(p_fdf, xfdf=False) == _fdf_dump(j_fdf, xfdf=False)


@requires_oracle
def test_export_xfdf_matches_pdfbox(tmp_path: Path) -> None:
    """ExportXFDF parity: both CLIs dump the filled form to an XFDF whose
    reloaded field tree matches (the ``/ids`` element carries a content-derived
    hash and is intentionally not compared)."""
    form_pdf = tmp_path / "form.pdf"
    fdf = tmp_path / "data.fdf"
    xfdf = tmp_path / "data.xfdf"
    _build_form_pdf(form_pdf)
    _build_data_files(fdf, xfdf)

    filled = tmp_path / "filled.pdf"
    assert ImportFDF.main(["-i", str(form_pdf), "--data", str(fdf), "-o", str(filled)]) == 0

    j_xfdf = tmp_path / "j_export.xfdf"
    java = json.loads(
        run_probe_text(
            "FdfCliToolProbe", "exportxfdf", "-i", str(filled), "-o", str(j_xfdf)
        )
    )
    assert java["exitCode"] == 0

    p_xfdf = tmp_path / "p_export.xfdf"
    assert ExportXFDF.main(["-i", str(filled), "-o", str(p_xfdf)]) == 0

    assert j_xfdf.read_bytes().startswith(b"<?xml")
    assert p_xfdf.read_bytes().startswith(b"<?xml")
    assert _fdf_dump(p_xfdf, xfdf=True) == _fdf_dump(j_xfdf, xfdf=True)


@requires_oracle
def test_export_fdf_no_form_matches_pdfbox(tmp_path: Path) -> None:
    """A PDF with no AcroForm → ExportFDF exits 1 on both sides; ExportXFDF
    exits 0 on both sides (upstream's documented asymmetry: ExportFDF returns
    1, ExportXFDF returns 0 for the same "no form" message)."""
    noform = tmp_path / "noform.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0)))
        doc.save(str(noform))
    finally:
        doc.close()

    j_fdf = json.loads(
        run_probe_text(
            "FdfCliToolProbe", "exportfdf", "-i", str(noform), "-o", str(tmp_path / "x.fdf")
        )
    )
    assert j_fdf["exitCode"] == 1
    assert ExportFDF.main(["-i", str(noform), "-o", str(tmp_path / "p.fdf")]) == 1

    j_xfdf = json.loads(
        run_probe_text(
            "FdfCliToolProbe", "exportxfdf", "-i", str(noform), "-o", str(tmp_path / "x.xfdf")
        )
    )
    assert j_xfdf["exitCode"] == 0
    assert ExportXFDF.main(["-i", str(noform), "-o", str(tmp_path / "p.xfdf")]) == 0


# ----------------------------------------------------- decompress objectstreams


@requires_oracle
def test_decompress_objectstreams_matches_pdfbox(tmp_path: Path) -> None:
    """Both CLIs strip the ``/ObjStm`` object streams from a Java-compressed
    PDF and exit 0; neither output carries ``/ObjStm`` and both preserve the
    page count."""
    objstm = tmp_path / "objstm.pdf"
    _make_objstm_pdf(objstm, tmp_path)
    assert _has_objstm(objstm), "fixture must carry /ObjStm to be a real test"

    j_out = tmp_path / "j_dec.pdf"
    java = json.loads(
        run_probe_text(
            "FdfCliToolProbe", "decompress", "-i", str(objstm), "-o", str(j_out)
        )
    )
    assert java["exitCode"] == 0

    p_out = tmp_path / "p_dec.pdf"
    assert DecompressObjectstreams.main(["-i", str(objstm), "-o", str(p_out)]) == 0

    assert not _has_objstm(j_out)
    assert not _has_objstm(p_out)
    assert _page_count(p_out) == _page_count(j_out) == 8


@requires_oracle
def test_decompress_objectstreams_in_place_matches_pdfbox(tmp_path: Path) -> None:
    """No ``-o`` → both CLIs overwrite the input file with the decompressed
    document; the ``/ObjStm`` is gone in place on both sides."""
    objstm = tmp_path / "objstm.pdf"
    _make_objstm_pdf(objstm, tmp_path)

    j_in = tmp_path / "j_inplace.pdf"
    p_in = tmp_path / "p_inplace.pdf"
    shutil.copy(objstm, j_in)
    shutil.copy(objstm, p_in)

    java = json.loads(
        run_probe_text("FdfCliToolProbe", "decompress", "-i", str(j_in))
    )
    assert java["exitCode"] == 0
    assert DecompressObjectstreams.main(["-i", str(p_in)]) == 0

    assert not _has_objstm(j_in)
    assert not _has_objstm(p_in)


# ------------------------------------------------------ shared error surfaces


@pytest.mark.parametrize(
    "tool",
    ["importfdf", "importxfdf", "exportfdf", "exportxfdf", "decompress"],
)
@requires_oracle
def test_missing_input_file_exit4_matches_pdfbox(tmp_path: Path, tool: str) -> None:
    """A missing input PDF → every FDF/XFDF/decompress CLI exits 4 on both
    sides (the picocli ``call()`` catches the IOException-equivalent and
    returns 4)."""
    missing = tmp_path / "nope.pdf"
    data = tmp_path / "data.fdf"
    xdata = tmp_path / "data.xfdf"
    _build_data_files(data, xdata)

    extra: list[str]
    if tool == "importfdf":
        extra = ["--data", str(data)]
    elif tool == "importxfdf":
        extra = ["--data", str(xdata)]
    elif tool in ("exportfdf", "exportxfdf"):
        extra = ["-o", str(tmp_path / "out.dat")]
    else:
        extra = []

    java = json.loads(
        run_probe_text("FdfCliToolProbe", tool, "-i", str(missing), *extra)
    )
    assert java["exitCode"] == 4

    runners = {
        "importfdf": ImportFDF,
        "importxfdf": ImportXFDF,
        "exportfdf": ExportFDF,
        "exportxfdf": ExportXFDF,
        "decompress": DecompressObjectstreams,
    }
    rc = runners[tool].main(["-i", str(missing), *extra])
    assert rc == 4


# ------------------------------------------------------- PrintPDF flag surface


@requires_oracle
def test_print_pdf_missing_input_file_exit4(tmp_path: Path) -> None:
    """PrintPDF with a missing input PDF returns 4 on both sides — the load
    fails before any ``PrinterJob`` is constructed, so no printer is touched."""
    missing = tmp_path / "nope.pdf"
    java = json.loads(run_probe_text("PrintPdfFlagProbe", "-i", str(missing)))
    assert java["exitCode"] == 4
    assert PrintPDF.main(["-i", str(missing)]) == 4


@requires_oracle
def test_print_pdf_missing_required_input_exit2(tmp_path: Path) -> None:
    """No ``-i`` → picocli exits 2; pypdfbox's argparse raises SystemExit(2)."""
    java = json.loads(run_probe_text("PrintPdfFlagProbe"))
    assert java["exitCode"] == 2
    with pytest.raises(SystemExit) as exc:
        PrintPDF.main([])
    assert exc.value.code == 2


@pytest.mark.parametrize(
    ("flag", "bad_value"),
    [("-orientation", "SIDEWAYS"), ("-duplex", "FLIP")],
)
@requires_oracle
def test_print_pdf_bad_enum_flag_exit2(
    tmp_path: Path, flag: str, bad_value: str
) -> None:
    """An unknown ``-orientation`` / ``-duplex`` enum token exits 2 on both
    sides. (Before wave 1497 pypdfbox accepted any orientation and raised an
    uncaught ``KeyError`` on a bad ``-duplex``.)"""
    missing = tmp_path / "nope.pdf"
    java = json.loads(
        run_probe_text("PrintPdfFlagProbe", "-i", str(missing), flag, bad_value)
    )
    assert java["exitCode"] == 2
    with pytest.raises(SystemExit) as exc:
        PrintPDF.main(["-i", str(missing), flag, bad_value])
    assert exc.value.code == 2


# ------------------------------------------------- oracle-independent pins


def test_import_fdf_value_coercion_pinned(tmp_path: Path) -> None:
    """Pin the exact post-import facts without the oracle so a regression in
    value transfer / coercion is caught even on a machine without Java."""
    form_pdf = tmp_path / "form.pdf"
    fdf = tmp_path / "data.fdf"
    xfdf = tmp_path / "data.xfdf"
    _build_form_pdf(form_pdf)
    _build_data_files(fdf, xfdf)

    out = tmp_path / "out.pdf"
    assert ImportFDF.main(["-i", str(form_pdf), "--data", str(fdf), "-o", str(out)]) == 0
    assert _import_dump(out) == [
        "name | COSString | Alice",
        "color | COSString | Green",
        "agree | COSName | Yes",
        "address | - | -",
        "address.city | COSString | Paris",
    ]


def test_print_pdf_bad_duplex_no_longer_crashes(tmp_path: Path) -> None:
    """Oracle-independent regression pin: a bad ``-duplex`` token now exits 2
    via argparse rather than raising an uncaught ``KeyError``."""
    with pytest.raises(SystemExit) as exc:
        PrintPDF.main(["-i", str(tmp_path / "x.pdf"), "-duplex", "FLIP"])
    assert exc.value.code == 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q", "--no-cov"]))
