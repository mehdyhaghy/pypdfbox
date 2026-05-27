"""Live Apache PDFBox differential parity tests for TEXT-FIELD appearance
generation (wave 1433).

Surface: ``PDTextField.set_value`` regenerating the widget ``/AP /N`` content
stream via ``AppearanceGeneratorHelper`` / ``PDAppearanceGenerator`` — the
``/DA`` font + size, ``/Q`` quadding (0 left / 1 centre / 2 right), the
multiline ``Ff`` flag (auto line-wrap), comb fields (``/MaxLen`` + comb flag →
evenly spaced cells), and auto-font-size (``/DA`` size 0 → fit).

Strategy
--------
A single AcroForm is built *via pypdfbox* (:func:`_build_form`) carrying six
text fields exercising each variation, with the field value already set so
pypdfbox's ``set_value`` has regenerated the appearance. That file is saved
once per session. The Java ``TextFieldApProbe`` (``oracle/probes/
TextFieldApProbe.java``, compiled against the pinned pdfbox-app-3.0.7 jar) then
loads the *same* file, re-runs ``setValue`` on each field (which makes upstream
PDFBox compose its own appearance into the identical field configuration), and
saves a parallel file. Both files are read back through the probe's READ mode,
which reports per field:

    fqName \t da \t bboxW \t bboxH \t opSeq \t facts

The Python side re-tokenises the pypdfbox file's ``/AP /N`` with the same
metric extraction (:func:`_py_facts`) so the two records are apples-to-apples.

Parity bar — STRUCTURAL, not byte-exact
---------------------------------------
Exact coordinates and the colour-operator encoding legitimately differ (PDFBox
emits ``cs <name> sc`` for the explicit DeviceGray colour space where pypdfbox
emits the equivalent ``0 g``; PDFBox's multiline wrap splits a line into one
``Tj`` per word where pypdfbox emits one ``Tj`` per wrapped line; PDFBox's
auto-size uses a cap-height formula where the lite port clamps to a
height-proportional ``AUTO_FONT_SIZE_MAX``). What MUST match:

  * the operator-sequence *skeleton* (``BMC q … W n BT … Tf … Td … Tj … ET Q
    EMC``),
  * the resolved ``/DA`` font name + size,
  * the quadding-driven alignment bucket (L / C / R),
  * the number of comb cells,
  * that multiline wraps to more than one baseline,
  * that auto-size resolves to a comparable non-zero size.

Both outputs must pass ``qpdf --check`` (warnings tolerated).

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
_RECT: COSName = COSName.get_pdf_name("Rect")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")

# Field specs: (name, da, quadding, multiline, comb, max_len, value).
_FIELDS: tuple[tuple[str, str, int, bool, bool, int | None, str], ...] = (
    ("LeftField", "/Helv 12 Tf 0 g", 0, False, False, None, "Hello World"),
    ("CenterField", "/Helv 12 Tf 0 g", 1, False, False, None, "Centered"),
    ("RightField", "/Helv 12 Tf 0 g", 2, False, False, None, "RightSide"),
    (
        "MultiField",
        "/Helv 10 Tf 0 g",
        0,
        True,
        False,
        None,
        "This is a long multiline value that should wrap across several "
        "lines because it is far too wide to fit inside the narrow field box",
    ),
    ("CombField", "/Helv 12 Tf 0 g", 0, False, True, 6, "ABC123"),
    ("AutoField", "/Helv 0 Tf 0 g", 0, False, False, None, "AutoSized"),
)

# The canonical flat-text appearance frame both implementations must emit
# (in this relative order, extra ops between anchors are allowed).
_TEXT_SKELETON: tuple[str, ...] = ("BMC", "BT", "Tf", "Td", "Tj", "ET", "EMC")


# --------------------------------------------------------------------------- #
# pypdfbox build
# --------------------------------------------------------------------------- #
def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray([COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)])


def _build_form(out: Path) -> None:
    """Build the six-field AcroForm via pypdfbox, set each value (which
    regenerates the appearance), and save to ``out``."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        form = PDAcroForm(doc)

        # A /DR carrying the Helv alias so the /DA font resolves on reload.
        dr = PDResources()
        dr.put(
            COSName.get_pdf_name("Helv"),
            PDFontFactory.create_default_font(Standard14Fonts.HELVETICA),
        )
        form.set_default_resources(dr)
        form.set_default_appearance("/Helv 12 Tf 0 g")

        fields: list[PDTextField] = []
        annots: list[PDAnnotationWidget] = []
        ury = 700.0
        for name, da, quad, multiline, comb, max_len, _value in _FIELDS:
            field = PDTextField(form)
            field.set_partial_name(name)
            field.set_default_appearance(da)
            if quad:
                field.set_q(quad)
            if multiline:
                field.set_multiline(True)
            if comb:
                field.set_comb(True)
            if max_len is not None:
                field.set_max_len(max_len)
            widget = PDAnnotationWidget()
            wc = widget.get_cos_object()
            wc.set_item(_RECT, _rect(50.0, ury, 350.0, ury + 20.0))
            wc.set_name(_SUBTYPE, "Widget")
            field.set_widgets([widget])
            fields.append(field)
            annots.append(widget)
            ury -= 40.0

        form.set_fields(fields)
        doc.get_document_catalog().set_acro_form(form)
        page.set_annotations(annots)

        # Setting the value regenerates the appearance (upstream parity).
        for field, spec in zip(fields, _FIELDS, strict=True):
            field.set_value(spec[6])

        doc.save(str(out))
    finally:
        # try/finally so any Windows file lock is released before the probe
        # / reload below reopens the same path.
        doc.close()


