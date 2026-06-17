"""Live PDFBox differential parity for ``PDTilingPattern`` ACCESSORS.

Companion to the rendering-side ``tests/rendering/oracle/test_pattern_*`` files
(which pin the rasterised tiling output). This file pins the *typed accessor
surface* of a tiling pattern (``/PatternType 1``) as parsed back off a saved
PDF: ``get_pattern_type`` / ``get_paint_type`` / ``get_tiling_type`` /
``get_b_box`` / ``get_x_step`` / ``get_y_step`` / ``get_matrix`` — exactly the
values Apache PDFBox's ``PDTilingPattern`` reports through the same accessors.

``oracle/probes/TilingPatternProbe.java`` walks each page's ``/Resources``
``/Pattern`` subdictionary, keeps the ``PDTilingPattern`` entries, and emits one
canonical block per pattern (sorted by resource name). pypdfbox reproduces the
identical block from its own accessors over the same reloaded fixture; the two
strings must be byte-for-byte equal.

Two fixtures exercise the surface from different angles:

* **offset_steps_matrix** — a ``/BBox`` with a non-zero lower-left origin,
  ``/XStep`` != ``/YStep`` (both larger than the cell, so cells are spaced
  apart), a non-identity ``/Matrix`` (anisotropic scale + translate), PaintType
  1, TilingType 2. Catches any off-by-one in BBox corner reads, a swapped
  X/Y step, or a transposed / mis-flattened matrix.
* **defaults** — a freshly built pattern that sets only PaintType/BBox/steps
  and leaves ``/Matrix`` and ``/TilingType`` absent, pinning the spec defaults
  (identity matrix, TilingType 0) against PDFBox's own defaulting.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.pattern import PDTilingPattern
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text


def _canon_float(value: float) -> str:
    """Mirror the probe's ``canonFloat``: round half-even to 3 decimals,
    strip trailing zeros / dot, normalise ``-0`` to ``0``."""
    from decimal import ROUND_HALF_EVEN, Decimal  # noqa: PLC0415

    quant = Decimal(repr(float(value))).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_EVEN
    )
    quant = quant.normalize()
    s = format(quant, "f")
    if s in {"-0", ""}:
        s = "0"
    return s


def _py_block(name: str, p: PDTilingPattern) -> str:
    bbox = p.get_b_box()
    if bbox is None:
        bbox_str = "none"
    else:
        bbox_str = ",".join(
            _canon_float(v)
            for v in (
                bbox.get_lower_left_x(),
                bbox.get_lower_left_y(),
                bbox.get_upper_right_x(),
                bbox.get_upper_right_y(),
            )
        )
    matrix_str = ",".join(_canon_float(v) for v in p.get_matrix())
    return (
        f"PATTERN {name}\n"
        f"PATTERNTYPE {p.get_pattern_type()}\n"
        f"PAINTTYPE {p.get_paint_type()}\n"
        f"TILINGTYPE {p.get_tiling_type()}\n"
        f"BBOX {bbox_str}\n"
        f"XSTEP {_canon_float(p.get_x_step())}\n"
        f"YSTEP {_canon_float(p.get_y_step())}\n"
        f"MATRIX {matrix_str}\n"
        "END\n"
    )


def _py_listing(fixture: Path) -> str:
    blocks: list[str] = []
    with PDDocument.load(fixture) as doc:
        for page in doc.get_pages():
            res = page.get_resources()
            if res is None:
                continue
            for name in res.get_pattern_names():
                pattern = res.get_pattern(name)
                if isinstance(pattern, PDTilingPattern):
                    blocks.append(_py_block(name.get_name(), pattern))
    blocks.sort()
    return "".join(blocks)


def _save(page: PDPage, pattern: PDTilingPattern, doc: PDDocument, out: Path) -> Path:
    res = PDResources()
    page.set_resources(res)
    res.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        pattern.get_cos_object(),
    )
    stream = COSStream()
    stream.set_raw_data(b"/Pattern cs /P0 scn 10 10 100 100 re f\n")
    page.get_cos_object().set_item(COSName.CONTENTS, stream)
    doc.save(str(out))
    doc.close()
    return out


def _new_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 120.0, 120.0))
    doc.add_page(page)
    return doc, page


def _build_offset_steps_matrix(out: Path) -> Path:
    doc, page = _new_doc()
    pattern = PDTilingPattern()
    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_COLORED)
    pattern.set_tiling_type(PDTilingPattern.TILING_TYPE_NO_DISTORTION)
    pattern.set_b_box(PDRectangle(2.0, 3.0, 42.0, 53.0))
    pattern.set_x_step(45.0)
    pattern.set_y_step(55.0)
    pattern.set_matrix([1.5, 0.0, 0.0, 2.0, 12.0, 8.0])
    pattern.get_cos_object().set_raw_data(b"1 0 0 rg 6 6 28 28 re f\n")
    return _save(page, pattern, doc, out)


def _build_defaults(out: Path) -> Path:
    doc, page = _new_doc()
    pattern = PDTilingPattern()
    pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_UNCOLORED)
    pattern.set_b_box(PDRectangle(0.0, 0.0, 30.0, 30.0))
    pattern.set_x_step(30.0)
    pattern.set_y_step(30.0)
    # No /Matrix, no /TilingType — pin the spec defaults.
    pattern.clear_matrix()
    pattern.get_cos_object().set_raw_data(b"6 6 18 18 re f\n")
    return _save(page, pattern, doc, out)


_BUILDERS = {
    "offset_steps_matrix": _build_offset_steps_matrix,
    "defaults": _build_defaults,
}


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_tiling_pattern_accessors_match_pdfbox(
    label: str, tmp_path: Path
) -> None:
    fixture = _BUILDERS[label](tmp_path / f"{label}.pdf")
    java = run_probe_text("TilingPatternProbe", str(fixture))
    py = _py_listing(fixture)
    assert py == java, (
        f"{label}: PDTilingPattern accessor surface diverges from PDFBox\n"
        f"--- java ---\n{java}\n--- pypdfbox ---\n{py}"
    )


def test_canon_float_mirrors_probe() -> None:
    """Guard the local ``_canon_float`` reproduces the probe's number
    canonicalisation for the values these fixtures exercise."""
    assert _canon_float(45.0) == "45"
    assert _canon_float(1.5) == "1.5"
    assert _canon_float(0.0) == "0"
    assert _canon_float(-0.0) == "0"
    assert _canon_float(2.0) == "2"
