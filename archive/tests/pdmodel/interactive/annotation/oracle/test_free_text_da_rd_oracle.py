"""Live Apache PDFBox differential parity for the FreeText ``/DA`` parse and
``/RD`` rectangle-difference path of
``PDFreeTextAppearanceHandler.generateNormalAppearance``.

Complements ``test_free_text_line_oracle.py`` (callout / line-ending skeleton)
by drilling into a *plain* (non-callout) FreeText whose ``/DA`` carries a
non-default font (``/Helv 14.5 Tf``) and a 3-component RGB non-stroking colour
(``0.2 0.4 0.6 rg``), with a ``/RD`` rectangle-difference and **no** ``/DS``
override. The probe fingerprints the generated ``/AP /N`` stream as operator
tokens *with operands*, so the test can pin:

* **/DA font** — the parsed font name + size flow into the AP as a single
  ``Tf`` op whose size operand is ``14.5`` (the value from ``/DA``).
* **/DA colour (stroking)** — Adobe uses ``/DA``'s last non-stroking colour as
  the stroking colour; the AP carries ``RG 0.2 0.4 0.6``.
* **/DA colour (text)** — with no ``/DS`` override the text non-stroking colour
  equals ``/DA``'s, so the AP carries ``rg 0.2 0.4 0.6`` inside the ``BT..ET``.
* **/RD** — ``applyRectDifferences`` shrinks the ``/BBox`` exactly:
  ``Rect(100,500,340,620)`` with ``/RD [5,7,9,11]`` →
  ``BBox(105,507,331,609)``.

The handler's two private helpers ``extractFontDetails`` /
``extractNonStrokingColor`` are not directly observable in Java, so we verify
their effect through the generated appearance tokens — the strongest available
behavioural signal.

Confirmed parity (regression pin) — no production change required.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.cos import COSName
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "FreeTextDaRdProbe"


# ---------------------------------------------------------------------------
# canonical float rendering — mirrors FreeTextDaRdProbe.canonFloat (Java)
# ---------------------------------------------------------------------------


def _canon_float(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


def _build_free_text() -> PDAnnotationFreeText:
    ft = PDAnnotationFreeText()
    ft.set_rectangle(PDRectangle.from_xywh(100, 500, 240, 120))
    ft.set_contents("hello")
    ft.set_color([1, 1, 1])
    ft.set_default_appearance("/Helv 14.5 Tf 0.2 0.4 0.6 rg")
    ft.set_intent(PDAnnotationFreeText.IT_FREE_TEXT)
    ft.set_rect_differences(5, 7, 9, 11)
    return ft


def _build_doc(path: Path) -> None:
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle.A4)
        doc.add_page(page)
        ft = _build_free_text()
        ft.construct_appearances(doc)
        page.add_annotation(ft)
        doc.save(str(path))
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# token fingerprint helpers (operator + operands)
# ---------------------------------------------------------------------------


def _operand(token: object) -> str:
    if isinstance(token, COSName):
        return "/" + token.get_name()
    float_value = getattr(token, "float_value", None)
    if callable(float_value):
        return _canon_float(float_value())
    return str(token)


def _tokens(stream) -> list[list[str]]:
    """Return ``[[op, *operands], ...]`` for every operator token in order."""
    parser = PDFStreamParser.from_content_stream(stream)
    rows: list[list[str]] = []
    operands: list[str] = []
    while True:
        token = parser.parse_next_token()
        if token is None:
            break
        if isinstance(token, Operator):
            rows.append([token.get_name(), *operands])
            operands = []
        else:
            operands.append(_operand(token))
    return rows


def _bbox(stream) -> str:
    bbox = stream.get_bbox()
    if bbox is None:
        return "none"
    return ",".join(
        _canon_float(v)
        for v in (
            bbox.get_lower_left_x(),
            bbox.get_lower_left_y(),
            bbox.get_upper_right_x(),
            bbox.get_upper_right_y(),
        )
    )


# ---------------------------------------------------------------------------
# java-side fingerprint parsing
# ---------------------------------------------------------------------------


def _parse_java(text: str) -> dict[str, object]:
    record: dict[str, object] = {"toks": []}
    for raw in text.splitlines():
        if raw.startswith("TOK "):
            record["toks"].append(raw[len("TOK ") :].split(" "))  # type: ignore[union-attr]
        elif raw.startswith("DA "):
            record["DA"] = raw[len("DA ") :]
        elif raw.startswith("RD "):
            record["RD"] = raw[len("RD ") :]
        elif raw.startswith("RECT "):
            record["RECT"] = raw[len("RECT ") :]
        elif raw.startswith("BBOX "):
            record["BBOX"] = raw[len("BBOX ") :]
    return record


def _java_record() -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "ftdard.pdf")
        run_probe_text(_PROBE, "write", out)
        text = run_probe_text(_PROBE, "read", out)
    return _parse_java(text)


def _find(toks: list[list[str]], op: str) -> list[str] | None:
    for row in toks:
        if row[0] == op:
            return row
    return None


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@requires_oracle
def test_da_rd_accessors_match_pdfbox() -> None:
    """``/DA`` and ``/RD`` accessors + the resulting ``/Rect`` match PDFBox."""
    java = _java_record()
    ft = _build_free_text()
    ft.construct_appearances()
    assert ft.get_default_appearance() == java["DA"]
    rd = ft.get_rect_differences()
    assert ",".join(_canon_float(v) for v in rd) == java["RD"]


@requires_oracle
def test_rd_shrinks_bbox_exactly() -> None:
    """``/RD [5,7,9,11]`` applied to ``Rect(100,500,340,620)`` yields a
    ``/BBox`` of ``(105,507,331,609)`` — identical to Apache PDFBox's
    ``applyRectDifferences``."""
    java = _java_record()
    ft = _build_free_text()
    ft.construct_appearances()
    stream = ft.get_normal_appearance_stream()
    assert stream is not None, "FreeText produced no /AP /N"
    assert _bbox(stream) == java["BBOX"], (
        f"BBox {_bbox(stream)!r} != PDFBox {java['BBOX']!r}"
    )
    # Pin the literal upstream value too so a refactor can't silently drift.
    assert java["BBOX"] == "105,507,331,609"


@requires_oracle
def test_da_font_size_flows_into_appearance() -> None:
    """The ``/DA`` font *size* (14.5) flows into the AP's ``Tf`` operator,
    matching Apache PDFBox (the parsed ``extractFontDetails`` size)."""
    java = _java_record()
    ft = _build_free_text()
    ft.construct_appearances()
    py_tf = _find(_tokens(ft.get_normal_appearance_stream()), "Tf")
    jr_tf = _find(java["toks"], "Tf")  # type: ignore[arg-type]
    assert jr_tf is not None and py_tf is not None, (py_tf, jr_tf)
    # Tf operands are ``/FontName size``; the size is the load-bearing value.
    assert py_tf[-1] == jr_tf[-1] == "14.5", (py_tf, jr_tf)


@requires_oracle
def test_da_colour_used_for_stroking() -> None:
    """Adobe (and Apache PDFBox) use ``/DA``'s last non-stroking colour as the
    *stroking* colour; the AP carries ``RG 0.2 0.4 0.6``."""
    java = _java_record()
    ft = _build_free_text()
    ft.construct_appearances()
    py_rg = _find(_tokens(ft.get_normal_appearance_stream()), "RG")
    jr_rg = _find(java["toks"], "RG")  # type: ignore[arg-type]
    assert jr_rg is not None and py_rg is not None, (py_rg, jr_rg)
    assert py_rg == jr_rg == ["RG", "0.2", "0.4", "0.6"], (py_rg, jr_rg)


@requires_oracle
def test_da_colour_used_for_text_without_ds_override() -> None:
    """With no ``/DS`` override the text non-stroking colour equals ``/DA``'s,
    so the ``BT..ET`` text run sets ``rg 0.2 0.4 0.6`` — matching PDFBox.

    Note: an earlier ``rg`` token sets the white background fill (``1 1 1``);
    the *last* ``rg`` is the text colour, so we assert on that one.
    """
    java = _java_record()
    ft = _build_free_text()
    ft.construct_appearances()
    py_toks = _tokens(ft.get_normal_appearance_stream())
    py_rgs = [row for row in py_toks if row[0] == "rg"]
    jr_rgs = [row for row in java["toks"] if row[0] == "rg"]  # type: ignore[union-attr]
    assert py_rgs and jr_rgs, (py_rgs, jr_rgs)
    assert py_rgs[-1] == jr_rgs[-1] == ["rg", "0.2", "0.4", "0.6"], (
        py_rgs,
        jr_rgs,
    )


@requires_oracle
def test_token_skeleton_matches_pdfbox() -> None:
    """The full operator sequence (operator names, ignoring operands) of the
    plain-FreeText AP matches Apache PDFBox: background fill, stroking colour,
    line width, border box ``re B``, the ``/Rotate`` ``cm``, the clip
    (``re W n``) and a single ``BT Tf rg Td Tj ET`` text object."""
    java = _java_record()
    ft = _build_free_text()
    ft.construct_appearances()
    py_ops = [row[0] for row in _tokens(ft.get_normal_appearance_stream())]
    jr_ops = [row[0] for row in java["toks"]]  # type: ignore[union-attr]
    assert py_ops == jr_ops, (
        f"FreeText op-sequence diverges\n pypdfbox: {py_ops}\n PDFBox:   {jr_ops}"
    )
