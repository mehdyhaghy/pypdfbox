"""Live Apache PDFBox differential parity tests for LIST-BOX appearance
generation (wave 1457).

Surface: :class:`PDListBox` ``set_value`` regenerating the widget ``/AP /N``
content stream via ``PDAppearanceGenerator._generate_choice`` /
``_regenerate_listbox_widget`` — upstream PDFBox's
``insertGeneratedListboxAppearance``. That routine:

  * draws **every** ``/Opt`` row one-per-line starting at the ``/TI`` scroll
    offset (top index), not just the selected ones,
  * paints a flat highlight **fill** rectangle behind each row whose index is
    selected (``/I`` or matched via ``/V``),
  * shows each row's display label as one ``Tj``.

The differential here is the generated CONTENT of the list-box appearance —
distinct from the value/``/I``/``/TI`` *data* surface already pinned by
``test_list_box_detail_oracle.py`` and the *text*-field appearance pinned by
``test_text_field_ap_oracle.py``. No prior probe tokenises a list-box ``/AP /N``.

Strategy
--------
A multi-select list box is built **via pypdfbox** (:func:`_build_listbox`) with
four export/display ``/Opt`` pairs and two options pre-selected; setting the
value regenerates pypdfbox's appearance. The Java ``ListBoxApProbe`` loads the
*same* file, re-runs ``setValue`` (so upstream composes its own appearance into
the identical field), and saves a parallel file. Both ``/AP /N`` streams are
tokenised the same way and compared.

Parity bar — STRUCTURAL, not byte-exact
---------------------------------------
Exact coordinates and the highlight-colour operator encoding legitimately
differ (PDFBox emits an explicit colour-space ``sc``; the lite port emits the
equivalent ``rg``). What MUST match:

  * the ``/Tx BMC … EMC`` marked-content frame,
  * the resolved ``Tf`` font resource name + size,
  * one show-text row per visible option, with the same row labels in order,
  * one highlight **fill** per selected visible row (same count).

Both outputs must pass ``qpdf --check`` (warnings tolerated).

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit) — no upstream fixture carries a
pre-selected multi-select list box with export/display ``/Opt`` pairs.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_PROBE = "ListBoxApProbe"

_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")

# Four export/display option pairs; "e1" and "e3" pre-selected.
_EXPORT = ["e1", "e2", "e3", "e4"]
_DISPLAY = ["Display 1", "Display 2", "Display 3", "Display 4"]
_FIELD = "ApList"

# The canonical list-box appearance frame both implementations must emit
# (relative order; extra ops between anchors are allowed).
_SKELETON: tuple[str, ...] = ("BMC", "BT", "Tf", "Tj", "ET", "EMC")


# --------------------------------------------------------------------------- #
# pypdfbox build
# --------------------------------------------------------------------------- #
def _build_listbox(out: Path, *, top_index: int = 0) -> None:
    """A multi-select list box with four /Opt pairs, ``e3`` + ``e1`` selected,
    scrolled to ``top_index``. Setting the value regenerates the appearance."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        form = PDAcroForm(doc)

        dr = PDResources()
        dr.put(
            COSName.get_pdf_name("Helv"),
            PDFontFactory.create_default_font(Standard14Fonts.HELVETICA),
        )
        form.set_default_resources(dr)
        form.set_default_appearance("/Helv 10 Tf 0 g")
        doc.get_document_catalog().set_acro_form(form)

        lb = PDListBox(form)
        lb.set_partial_name(_FIELD)
        lb.set_multi_select(True)
        lb.set_default_appearance("/Helv 10 Tf 0 g")
        lb.set_options(_EXPORT, _DISPLAY)

        widget = lb.get_widgets()[0]
        widget.set_rectangle(PDRectangle(50, 500, 200, 100))
        widget.set_page(page)
        page.get_annotations().append(widget)
        form.set_fields([lb])

        lb.set_top_index(top_index)
        # Out of /Opt order: /V keeps insertion order, /I sorts to 0,2.
        lb.set_value(["e3", "e1"])
        doc.save(str(out))
    finally:
        doc.close()


# --------------------------------------------------------------------------- #
# fact extraction — mirrors ListBoxApProbe.walk
# --------------------------------------------------------------------------- #
class _Facts:
    """Structured per-field list-box appearance facts."""

    def __init__(
        self,
        bbox_w: int,
        bbox_h: int,
        ops: list[str],
        tf: tuple[str, float] | None,
        rows: int,
        fills: int,
        texts: list[str],
    ) -> None:
        self.bbox_w = bbox_w
        self.bbox_h = bbox_h
        self.ops = ops
        self.tf = tf
        self.rows = rows
        self.fills = fills
        self.texts = texts


def _py_facts(doc: PDDocument, name: str) -> _Facts:
    form = doc.get_document_catalog().get_acro_form()
    field = form.get_field(name)
    assert isinstance(field, PDListBox), f"field {name!r} is not a list box"

    widget = field.get_widgets()[0]
    ap = widget.get_cos_object().get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary), f"{name}: no /AP dict"
    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSStream), f"{name}: /AP /N is not a stream"

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
    tf: tuple[str, float] | None = None
    rows = 0
    fills = 0
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
            elif op in ("f", "F", "f*"):
                fills += 1
            elif op in ("Tj", "'", '"'):
                if operands and hasattr(operands[-1], "get_string"):
                    texts.append(operands[-1].get_string())
                rows += 1
            elif op == "TJ":
                if operands and isinstance(operands[-1], COSArray):
                    chunk = "".join(
                        el.get_string()
                        for el in operands[-1]
                        if hasattr(el, "get_string")
                    )
                    texts.append(chunk)
                rows += 1
            operands = []
        else:
            operands.append(token)
        token = parser.parse_next_token()

    return _Facts(bbox_w, bbox_h, ops, tf, rows, fills, texts)


