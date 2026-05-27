"""Live Apache PDFBox differential parity for the FreeText-callout and
Line-caption annotation specifics.

This complements the appearance-generation batteries (waves 1414 / the gen2
file) by drilling into the *callout / line-ending* details of two markup types:

* ``FreeText`` with ``/DA`` default appearance, ``/Q 1`` quadding,
  ``/CL`` callout line, ``/LE /OpenArrow`` line ending and
  ``/IT /FreeTextCallout`` intent.
* ``Line`` with ``/L`` coordinates, ``/LE [/Diamond /ClosedArrow]`` start/end
  endings, ``/LL 10`` leader length, a ``/Cap true`` caption positioned
  ``/CP /Top`` and an ``/IC`` interior colour.

How it works
------------
The Java probe ``FreeTextLineProbe`` runs in two modes:

* ``write out.pdf`` — builds the two annotations above, calls
  ``constructAppearances(doc)`` on each and saves.
* ``read out.pdf`` — re-opens and emits, per annotation: the accessor lines
  (FreeText: ``DA``/``Q``/``IT``/``LE``/``DS``/``CL``; Line:
  ``L``/``LE_START``/``LE_END``/``LL``/``CAP``/``CP``) then the coordinate-
  independent ``/AP /N`` fingerprint (``BBOX <canonical floats>`` + one
  ``OP:<name>`` per operator token).

pypdfbox builds the identical annotations and emits the same fingerprint.

Parity asserted
---------------
* **Accessors** — every FreeText / Line accessor matches Apache PDFBox exactly.
* **BBox** — the generated ``/AP /N`` ``/BBox`` matches exactly per type.
* **Line op-sequence** — matches Apache PDFBox **exactly** (the leader lines,
  the caption text run, the Diamond start ending and the ClosedArrow end
  ending are all present in the same order).
* **FreeText op-sequence** — the structural skeleton matches: callout polyline
  drawn (``m l l S``), the OpenArrow ending drawn inside a ``q ... Q`` block,
  the border box, the ``/Rotate`` ``cm``, the clip, and a ``BT ... ET`` text
  object that shows the contents. See the documented divergence below.

FIXED this wave
---------------
``PDFreeTextAppearanceHandler`` emitted the ``/Rotate`` ``cm`` operator only
when ``/Rotate`` was non-zero (``if rotation:``). Upstream emits it
unconditionally — ``getRotateInstance(0, 0, 0)`` is the identity matrix but
the ``cm`` token is still written — so the lite stream was one ``cm`` short of
Apache PDFBox's. Fixed to emit the transform unconditionally; the FreeText
appearance op-sequence now carries the ``cm`` exactly where PDFBox does.

Documented (NOT fixed — legitimate lite-surface difference)
-----------------------------------------------------------
* **FreeText text layout**: upstream word-wraps ``/Contents`` with
  ``PlainTextFormatter`` into multiple ``Td Tj`` runs; the lite handler emits
  one ``Td Tj`` per ``\\n``-terminated segment (here a single run). ``/BBox``,
  the callout/arrow/border/clip skeleton and the ``BT Tf rg ... ET`` text
  object all match; only the number of ``Td Tj`` pairs inside the text object
  differs (documented in the handler + ``CHANGES.md``). The test asserts the
  shared skeleton plus "at least one ``Td Tj``", not the exact run count.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "FreeTextLineProbe"


# ---------------------------------------------------------------------------
# canonical float rendering — mirrors FreeTextLineProbe.canonFloat (Java)
# ---------------------------------------------------------------------------


def _canon_float(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


def _operators(stream) -> list[str]:
    parser = PDFStreamParser.from_content_stream(stream)
    ops: list[str] = []
    while True:
        token = parser.parse_next_token()
        if token is None:
            break
        if isinstance(token, Operator):
            ops.append(token.get_name())
    return ops


def _bbox_line(stream) -> str:
    bbox = stream.get_bbox()
    if bbox is None:
        return "BBOX none"
    return "BBOX " + ",".join(
        _canon_float(v)
        for v in (
            bbox.get_lower_left_x(),
            bbox.get_lower_left_y(),
            bbox.get_upper_right_x(),
            bbox.get_upper_right_y(),
        )
    )


def _rect(x: float, y: float, w: float, h: float) -> PDRectangle:
    return PDRectangle.from_xywh(x, y, w, h)


def _build_free_text() -> PDAnnotationFreeText:
    ft = PDAnnotationFreeText()
    ft.set_rectangle(_rect(200, 600, 200, 100))
    ft.set_contents("callout text")
    ft.set_color([1, 1, 0])
    ft.set_default_appearance("/Helv 12 Tf 0 0 1 rg")
    ft.set_q(1)
    ft.set_intent(PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT)
    ft.set_callout([150, 560, 180, 610, 200, 650])
    ft.set_line_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    ft.set_default_style_string("font: Helvetica 12pt; color: #0000FF")
    return ft


def _build_line() -> PDAnnotationLine:
    ln = PDAnnotationLine()
    ln.set_rectangle(_rect(50, 200, 300, 200))
    ln.set_line([60, 250, 340, 350])
    ln.set_start_point_ending_style(PDAnnotationLine.LE_DIAMOND)
    ln.set_end_point_ending_style(PDAnnotationLine.LE_CLOSED_ARROW)
    ln.set_leader_line_length(10)
    ln.set_caption(True)
    ln.set_caption_positioning("Top")
    ln.set_contents("measured")
    ln.set_color([1, 0, 0])
    ln.set_interior_color([0, 1, 0])
    return ln


def _build_doc(path: Path) -> None:
    """Build the same battery as FreeTextLineProbe.write and save it."""
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle.A4)
        doc.add_page(page)
        ft = _build_free_text()
        ft.construct_appearances(doc)
        page.add_annotation(ft)
        ln = _build_line()
        ln.construct_appearances(doc)
        page.add_annotation(ln)
        doc.save(str(path))
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# java-side fingerprint parsing
# ---------------------------------------------------------------------------


def _parse_java(text: str) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    subtype: str | None = None
    for raw in text.splitlines():
        if raw.startswith("ANNOT "):
            subtype = raw[len("ANNOT ") :]
            current = {"acc": {}, "bbox": None, "ops": []}
        elif raw.startswith("OP:"):
            assert current is not None
            current["ops"].append(raw[len("OP:") :])  # type: ignore[union-attr]
        elif raw.startswith("BBOX "):
            assert current is not None
            current["bbox"] = raw
        elif raw == "NOAP":
            assert current is not None
            current["bbox"] = "NOAP"
        elif raw == "END":
            assert current is not None and subtype is not None
            records[subtype] = current
            current = None
        else:
            # accessor line "KEY value..."
            assert current is not None
            key, _, value = raw.partition(" ")
            current["acc"][key] = value  # type: ignore[index]
    return records


def _java_records() -> dict[str, dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "ftl.pdf")
        run_probe_text(_PROBE, "write", out)
        text = run_probe_text(_PROBE, "read", out)
    return _parse_java(text)


# ---------------------------------------------------------------------------
# python-side accessor fingerprint (mirrors the probe's emit* helpers)
# ---------------------------------------------------------------------------


def _free_text_accessors(ft: PDAnnotationFreeText) -> dict[str, str]:
    callout = ft.get_callout()
    return {
        "DA": ft.get_default_appearance() or "null",
        "Q": str(ft.get_q()),
        "IT": ft.get_intent() or "null",
        "LE": ft.get_line_ending_style(),
        "DS": ft.get_default_style_string() or "null",
        "CL": (
            "null"
            if not callout
            else ",".join(_canon_float(v) for v in callout)
        ),
    }


def _line_accessors(ln: PDAnnotationLine) -> dict[str, str]:
    line = ln.get_line()
    return {
        "L": (
            "null" if not line else ",".join(_canon_float(v) for v in line)
        ),
        "LE_START": ln.get_start_point_ending_style(),
        "LE_END": ln.get_end_point_ending_style(),
        "LL": _canon_float(ln.get_leader_line_length()),
        "CAP": "true" if ln.has_caption() else "false",
        "CP": ln.get_caption_positioning() or "null",
    }


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@requires_oracle
def test_free_text_accessors_match_pdfbox() -> None:
    """FreeText /DA, /Q, /IT, /LE, /DS, /CL accessors match Apache PDFBox."""
    java = _java_records()["FreeText"]["acc"]
    py = _free_text_accessors(_build_free_text())
    assert py == java, f"FreeText accessor mismatch\n py: {py}\n java: {java}"


@requires_oracle
def test_line_accessors_match_pdfbox() -> None:
    """Line /L, start/end /LE, /LL, /Cap, /CP accessors match Apache PDFBox."""
    java = _java_records()["Line"]["acc"]
    py = _line_accessors(_build_line())
    assert py == java, f"Line accessor mismatch\n py: {py}\n java: {java}"


@requires_oracle
def test_line_appearance_op_sequence_exact() -> None:
    """The Line ``/AP /N`` op-sequence + ``/BBox`` match Apache PDFBox exactly:
    line body + leader lines, caption text run, Diamond start ending and
    ClosedArrow end ending all drawn in the same order."""
    java = _java_records()["Line"]
    ln = _build_line()
    ln.construct_appearances()
    stream = ln.get_normal_appearance_stream()
    assert stream is not None, "Line produced no /AP /N"
    assert _bbox_line(stream) == java["bbox"], (
        f"Line bbox {_bbox_line(stream)!r} != PDFBox {java['bbox']!r}"
    )
    py_ops = _operators(stream)
    assert py_ops == java["ops"], (
        f"Line op-sequence diverges\n pypdfbox: {py_ops}\n PDFBox:   {java['ops']}"
    )


@requires_oracle
def test_line_ending_shapes_present() -> None:
    """The Diamond (start) and ClosedArrow (end) shapes are filled/stroked
    paths in the Line appearance: a ``B`` (fill+stroke) closes each shape, and
    the interior colour is set (``rg``) before them."""
    ln = _build_line()
    ln.construct_appearances()
    py_ops = _operators(ln.get_normal_appearance_stream())
    # Two closed shapes (diamond + closed arrow) each end in ``h B``.
    assert py_ops.count("B") >= 2, py_ops
    assert py_ops.count("h") >= 2, py_ops
    # /IC interior colour is applied before the endings.
    assert "rg" in py_ops, py_ops


@requires_oracle
def test_free_text_appearance_skeleton_matches() -> None:
    """The FreeText ``/AP /N`` ``/BBox`` matches exactly and the structural
    op-skeleton (callout polyline + OpenArrow ending + border box + /Rotate cm
    + clip + BT..ET text) matches Apache PDFBox.

    Only the *number* of ``Td Tj`` runs inside the text object differs
    (documented PlainTextFormatter word-wrap divergence)."""
    java = _java_records()["FreeText"]
    ft = _build_free_text()
    ft.construct_appearances()
    stream = ft.get_normal_appearance_stream()
    assert stream is not None, "FreeText produced no /AP /N"
    assert _bbox_line(stream) == java["bbox"], (
        f"FreeText bbox {_bbox_line(stream)!r} != PDFBox {java['bbox']!r}"
    )
    py_ops = _operators(stream)
    jr_ops = list(java["ops"])  # type: ignore[arg-type]

    # Callout polyline: 3-point /CL drawn as ``m l l`` then stroked.
    assert "m" in py_ops and py_ops.count("l") >= 2 and "S" in py_ops, py_ops

    # OpenArrow line-ending drawn inside a ``q ... Q`` block with its own
    # ``cm`` transform — present on both sides.
    assert "q" in py_ops and "Q" in py_ops, py_ops
    assert "cm" in py_ops and "cm" in jr_ops, (py_ops, jr_ops)

    # Border box (``re B``), clip (``re W n``) and the text object skeleton.
    for op in ("re", "B", "W", "n", "BT", "Tf", "rg", "Td", "Tj", "ET"):
        assert op in py_ops, f"FreeText missing {op!r} in {py_ops}"
        assert op in jr_ops, f"PDFBox missing {op!r} in {jr_ops}"

    # The ``cm`` rotate is now emitted unconditionally (the fix). Confirm the
    # border box draw is followed by a ``cm`` then the clip — the upstream
    # order — by checking ``B`` precedes a ``cm`` which precedes ``W``.
    b_idx = py_ops.index("B")
    assert "cm" in py_ops[b_idx:], py_ops
    cm_after_b = b_idx + py_ops[b_idx:].index("cm")
    assert "W" in py_ops[cm_after_b:], py_ops


@requires_oracle
def test_free_text_quadding_not_ignored() -> None:
    """``/Q 1`` survives round-trip on the FreeText annotation (it is not
    dropped during appearance construction)."""
    ft = _build_free_text()
    ft.construct_appearances()
    assert ft.get_q() == 1
    java = _java_records()["FreeText"]["acc"]
    assert java["Q"] == "1"


@requires_oracle
def test_generated_pdf_is_qpdf_valid() -> None:
    """The pypdfbox-built FreeText+Line document passes ``qpdf --check``
    (skipped when qpdf is unavailable)."""
    import shutil

    if shutil.which("qpdf") is None:
        import pytest

        pytest.skip("qpdf not installed")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "ftl_py.pdf"
        _build_doc(out)
        result = subprocess.run(
            ["qpdf", "--check", str(out)],
            capture_output=True,
            text=True,
            check=False,
        )
    # qpdf returns 0 (clean) or 3 (warnings only); 2 = errors.
    assert result.returncode in (0, 3), (
        f"qpdf --check failed (rc={result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )
