"""Live PDFBox differential fuzz of RENDER-TIME tiling-pattern paint.

Companion to ``test_spaced_tiling_oracle.py`` (XStep/YStep > BBox gaps),
``test_uncolored_tiling_oracle.py`` (PaintType 2 tint routing) and
``test_pattern_fill_oracle.py`` (basic seamless fill). Prior waves fuzzed the
pattern *dictionary* accessors (wave 1541, ``TilingPatternDictionaryFuzzProbe``)
— this module fuzzes the **paint path** in
``PageDrawer._paint_tiling_pattern`` / ``_render_tiling_cell``: how a tiling
pattern is replicated across a filled region.

Both engines build the *same* small PDF from identical parameters and render it
at 72 DPI. The Java side is ``TilingPaintFuzzProbe``; pypdfbox builds the twin
fixture through its own API. Each side projects a COARSE fingerprint that is
robust to anti-aliasing and sub-pixel tile-phase differences:

* **exact page dimensions** — a mismatch is a real bug (scale / media-box).
* **painted-pixel bucket** ``round(painted / total * 100)`` — the percentage of
  the page that is not white background. Discriminates a fully painted region
  (seamless, ~44) from a gapped lattice (~11) from an unpainted region (0).
* **painted device bounding box** ``minX,minY,maxX,maxY`` — where the paint
  lands; a mis-placed lattice phase shows up as a shifted box.
* **four sampled colours** at fixed device points inside the fill region — the
  tile colour at known spots (red / blue / green / white-gap).

Comparison is coarse on purpose: the bucket is compared with a small tolerance
(AA on cell edges nudges a pixel or two), the bbox with a 1-pixel slack, and
each sampled colour by nearest primary (so a 254 vs 255 red still reads "red").
A real bug — region unpainted, wrong tile colour, or a grossly wrong lattice
density — is what trips this gate.

Measured against PDFBox 3.0.7 every case lands EXACTLY on the expected
fingerprint below (the cell geometry sits on integer device boundaries at 72
DPI), so the embedded ``_EXPECTED`` table both documents the oracle answer and
lets the test run self-contained when the live oracle is unavailable.

Real bug found + fixed this wave (pinned by the ``zero_xstep`` case):
``PageDrawer._paint_tiling_pattern`` returned early on a zero ``/XStep`` /
``/YStep``, leaving the fill region BLANK, while PDFBox's
``TilingPaint.getAnchorRect`` (PDFBOX-1094) logs a warning and falls back to the
/BBox width / height — so PDFBox paints the region. The Python paint path now
applies the same fallback; ``zero_xstep`` now matches PDFBox (bucket 44, all
samples red) instead of diverging (bucket 0, all white).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.pattern import PDTilingPattern
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import oracle_available, requires_oracle, run_probe_text

_PAGE = 120.0
_BBOX = 20.0

# Fixed device-space sample points — must mirror TilingPaintFuzzProbe.SAMPLES.
_SAMPLES = [(15, 105), (35, 85), (55, 65), (75, 45)]

# Coarse tolerances.
_BUCKET_SLACK = 3       # painted-% may drift a couple points from AA edges.
_BBOX_SLACK = 2         # painted bbox edges may move a pixel or two from AA.

# PDFBox-3.0.7-derived expected fingerprints (verified live this wave):
#   case -> (dims, (bucket, minx, miny, maxx, maxy), [(r,g,b) x4])
_EXPECTED: dict[str, tuple] = {
    "colored": ((120, 120), (44, 10, 10, 109, 109),
                [(255, 0, 0)] * 4),
    "colored_blue": ((120, 120), (44, 10, 10, 109, 109),
                     [(0, 0, 255)] * 4),
    "uncolored_red": ((120, 120), (44, 10, 10, 109, 109),
                      [(255, 0, 0)] * 4),
    "uncolored_blue": ((120, 120), (44, 10, 10, 109, 109),
                       [(0, 0, 255)] * 4),
    # XStep/YStep (40) > BBox (20): gapped lattice — far fewer painted pixels,
    # and two of the four sample points land in a transparent gap (white).
    "spaced": ((120, 120), (11, 10, 23, 97, 109),
               [(255, 0, 0), (255, 255, 255), (255, 0, 0), (255, 255, 255)]),
    "seamless": ((120, 120), (44, 10, 10, 109, 109),
                 [(255, 0, 0)] * 4),
    # /Matrix scales the pattern 2x: a bigger cell motif covers more of the
    # region, so the painted bucket rises (~49 vs 44).
    "matrix_scale": ((120, 120), (49, 10, 10, 109, 109),
                     [(255, 0, 0)] * 4),
    # /Matrix translates the lattice by (10,10): same density, shifted phase —
    # the painted bbox moves a couple pixels.
    "matrix_xlate": ((120, 120), (44, 12, 13, 107, 108),
                     [(255, 0, 0)] * 4),
    # Degenerate /XStep 0 — PDFBox falls back to /BBox width (PDFBOX-1094),
    # painting the region exactly like the seamless case. (Was a real bug:
    # pypdfbox left this region blank before this wave's fix.)
    "zero_xstep": ((120, 120), (44, 10, 10, 109, 109),
                   [(255, 0, 0)] * 4),
    "green_square": ((120, 120), (44, 10, 10, 109, 109),
                     [(0, 255, 0)] * 4),
}


# ---------------------------------------------------------------------------
# fixture builder — synthesise the twin PDF through the pypdfbox API
# ---------------------------------------------------------------------------


def _new_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)
    return doc, page


def _build(out: Path, which: str) -> Path:
    doc, page = _new_doc()
    pattern = PDTilingPattern()
    pattern.set_tiling_type(PDTilingPattern.TILING_TYPE_CONSTANT_SPACING)
    pattern.set_b_box(PDRectangle(0.0, 0.0, _BBOX, _BBOX))
    pattern.set_x_step(_BBOX)
    pattern.set_y_step(_BBOX)

    uncolored = which.startswith("uncolored")
    if uncolored:
        pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_UNCOLORED)
        motif = b"2 2 16 16 re f\n"
    else:
        pattern.set_paint_type(PDTilingPattern.PAINT_TYPE_COLORED)
        rg = b"1 0 0 rg"
        if which == "colored_blue":
            rg = b"0 0 1 rg"
        elif which == "green_square":
            rg = b"0 1 0 rg"
        motif = rg + b" 2 2 16 16 re f\n"

    if which == "spaced":
        pattern.set_x_step(40.0)
        pattern.set_y_step(40.0)
    if which == "zero_xstep":
        pattern.set_x_step(0.0)
    if which == "matrix_scale":
        pattern.set_matrix([2.0, 0.0, 0.0, 2.0, 0.0, 0.0])
    if which == "matrix_xlate":
        pattern.set_matrix([1.0, 0.0, 0.0, 1.0, 10.0, 10.0])

    pattern.get_cos_object().set_raw_data(motif)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Pattern"),
        COSName.get_pdf_name("P0"),
        pattern.get_cos_object(),
    )

    if uncolored:
        pattern_cs = COSArray()
        pattern_cs.add(COSName.get_pdf_name("Pattern"))
        pattern_cs.add(COSName.get_pdf_name("DeviceRGB"))
        cs_dict = COSDictionary()
        cs_dict.set_item(COSName.get_pdf_name("PCS"), pattern_cs)
        resources.get_cos_object().set_item(
            COSName.get_pdf_name("ColorSpace"), cs_dict
        )
        tint = b"0 0 1" if which == "uncolored_blue" else b"1 0 0"
        content = b"/PCS cs " + tint + b" /P0 scn 10 10 100 100 re f\n"
    else:
        content = b"/Pattern cs /P0 scn 10 10 100 100 re f\n"

    stream = COSStream()
    stream.set_raw_data(content)
    page.get_cos_object().set_item(COSName.CONTENTS, stream)
    doc.save(str(out))
    doc.close()
    return out


# ---------------------------------------------------------------------------
# fingerprint helpers — must mirror TilingPaintFuzzProbe.java exactly
# ---------------------------------------------------------------------------


def _facts(img: Image.Image) -> tuple[int, tuple[int, int, int, int], list]:
    rgb = img.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    painted = 0
    min_x = min_y = 10**9
    max_x = max_y = -1
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            if r < 240 or g < 240 or b < 240:
                painted += 1
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    bucket = round(100.0 * painted / (width * height))
    bbox = (-1, -1, -1, -1) if max_x < 0 else (min_x, min_y, max_x, max_y)
    samples = [pixels[min(width - 1, sx), min(height - 1, sy)]
               for sx, sy in _SAMPLES]
    return bucket, bbox, samples


def _pypdfbox_facts(fixture: Path) -> tuple:
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    bucket, bbox, samples = _facts(img)
    return img.size, (bucket, *bbox), samples


def _oracle_facts(case: str) -> tuple:
    lines = run_probe_text("TilingPaintFuzzProbe", case).splitlines()
    width, height = (int(v) for v in lines[0].split())
    bbox_vals = tuple(int(v) for v in lines[1].split())
    samples = [tuple(int(c) for c in tok.split(","))
               for tok in lines[2].split()]
    return (width, height), bbox_vals, samples


# ---------------------------------------------------------------------------
# coarse comparison
# ---------------------------------------------------------------------------


def _nearest_primary(rgb: tuple[int, int, int]) -> str:
    """Snap a sampled colour to a coarse label: the dominant primary, or
    'white' when it is the unpainted background."""
    r, g, b = rgb
    if r >= 200 and g >= 200 and b >= 200:
        return "white"
    if r >= 128 and g < 128 and b < 128:
        return "red"
    if g >= 128 and r < 128 and b < 128:
        return "green"
    if b >= 128 and r < 128 and g < 128:
        return "blue"
    return f"other({r},{g},{b})"


def _assert_coarse(case: str, dims, bbox_vals, samples, ref) -> None:
    ref_dims, ref_bbox, ref_samples = ref
    assert dims == ref_dims, (
        f"{case}: dims {dims} != {ref_dims} (scale / media-box bug)"
    )
    bucket = bbox_vals[0]
    ref_bucket = ref_bbox[0]
    assert abs(bucket - ref_bucket) <= _BUCKET_SLACK, (
        f"{case}: painted bucket {bucket} far from {ref_bucket} — region "
        f"un/over-painted, not just AA"
    )
    # Painted bbox: allow a small per-edge slack (skip the all-unpainted case
    # whose bbox is the (-1,-1,-1,-1) sentinel).
    if ref_bbox[1] != -1:
        for got, want, edge in zip(
            bbox_vals[1:], ref_bbox[1:], ("minx", "miny", "maxx", "maxy"),
            strict=True,
        ):
            assert abs(got - want) <= _BBOX_SLACK, (
                f"{case}: painted-bbox {edge} {got} far from {want} — "
                f"lattice phase mis-placed"
            )
    got_labels = [_nearest_primary(c) for c in samples]
    want_labels = [_nearest_primary(c) for c in ref_samples]
    assert got_labels == want_labels, (
        f"{case}: sampled tile colours {got_labels} != {want_labels} "
        f"(raw got={samples} want={ref_samples}) — wrong tile colour / gap"
    )


# ---------------------------------------------------------------------------
# self-contained tests (run everywhere, pinned to PDFBox-3.0.7 values)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", list(_EXPECTED), ids=list(_EXPECTED))
def test_tiling_paint_matches_pdfbox_values(case: str, tmp_path: Path) -> None:
    fixture = _build(tmp_path / f"{case}.pdf", case)
    dims, bbox_vals, samples = _pypdfbox_facts(fixture)
    _assert_coarse(case, dims, bbox_vals, samples, _EXPECTED[case])


# ---------------------------------------------------------------------------
# live differential (skips when the PDFBox oracle is unavailable)
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("case", list(_EXPECTED), ids=list(_EXPECTED))
def test_tiling_paint_matches_live_oracle(case: str, tmp_path: Path) -> None:
    fixture = _build(tmp_path / f"{case}.pdf", case)
    py_dims, py_bbox, py_samples = _pypdfbox_facts(fixture)
    java_dims, java_bbox, java_samples = _oracle_facts(case)
    # Pin BOTH sides coarsely against each other.
    _assert_coarse(
        case, py_dims, py_bbox, py_samples,
        (java_dims, java_bbox, java_samples),
    )


def test_oracle_table_self_consistent() -> None:
    """Guard: the embedded expected table is the live oracle's answer. When the
    oracle is present, regenerate it and confirm it still matches — so a future
    PDFBox bump that changes the paint can't silently rot the embedded values.
    """
    if not oracle_available():
        pytest.skip("live PDFBox oracle unavailable")
    for case, ref in _EXPECTED.items():
        java_dims, java_bbox, java_samples = _oracle_facts(case)
        _assert_coarse(
            case, java_dims, java_bbox, java_samples, ref
        )