def _parse_probe_record(line: str) -> _Facts:
    """Parse one ListBoxApProbe READ-mode record into :class:`_Facts`."""
    parts = (line.split("\t") + ["0", "0", "", ""])[:5]
    _name, bbox_w, bbox_h, op_seq, fact_str = parts
    ops = op_seq.split(",") if op_seq else []
    tf: tuple[str, float] | None = None
    rows = 0
    fills = 0
    texts: list[str] = []
    for token in (fact_str.split(";") if fact_str else []):
        key, _, val = token.partition("=")
        if key == "tf":
            fname, _, fsize = val.partition("/")
            tf = (fname, float(fsize)) if fsize else (fname, 0.0)
        elif key == "rows":
            rows = int(val)
        elif key == "fills":
            fills = int(val)
        elif key == "tj":
            texts.append(val)
    return _Facts(int(bbox_w), int(bbox_h), ops, tf, rows, fills, texts)


def _java_facts(path: Path, *names: str) -> dict[str, _Facts]:
    text = run_probe_text(_PROBE, "read", str(path), *names)
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
    return result.returncode in (0, 3)


def _assert_skeleton(ops: list[str]) -> None:
    it = iter(ops)
    for anchor in _SKELETON:
        assert anchor in it, f"missing {anchor!r} in op sequence {ops}"


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def py_file(tmp_path: Path) -> Path:
    """The pypdfbox-built list box with its value already set."""
    out = tmp_path / "py_listbox.pdf"
    _build_listbox(out)
    return out


@pytest.fixture
def java_file(tmp_path: Path, py_file: Path) -> Path:
    """A parallel file produced by re-running setValue through PDFBox."""
    out = tmp_path / "java_listbox.pdf"
    run_probe(_PROBE, "set", str(py_file), str(out), f"{_FIELD}=e3|e1")
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
def test_listbox_marked_content_frame_parity(
    py_file: Path, java_file: Path
) -> None:
    """The list-box appearance carries the canonical ``/Tx BMC … EMC`` text
    frame in both implementations."""
    java = _java_facts(java_file, _FIELD)[_FIELD]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_facts(doc, _FIELD)
    finally:
        doc.close()

    _assert_skeleton(py.ops)
    _assert_skeleton(java.ops)
    assert py.ops[0] == java.ops[0] == "BMC"
    assert py.ops[-1] == java.ops[-1] == "EMC"


@requires_oracle
def test_listbox_font_parity(py_file: Path, java_file: Path) -> None:
    """The resolved ``Tf`` font resource name + size match PDFBox (the /DA is
    ``/Helv 10`` → both emit the Helv alias at size 10)."""
    java = _java_facts(java_file, _FIELD)[_FIELD]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_facts(doc, _FIELD)
    finally:
        doc.close()

    assert py.tf is not None
    assert java.tf is not None
    assert py.tf[0] == java.tf[0]
    assert py.tf[1] == java.tf[1] == 10.0


@requires_oracle
def test_listbox_all_rows_rendered_parity(
    py_file: Path, java_file: Path
) -> None:
    """Every option row is drawn (not just the selected ones), with the same
    display labels in the same order, in both implementations."""
    java = _java_facts(java_file, _FIELD)[_FIELD]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_facts(doc, _FIELD)
    finally:
        doc.close()

    # All four options rendered as four show-text rows.
    assert py.rows == java.rows == len(_DISPLAY)
    assert py.texts == java.texts == _DISPLAY


@requires_oracle
def test_listbox_selection_highlight_count_parity(
    py_file: Path, java_file: Path
) -> None:
    """Each selected visible row gets exactly one highlight fill rectangle —
    two selections (``e1`` row 0, ``e3`` row 2) → two fills in both
    implementations."""
    java = _java_facts(java_file, _FIELD)[_FIELD]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_facts(doc, _FIELD)
    finally:
        doc.close()

    assert py.fills == java.fills == 2


@requires_oracle
def test_listbox_top_index_scroll_parity(tmp_path: Path) -> None:
    """A ``/TI`` scroll offset hides the rows above it from the rendered text:
    with top index 2 only options 2 and 3 ("Display 3", "Display 4") are drawn.

    Selection highlights, however, are emitted for **every** selected option
    regardless of the scroll window — upstream's
    ``insertGeneratedListboxSelectionHighlight`` loops over the full selected-
    index set and positions each rect relative to ``/TI``, so a selection
    scrolled above the window (here ``e1`` at index 0) still gets a fill that
    lands off the top of the rect and is clipped by the ``/Tx`` clip path. So
    both selected rows (``e1`` + ``e3``) yield two fills in both
    implementations — this is the regression the production fix pins."""
    py_file = tmp_path / "py_ti.pdf"
    _build_listbox(py_file, top_index=2)
    java_file = tmp_path / "java_ti.pdf"
    run_probe(_PROBE, "set", str(py_file), str(java_file), f"{_FIELD}=e3|e1")

    java = _java_facts(java_file, _FIELD)[_FIELD]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_facts(doc, _FIELD)
    finally:
        doc.close()

    # Top index 2 → rows e3, e4 visible (Display 3, Display 4).
    assert py.texts == java.texts == ["Display 3", "Display 4"]
    assert py.rows == java.rows == 2
    # Highlights are emitted for both selected options, not gated on the
    # visible window (e1's lands off-screen, clipped).
    assert py.fills == java.fills == 2
    assert _qpdf_ok(py_file)
    assert _qpdf_ok(java_file)