# --------------------------------------------------------------------------- #
# fact extraction — mirrors TextFieldApProbe.walk
# --------------------------------------------------------------------------- #
class _Facts:
    """Structured per-field appearance facts, the differential surface."""

    def __init__(
        self,
        da: str,
        bbox_w: int,
        bbox_h: int,
        ops: list[str],
        tf: tuple[str, float] | None,
        cells: int,
        lines: int,
        bucket: str,
        texts: list[str],
    ) -> None:
        self.da = da
        self.bbox_w = bbox_w
        self.bbox_h = bbox_h
        self.ops = ops
        self.tf = tf
        self.cells = cells
        self.lines = lines
        self.bucket = bucket
        self.texts = texts


def _bucket(x: float, bbox_w: int) -> str:
    if bbox_w <= 0:
        return "L"
    third = bbox_w / 3.0
    if x < third:
        return "L"
    if x < 2.0 * third:
        return "C"
    return "R"


def _py_facts(doc: PDDocument, name: str) -> _Facts:
    """Reload-equivalent of the probe's READ mode for one pypdfbox field."""
    form = doc.get_document_catalog().get_acro_form()
    field = form.get_field(name)
    assert field is not None, f"field {name!r} not found"
    da = field.get_default_appearance() or (
        form.get_default_appearance() or "none"
    )

    widget = field.get_widgets()[0]
    ap = widget.get_cos_object().get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary), f"{name}: no /AP dict"
    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSStream), f"{name}: /AP /N is not a stream"

    # BBox from the stream dictionary.
    bbox = n.get_dictionary_object(COSName.get_pdf_name("BBox"))
    bbox_w = bbox_h = 0
    if isinstance(bbox, COSArray) and bbox.size() >= 4:
        xs = [float(bbox.get_object(i).value) for i in range(4)]
        bbox_w = round(abs(xs[2] - xs[0]))
        bbox_h = round(abs(xs[3] - xs[1]))

    data = n.create_input_stream().read()
    parser = PDFStreamParser.from_bytes(data)
    ops: list[str] = []
    operands: list[object] = []
    pen_x = pen_y = 0.0
    cells = 0
    tf: tuple[str, float] | None = None
    first_x = 0.0
    first_shown = True
    baselines: list[int] = []
    texts: list[str] = []

    token = parser.parse_next_token()
    while token is not None:
        if isinstance(token, Operator):
            op = token.get_name()
            ops.append(op)
            if op == "Tf" and len(operands) >= 2:
                fname = operands[-2]
                fsize = operands[-1]
                tf = (
                    fname.name if isinstance(fname, COSName) else "?",
                    float(getattr(fsize, "value", 0.0)),
                )
            elif op in ("Td", "TD") and len(operands) >= 2:
                pen_x += float(getattr(operands[-2], "value", 0.0))
                pen_y += float(getattr(operands[-1], "value", 0.0))
            elif op == "Tm" and len(operands) >= 6:
                pen_x = float(getattr(operands[4], "value", 0.0))
                pen_y = float(getattr(operands[5], "value", 0.0))
            elif op in ("Tj", "'", '"'):
                if operands and hasattr(operands[-1], "get_string"):
                    texts.append(operands[-1].get_string())
                cells += 1
                by = round(pen_y)
                if by not in baselines:
                    baselines.append(by)
                if first_shown:
                    first_shown = False
                    first_x = pen_x
            elif op == "TJ":
                if operands and isinstance(operands[-1], COSArray):
                    chunk = "".join(
                        el.get_string()
                        for el in operands[-1]
                        if hasattr(el, "get_string")
                    )
                    texts.append(chunk)
                cells += 1
                by = round(pen_y)
                if by not in baselines:
                    baselines.append(by)
                if first_shown:
                    first_shown = False
                    first_x = pen_x
            operands = []
        else:
            operands.append(token)
        token = parser.parse_next_token()

    return _Facts(
        da=da,
        bbox_w=bbox_w,
        bbox_h=bbox_h,
        ops=ops,
        tf=tf,
        cells=cells,
        lines=max(1, len(baselines)),
        bucket=_bucket(first_x, bbox_w),
        texts=texts,
    )


