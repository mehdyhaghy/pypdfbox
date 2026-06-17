"""Live Apache PDFBox differential parity tests for COMB text-field
appearance generation (wave 1472).

Surface
-------
A ``PDTextField`` carrying the Comb ``/Ff`` flag (bit 25) plus ``/MaxLen N``.
On ``set_value`` the value's characters are laid out into N evenly-spaced
cells across the field width, each glyph centred in its comb cell, mirroring
``AppearanceGeneratorHelper.insertGeneratedCombAppearance``. The geometry is
the per-cell ``newLineAtOffset`` (``Td``) sequence:

  * ``combWidth = bboxW / maxLen``
  * ``baselineOffset = (bboxH - ascent/1000*fontSize) / 2`` on the first cell,
    0 thereafter
  * ``initialOffset = (combWidth - firstCharWidth/1000*fontSize) / 2`` with a
    ``/Q`` shift of ``(maxLen-numChars)*combWidth`` (right) or
    ``floor((maxLen-numChars)/2)*combWidth`` (centre) when the value is
    shorter than ``/MaxLen``
  * per cell ``xOffset = xOffset + prevCharWidth/2 - currCharWidth/2`` where
    ``currCharWidth = stringWidth/1000*fontSize/2``; after the first cell
    ``xOffset`` resets to ``combWidth``

Strategy
--------
A comb-field AcroForm is built *via pypdfbox* with the value already set (so
pypdfbox's ``set_value`` has regenerated the comb appearance) and saved once.
The Java ``CombFieldApProbe`` then re-runs ``setValue`` on the same file (so
upstream PDFBox composes its own comb appearance into the identical field
configuration) and saves a parallel file. Both files are read back through the
probe's READ mode (one JSON object per field). The Python side re-tokenises
the pypdfbox file's ``/AP /N`` with the same metric extraction so the two are
apples-to-apples.

Parity bar
----------
The comb geometry must match to a tight tolerance: the ``combWidth``, the cell
count, and every per-cell ``Td`` (dx, dy) offset. The Standard-14 Helvetica
glyph widths and font-descriptor ascent are identical between the two, so the
ascent-centred baseline and the incremental per-cell advance reproduce
exactly. Both files must pass ``qpdf --check`` (warnings tolerated).

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

import json
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

# Comb-field specs: (name, da, quadding, max_len, value). Each exercises a
# distinct comb geometry: a full value, and short values under each /Q so the
# initial-offset shift term is covered.
_FIELDS: tuple[tuple[str, str, int, int, str], ...] = (
    ("CombFull", "/Helv 12 Tf 0 g", 0, 6, "ABC123"),
    ("CombShortLeft", "/Helv 12 Tf 0 g", 0, 8, "WX9"),
    ("CombShortCenter", "/Helv 12 Tf 0 g", 1, 8, "WX9"),
    ("CombShortRight", "/Helv 12 Tf 0 g", 2, 8, "WX9"),
    ("CombWide", "/Helv 10 Tf 0 g", 0, 10, "1234567890"),
)

_TOL = 0.05  # user-space units; widths/ascent are identical so deltas match.


# --------------------------------------------------------------------------- #
# pypdfbox build
# --------------------------------------------------------------------------- #
def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray([COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)])


def _build_form(out: Path) -> None:
    """Build the comb-field AcroForm via pypdfbox, set each value (which
    regenerates the comb appearance), and save to ``out``."""
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
        form.set_default_appearance("/Helv 12 Tf 0 g")

        fields: list[PDTextField] = []
        annots: list[PDAnnotationWidget] = []
        ury = 700.0
        for name, da, quad, max_len, _value in _FIELDS:
            field = PDTextField(form)
            field.set_partial_name(name)
            field.set_default_appearance(da)
            field.set_comb(True)
            field.set_max_len(max_len)
            if quad:
                field.set_q(quad)
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

        for field, spec in zip(fields, _FIELDS, strict=True):
            field.set_value(spec[4])

        doc.save(str(out))
    finally:
        doc.close()


# --------------------------------------------------------------------------- #
# fact extraction
# --------------------------------------------------------------------------- #
class _Comb:
    """Comb geometry facts — the differential surface."""

    def __init__(
        self,
        max_len: int,
        bbox_w: float,
        bbox_h: float,
        comb_width: float,
        tds: list[tuple[float, float]],
        text: str,
    ) -> None:
        self.max_len = max_len
        self.bbox_w = bbox_w
        self.bbox_h = bbox_h
        self.comb_width = comb_width
        self.tds = tds
        self.text = text


def _py_comb(doc: PDDocument, name: str) -> _Comb:
    """Reload-equivalent of the probe's READ mode for one pypdfbox field."""
    form = doc.get_document_catalog().get_acro_form()
    field = form.get_field(name)
    assert field is not None, f"field {name!r} not found"
    max_len = field.get_max_len()

    widget = field.get_widgets()[0]
    ap = widget.get_cos_object().get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary), f"{name}: no /AP dict"
    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSStream), f"{name}: /AP /N is not a stream"

    bbox = n.get_dictionary_object(COSName.get_pdf_name("BBox"))
    bbox_w = bbox_h = 0.0
    if isinstance(bbox, COSArray) and bbox.size() >= 4:
        xs = [float(bbox.get_object(i).value) for i in range(4)]
        bbox_w = abs(xs[2] - xs[0])
        bbox_h = abs(xs[3] - xs[1])

    data = n.create_input_stream().read()
    parser = PDFStreamParser.from_bytes(data)
    operands: list[object] = []
    tds: list[tuple[float, float]] = []
    text_parts: list[str] = []

    token = parser.parse_next_token()
    while token is not None:
        if isinstance(token, Operator):
            op = token.get_name()
            if op in ("Td", "TD") and len(operands) >= 2:
                dx = float(getattr(operands[-2], "value", 0.0))
                dy = float(getattr(operands[-1], "value", 0.0))
                tds.append((dx, dy))
            elif op == "Tj" and operands and hasattr(operands[-1], "get_string"):
                text_parts.append(operands[-1].get_string())
            operands = []
        else:
            operands.append(token)
        token = parser.parse_next_token()

    comb_width = (bbox_w / max_len) if max_len > 0 else 0.0
    return _Comb(
        max_len=max_len,
        bbox_w=bbox_w,
        bbox_h=bbox_h,
        comb_width=comb_width,
        tds=tds,
        text="".join(text_parts),
    )


