"""Live Apache PDFBox differential parity for the STRIKEOUT and SQUIGGLY
text-markup appearance handlers — colour-set operator, line geometry, render.

Surface under test:
``pypdfbox.pdmodel.interactive.annotation.PDAnnotationStrikeout`` /
``PDAnnotationSquiggly`` appearance generation via
``PDStrikeoutAppearanceHandler`` / ``PDSquigglyAppearanceHandler``.

This drills DEEPER than ``test_text_markup_oracle.py`` (wave 1442/1455), which
fingerprints only the operator KEYWORD sequence and normalises the colour-set
operator away as a documented "RG vs CS SC" spelling divergence. Two facts that
test cannot see:

1. **Colour-set operator parity.** Upstream passes the typed ``PDColor`` to
   ``setStrokingColor``, emitting ``/DeviceRGB CS r g b SC`` (colour-space
   select + components + ``SC``), NOT the device-shorthand ``RG``. The Caret
   handler was already converted to the typed-PDColor form (wave 1466); this
   file pins the same fix for StrikeOut and Squiggly so the colour bytes match
   Apache PDFBox exactly rather than being normalised over.
2. **StrikeOut line midline.** Upstream draws the strikeout line through the
   vertical MIDDLE of each quad, with each endpoint pulled in by the
   ``len/2 - width`` Adobe trick (``PDStrikeoutAppearanceHandler.java``). The
   keyword-only fingerprint never checks the line's actual y. Here the probe
   recovers the constant y of the stroked segment and asserts it matches
   PDFBox to the canonical float.

The Java probe ``StrikeoutSquigglyProbe`` runs in two modes:

* ``write out.pdf`` — one StrikeOut + one Squiggly over a horizontal 200pt band,
  each with a ``/Rect``, a ``/QuadPoints`` quad and a ``/C`` RGB colour, then
  ``constructAppearances(doc)`` + save. PDFBox-AUTHORED reference.
* ``read out.pdf`` — re-opens ANY StrikeOut/Squiggly PDF and emits, per
  annotation: ``ANNOT`` / ``BBOX`` / ``COLOROP`` / ``COLORCS`` / ``STROKEY`` /
  ``OPS`` / ``END``.

Squiggly tiling pattern (wave 1499 — now at full parity)
--------------------------------------------------------
Upstream paints the zig-zag via an uncolored tiling pattern wrapped in a form
XObject (``CS SC cm Do`` outer stream). Wave 1499 ported that construction
faithfully (``PDFormContentStream`` / ``PDPatternContentStream`` +
``PDAppearanceContentStream.draw_form``), so the outer appearance operator
sequence and ``/BBox`` are byte-equivalent to Apache PDFBox; the render gate
below confirms the painted result.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationSquiggly,
    PDAnnotationStrikeout,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "StrikeoutSquigglyProbe"
_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

# Identical battery on the Java (StrikeoutSquigglyProbe.write) and Python sides.
# (subtype-label, cls, rect, quad, color)
_CASES = [
    (
        "StrikeOut",
        PDAnnotationStrikeout,
        (50, 195, 250, 220),
        [50, 215, 250, 215, 50, 200, 250, 200],
        [0.0, 0.0, 1.0],
    ),
    (
        "Squiggly",
        PDAnnotationSquiggly,
        (50, 145, 250, 170),
        [50, 165, 250, 165, 50, 150, 250, 150],
        [0.0, 0.5, 0.0],
    ),
]


def _build_pypdfbox(path: Path) -> None:
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0, 0, 300, 400))
        doc.add_page(page)
        annotations = []
        for _label, cls, rect, quad, color in _CASES:
            ann = cls()
            ann.set_rectangle(PDRectangle(*rect))
            ann.set_quad_points(quad)
            ann.set_color(color)
            ann.construct_appearances(doc)
            annotations.append(ann)
        page.set_annotations(annotations)
        doc.save(str(path))
    finally:
        doc.close()


def _parse_records(text: str) -> dict[str, dict[str, str]]:
    records: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        if raw.startswith("ANNOT "):
            current = {"subtype": raw[len("ANNOT ") :]}
        elif raw.startswith("BBOX "):
            assert current is not None
            current["bbox"] = raw[len("BBOX ") :]
        elif raw == "NOAP":
            assert current is not None
            current["bbox"] = "NOAP"
        elif raw.startswith("COLOROP "):
            assert current is not None
            current["colorop"] = raw[len("COLOROP ") :]
        elif raw.startswith("COLORCS "):
            assert current is not None
            current["colorcs"] = raw[len("COLORCS ") :]
        elif raw.startswith("STROKEY "):
            assert current is not None
            current["strokey"] = raw[len("STROKEY ") :]
        elif raw.startswith("OPS "):
            assert current is not None
            current["ops"] = raw[len("OPS ") :]
        elif raw == "END":
            assert current is not None
            records[current["subtype"]] = current
            current = None
    return records


# --- render fingerprint (identical cell mapping to RenderProbe.java) ---------


def _grid_from_image(img: Image.Image) -> list[int]:
    gray = img.convert("L")
    width, height = gray.size
    pixels = gray.load()
    total = [0] * (_GRID * _GRID)
    count = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(_GRID - 1, y * _GRID // height)
        for x in range(width):
            cx = min(_GRID - 1, x * _GRID // width)
            idx = cy * _GRID + cx
            total[idx] += pixels[x, y]
            count[idx] += 1
    return [
        round(total[i] / count[i]) if count[i] else 255 for i in range(_GRID * _GRID)
    ]


def _render_grid_java(path: Path) -> tuple[tuple[int, int], list[int]]:
    lines = run_probe_text("RenderProbe", str(path), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _render_grid_py(path: Path) -> tuple[tuple[int, int], list[int]]:
    with PDDocument.load(path) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    return img.size, _grid_from_image(img)


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


@requires_oracle
def test_strikeout_appearance_matches_pdfbox(tmp_path: Path) -> None:
    """StrikeOut generates the BYTE-level-equivalent ``/AP /N``: the typed
    DeviceRGB colour (``/DeviceRGB CS r g b SC``, not the shorthand ``RG``), the
    same ``w m l S`` line-drawing sequence, the same ``/BBox``, and the stroked
    line at the same constant y (the quad's vertical midline) as Apache
    PDFBox."""
    py_pdf = tmp_path / "ss_py.pdf"
    java_pdf = tmp_path / "ss_java.pdf"
    _build_pypdfbox(py_pdf)
    run_probe_text(_PROBE, "write", str(java_pdf))

    py = _parse_records(run_probe_text(_PROBE, "read", str(py_pdf)))["StrikeOut"]
    java = _parse_records(run_probe_text(_PROBE, "read", str(java_pdf)))["StrikeOut"]

    assert py["bbox"] != "NOAP", "pypdfbox produced no StrikeOut /AP /N"
    assert py["bbox"] == java["bbox"], f"bbox {py['bbox']!r} != {java['bbox']!r}"

    # Colour-set operator: typed DeviceRGB CS SC, matching upstream exactly.
    assert java["colorop"] == "CS" and java["colorcs"] == "DeviceRGB", (
        f"PDFBox StrikeOut colour {java['colorop']}/{java['colorcs']}"
    )
    assert py["colorop"] == "CS", (
        f"pypdfbox StrikeOut colour op {py['colorop']!r} != 'CS' — must emit the "
        "typed-PDColor /DeviceRGB CS ... SC form, not the device shorthand RG"
    )
    assert py["colorcs"] == "DeviceRGB", (
        f"pypdfbox StrikeOut colour space {py['colorcs']!r} != 'DeviceRGB'"
    )

    # Full operator sequence is identical now that the colour op matches.
    assert py["ops"] == java["ops"], (
        f"StrikeOut operator sequence {py['ops']!r} != PDFBox {java['ops']!r}"
    )

    # Strike line at the quad's vertical midline (Adobe len/2-width endpoints).
    assert java["strokey"] != "none", f"PDFBox StrikeOut not horizontal: {java}"
    assert py["strokey"] == java["strokey"], (
        f"StrikeOut line y {py['strokey']!r} != PDFBox {java['strokey']!r} — the "
        "line must cross the vertical middle of the quad"
    )


@requires_oracle
def test_squiggly_appearance_matches_pdfbox(tmp_path: Path) -> None:
    """Squiggly emits the typed DeviceRGB colour (``/DeviceRGB CS r g b SC``) and
    the same ``/BBox`` as Apache PDFBox. The zig-zag itself is the documented
    lite divergence: upstream paints it from a tiling pattern in a form XObject
    (``cm Do`` after the colour ops); the lite handler strokes a multi-segment
    polyline inline (``w m l ... l S``)."""
    py_pdf = tmp_path / "ss_py.pdf"
    java_pdf = tmp_path / "ss_java.pdf"
    _build_pypdfbox(py_pdf)
    run_probe_text(_PROBE, "write", str(java_pdf))

    py = _parse_records(run_probe_text(_PROBE, "read", str(py_pdf)))["Squiggly"]
    java = _parse_records(run_probe_text(_PROBE, "read", str(java_pdf)))["Squiggly"]

    assert py["bbox"] != "NOAP", "pypdfbox produced no Squiggly /AP /N"
    assert py["bbox"] == java["bbox"], f"bbox {py['bbox']!r} != {java['bbox']!r}"

    # Colour-set operator parity (the part the lite surface CAN match exactly).
    assert java["colorop"] == "CS" and java["colorcs"] == "DeviceRGB", (
        f"PDFBox Squiggly colour {java['colorop']}/{java['colorcs']}"
    )
    assert py["colorop"] == "CS", (
        f"pypdfbox Squiggly colour op {py['colorop']!r} != 'CS' — must emit the "
        "typed-PDColor /DeviceRGB CS ... SC form, not the device shorthand RG"
    )
    assert py["colorcs"] == "DeviceRGB", (
        f"pypdfbox Squiggly colour space {py['colorcs']!r} != 'DeviceRGB'"
    )

    # Wave 1499 ported the tiling-pattern construction faithfully: upstream and
    # pypdfbox both paint the zig-zag from an uncolored tiling pattern wrapped in
    # a form XObject. The outer appearance stream is byte-equivalent — colour set
    # via CS SC, then per quad a cm transform + Do draws the form XObject.
    py_ops = py["ops"].split()
    java_ops = java["ops"].split()
    assert py_ops[:2] == ["CS", "SC"], f"pypdfbox squiggly colour ops: {py_ops}"
    assert java_ops[:2] == ["CS", "SC"], f"PDFBox squiggly colour ops: {java_ops}"
    assert java_ops[-1] == "Do", f"PDFBox squiggly not a form XObject: {java_ops}"
    assert py_ops == java_ops, (
        f"Squiggly operator sequence {py_ops} != PDFBox {java_ops} — the "
        "zig-zag must be painted from a tiling pattern in a form XObject"
    )


@requires_oracle
def test_rendered_shapes_match_pdfbox(tmp_path: Path) -> None:
    """Rasterise both the PDFBox-authored and the pypdfbox-authored StrikeOut +
    Squiggly PDFs at 72 DPI and confirm the drawn shapes match within the
    render-oracle tolerance — the high-value proof the colour fix and the
    inline-zig-zag approximation are visually equivalent to PDFBox."""
    py_pdf = tmp_path / "ss_py.pdf"
    java_pdf = tmp_path / "ss_java.pdf"
    _build_pypdfbox(py_pdf)
    run_probe_text(_PROBE, "write", str(java_pdf))

    (jw, jh), java_grid = _render_grid_java(java_pdf)
    (pw, ph), py_grid = _render_grid_py(py_pdf)

    assert (pw, ph) == (jw, jh), (
        f"rendered dimensions diverge: pypdfbox={pw}x{ph} java={jw}x{jh}"
    )

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"strikeout/squiggly render mean abs cell diff {mad:.2f} >= "
        f"{_MAD_TOLERANCE} (maxdiff={maxdiff}) — a markup shape diverges"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"strikeout/squiggly render worst cell diff {maxdiff} >= "
        f"{_MAXDIFF_TOLERANCE} (mad={mad:.2f}) — a region diverges beyond AA"
    )