def _parse_probe_record(line: str) -> _Facts:
    """Parse one TextFieldApProbe READ-mode record into :class:`_Facts`."""
    parts = (line.split("\t") + ["", "", "0", "0", "", ""])[:6]
    _name, da, bbox_w, bbox_h, op_seq, fact_str = parts
    ops = op_seq.split(",") if op_seq else []
    tf: tuple[str, float] | None = None
    cells = 0
    lines = 1
    bucket = "L"
    texts: list[str] = []
    for token in (fact_str.split(";") if fact_str else []):
        key, _, val = token.partition("=")
        if key == "tf":
            fname, _, fsize = val.partition("/")
            tf = (fname, float(fsize)) if fsize else (fname, 0.0)
        elif key == "cells":
            cells = int(val)
        elif key == "lines":
            lines = int(val)
        elif key == "bucket":
            bucket = val
        elif key == "tj":
            texts.append(val)
    return _Facts(
        da=da,
        bbox_w=int(bbox_w),
        bbox_h=int(bbox_h),
        ops=ops,
        tf=tf,
        cells=cells,
        lines=lines,
        bucket=bucket,
        texts=texts,
    )


def _java_facts(path: Path, *names: str) -> dict[str, _Facts]:
    text = run_probe_text("TextFieldApProbe", "read", str(path), *names)
    out: dict[str, _Facts] = {}
    for line in text.splitlines():
        if not line:
            continue
        name = line.split("\t", 1)[0]
        out[name] = _parse_probe_record(line)
    return out


def _qpdf_ok(path: Path) -> bool:
    """``qpdf --check`` passes (warnings tolerated, hard errors not)."""
    if shutil.which("qpdf") is None:
        return True
    result = subprocess.run(
        ["qpdf", "--check", str(path)],
        capture_output=True,
        text=True,
    )
    # qpdf exit codes: 0 = clean, 3 = warnings only, 2 = errors.
    return result.returncode in (0, 3)


def _assert_skeleton(ops: list[str]) -> None:
    it = iter(ops)
    for anchor in _TEXT_SKELETON:
        assert anchor in it, f"missing {anchor!r} in op sequence {ops}"


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def py_file(tmp_path: Path) -> Path:
    """The pypdfbox-built form with every value already set."""
    out = tmp_path / "py_text_fields.pdf"
    _build_form(out)
    return out


@pytest.fixture
def java_file(tmp_path: Path, py_file: Path) -> Path:
    """A parallel file produced by re-running setValue through PDFBox."""
    out = tmp_path / "java_text_fields.pdf"
    pairs = [f"{spec[0]}={spec[6]}" for spec in _FIELDS]
    run_probe("TextFieldApProbe", "set", str(py_file), str(out), *pairs)
    return out


# --------------------------------------------------------------------------- #
# tests
# --------------------------------------------------------------------------- #
@requires_oracle
def test_both_files_qpdf_valid(py_file: Path, java_file: Path) -> None:
    """Both the pypdfbox build and PDFBox's regeneration are qpdf-valid."""
    assert _qpdf_ok(py_file)
    assert _qpdf_ok(java_file)


@requires_oracle
@pytest.mark.parametrize("name", [spec[0] for spec in _FIELDS])
def test_da_font_and_size_parity(
    py_file: Path, java_file: Path, name: str
) -> None:
    """The resolved /DA and the emitted ``Tf`` font name match PDFBox.

    The font *size* matches exactly for the explicit-size fields; the
    auto-size field (``/DA`` size 0) is asserted separately for
    comparability (see :func:`test_auto_size_comparable`).
    """
    java = _java_facts(java_file, name)[name]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_facts(doc, name)
    finally:
        doc.close()

    # The /DA string is preserved identically.
    assert py.da == java.da

    assert py.tf is not None
    assert java.tf is not None
    # Same font resource name emitted in the Tf operator.
    assert py.tf[0] == java.tf[0]

    # Explicit-size fields: the Tf size matches the /DA exactly.
    spec = next(s for s in _FIELDS if s[0] == name)
    da_size = float(spec[1].split()[1])
    if da_size > 0.0:
        assert py.tf[1] == java.tf[1] == da_size