def _parse_probe_record(line: str) -> _Comb:
    obj = json.loads(line)
    tds = [(float(t[0]), float(t[1])) for t in obj["tds"]]
    return _Comb(
        max_len=int(obj["maxLen"]),
        bbox_w=float(obj["bboxW"]),
        bbox_h=float(obj["bboxH"]),
        comb_width=float(obj["combWidth"]),
        tds=tds,
        text=obj["text"],
    )


def _java_comb(path: Path, *names: str) -> dict[str, _Comb]:
    text = run_probe_text("CombFieldApProbe", "read", str(path), *names)
    out: dict[str, _Comb] = {}
    lines = [ln for ln in text.splitlines() if ln.strip()]
    for name, line in zip(names, lines, strict=True):
        out[name] = _parse_probe_record(line)
    return out


def _qpdf_ok(path: Path) -> bool:
    if shutil.which("qpdf") is None:
        return True
    result = subprocess.run(
        ["qpdf", "--check", str(path)],
        capture_output=True,
        text=True,
    )
    return result.returncode in (0, 3)


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def py_file(tmp_path: Path) -> Path:
    out = tmp_path / "py_comb_fields.pdf"
    _build_form(out)
    return out


@pytest.fixture
def java_file(tmp_path: Path, py_file: Path) -> Path:
    out = tmp_path / "java_comb_fields.pdf"
    pairs = [f"{spec[0]}={spec[4]}" for spec in _FIELDS]
    run_probe("CombFieldApProbe", "set", str(py_file), str(out), *pairs)
    return out


# --------------------------------------------------------------------------- #
# tests
# --------------------------------------------------------------------------- #
@requires_oracle
def test_both_files_qpdf_valid(py_file: Path, java_file: Path) -> None:
    assert _qpdf_ok(py_file)
    assert _qpdf_ok(java_file)


@requires_oracle
@pytest.mark.parametrize("name", [spec[0] for spec in _FIELDS])
def test_comb_width_and_cell_count_parity(
    py_file: Path, java_file: Path, name: str
) -> None:
    """The comb cell width and the number of positioned cells match PDFBox."""
    java = _java_comb(java_file, name)[name]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_comb(doc, name)
    finally:
        doc.close()

    assert py.max_len == java.max_len
    assert abs(py.bbox_w - java.bbox_w) < _TOL
    assert abs(py.bbox_h - java.bbox_h) < _TOL
    assert abs(py.comb_width - java.comb_width) < _TOL
    # One positioned cell per character (value length, capped at MaxLen).
    spec = next(s for s in _FIELDS if s[0] == name)
    expected_cells = min(len(spec[4]), spec[3])
    assert len(py.tds) == len(java.tds) == expected_cells
    assert py.text == java.text == spec[4]


@requires_oracle
@pytest.mark.parametrize("name", [spec[0] for spec in _FIELDS])
def test_comb_per_cell_td_offsets_parity(
    py_file: Path, java_file: Path, name: str
) -> None:
    """Every per-cell ``Td`` (dx, dy) offset matches PDFBox to tolerance.

    This is the core comb geometry: the ascent-centred baseline on the first
    cell, 0 thereafter, and the incremental
    ``xOffset = xOffset + prevCharWidth/2 - currCharWidth/2`` per-cell advance
    (with the ``/Q`` initial-offset shift for short values)."""
    java = _java_comb(java_file, name)[name]
    doc = PDDocument.load(str(py_file))
    try:
        py = _py_comb(doc, name)
    finally:
        doc.close()

    assert len(py.tds) == len(java.tds)
    for i, (p, j) in enumerate(zip(py.tds, java.tds, strict=True)):
        assert abs(p[0] - j[0]) < _TOL, (
            f"{name} cell {i} dx: py={p[0]} java={j[0]}"
        )
        assert abs(p[1] - j[1]) < _TOL, (
            f"{name} cell {i} dy: py={p[1]} java={j[1]}"
        )