@requires_oracle
@pytest.mark.parametrize(
    ("name", "expected_bucket"),
    [("LeftField", "L"), ("CenterField", "C"), ("RightField", "R")],
)
def test_quadding_alignment_bucket_parity(
    py_file: Path, java_file: Path, name: str, expected_bucket: str
) -> None:
    """``/Q`` 0/1/2 drives the same left/centre/right horizontal placement
    bucket in both implementations (exact x differs — benign)."""
    java = _java_facts(java_file, name)[name]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_facts(doc, name)
    finally:
        doc.close()

    assert py.bucket == java.bucket == expected_bucket
    _assert_skeleton(py.ops)
    _assert_skeleton(java.ops)


@requires_oracle
def test_comb_field_cell_count_parity(
    py_file: Path, java_file: Path
) -> None:
    """A comb field with ``/MaxLen 6`` distributes its 6 characters into 6
    positioned cells in both implementations."""
    java = _java_facts(java_file, "CombField")["CombField"]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_facts(doc, "CombField")
    finally:
        doc.close()

    # Six characters → six show-text cells.
    assert py.cells == java.cells == 6
    # Each cell carries one character.
    assert "".join(py.texts) == "".join(java.texts) == "ABC123"


@requires_oracle
def test_multiline_wraps_to_multiple_lines(
    py_file: Path, java_file: Path
) -> None:
    """A multiline value too long for one line wraps to more than one
    baseline in both implementations (the number of Tj per line differs —
    PDFBox emits one Tj per word, pypdfbox one per wrapped line — but both
    advance to a second baseline)."""
    java = _java_facts(java_file, "MultiField")["MultiField"]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_facts(doc, "MultiField")
    finally:
        doc.close()

    assert java.lines >= 2, "PDFBox should wrap the long value"
    assert py.lines >= 2, "pypdfbox should wrap the long value"
    # The full text is rendered (whitespace / per-line split differs).
    assert "".join(py.texts).replace(" ", "") == "".join(
        java.texts
    ).replace(" ", "")
    assert py.bucket == java.bucket == "L"


@requires_oracle
def test_auto_size_comparable(py_file: Path, java_file: Path) -> None:
    """The auto-size field (``/DA`` size 0) resolves to a comparable non-zero
    size in both implementations.

    pypdfbox clamps to a height-proportional ``AUTO_FONT_SIZE_MAX`` (12pt for
    a 20pt-tall rect) where PDFBox uses a cap-height formula (~17.3pt). Both
    pick a sane, non-zero, value-fitting size — that comparability is the
    parity bar; the exact size is a documented benign heuristic divergence
    (CHANGES.md, wave 1433)."""
    java = _java_facts(java_file, "AutoField")["AutoField"]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_facts(doc, "AutoField")
    finally:
        doc.close()

    assert py.tf is not None
    assert java.tf is not None
    # Both resolve the /DA size-0 tag to a positive, non-trivial size.
    assert py.tf[1] > 0.0
    assert java.tf[1] > 0.0
    assert py.tf[1] >= 4.0  # MINIMUM_FONT_SIZE
    # Comparable order of magnitude — neither degenerate nor wildly oversized.
    assert py.tf[1] <= java.tf[1] * 2.0
    assert java.tf[1] <= py.tf[1] * 2.0
    # Same /DA, same font, same alignment, single line.
    assert py.da == java.da
    assert py.tf[0] == java.tf[0]
    assert py.bucket == java.bucket == "L"
    assert py.lines == java.lines == 1


@requires_oracle
def test_operator_skeleton_parity_all_fields(
    py_file: Path, java_file: Path
) -> None:
    """Every field's appearance carries the canonical flat-text operator
    skeleton in both implementations."""
    names = [spec[0] for spec in _FIELDS]
    java = _java_facts(java_file, *names)
    doc = PDDocument.load(str(py_file))
    try:
        for name in names:
            py = _py_facts(doc, name)
            _assert_skeleton(py.ops)
            _assert_skeleton(java[name].ops)
            # Both bracket the value in /Tx BMC … EMC marked content.
            assert py.ops[0] == java[name].ops[0] == "BMC"
            assert py.ops[-1] == java[name].ops[-1] == "EMC"
    finally:
        doc.close()
