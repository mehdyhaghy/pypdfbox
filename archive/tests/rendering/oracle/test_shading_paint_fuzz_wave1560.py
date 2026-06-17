"""Coarse-fact differential fuzz for the RENDER-TIME axial (type 2) / radial
(type 3) shading paint against Apache PDFBox 3.0.7 (wave 1560, agent A).

Where ``test_shading_domain_remap_wave1488.py`` and
``test_shading_background_degenerate_oracle.py`` pin a handful of hand-picked
pixel RGBs for the domain-remap / background / degenerate-cone quirks, this
module projects COARSE whole-page facts about the painted gradient so a wrong
gradient *direction*, a dropped ``/Extend`` region, or a degenerate shading that
should-or-should-not paint surfaces structurally — and exercises angles those
tests do not:

* a diagonal / vertical / anti-diagonal (non-axis-aligned) axial axis,
* asymmetric ``/Extend`` on the axial axis (``[true false]`` / ``[false true]``)
  with the painted-region bbox proving which side got clamped,
* an eccentric (offset-centre) nested radial gradient and an inner-bigger-than-
  outer radial,
* a type-3 stitching-function gradient (axial and radial),
* a ``/Domain`` subrange, and
* degenerate geometry: a zero-length axial axis and a zero-radius radial start.

Each fixture is a 100x100 page (1:1 device pixels at 72 DPI) with a single
``/Sh0 sh`` clipped to the page. The probe
``oracle/probes/ShadingPaintFuzzProbe.java`` renders the SAME bytes on the Java
side and emits, per case: render dims, the bounding box of the non-white painted
region, a coarse painted-pixel-count bucket (nearest 200), a distinct-colour
bucket (``1`` / ``few`` / ``many``), and the RGB at nine fixed sample points
(centre, mid-edges, corners).

Findings (live PDFBox 3.0.7 oracle, this wave): pypdfbox's lite renderer is at
full parity on every case — the only deltas are sub-step ramp-quantisation
rounding (truncating ``(int)(inputValue*factor)`` index vs the AGG raster) of at
most a few channel levels, and AA-fringe wobble of at most a pixel on the
painted bbox. No production divergence; nothing to fix. The comparisons are
therefore COARSE by design:

* ``dims`` and the non-white painted bbox are compared with a small pixel slop
  (``_BBOX_TOL``) — AA can shift the white/non-white boundary by a pixel.
* ``painted`` (count bucketed to 200) is compared exactly (all 25 cases agreed).
* ``colors`` only distinguishes a *flat* fill (``1``) from a real gradient
  (``>1``); ``few`` vs ``many`` is an AA-sensitive bucket boundary
  (``axial_dom_sub`` lands ``few`` in pypdfbox, ``many`` in Java) and is NOT a
  paint bug, so the two are treated as equivalent.
* the nine sample-point RGBs are compared within ``_CHANNEL_TOL``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.shading import PDShadingType2, PDShadingType3
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_PAGE = 100.0
# Sub-step ramp quantisation only (truncating index vs the AGG raster). A wrong
# extend / wrong direction would shift a channel by tens, far beyond this.
_CHANNEL_TOL = 6
# AA can move the white/non-white boundary by a pixel on each edge.
_BBOX_TOL = 2


# ---------------------------------------------------------------------------
# fixture builders
# ---------------------------------------------------------------------------


def _new_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)
    return doc, page


def _arr(*vals: float) -> COSArray:
    arr = COSArray()
    for v in vals:
        arr.add(COSFloat(v))
    return arr


def _exp_function(
    c0: list[float], c1: list[float], domain: tuple[float, float] = (0.0, 1.0)
) -> COSStream:
    fn = COSStream()
    fn.set_int(COSName.get_pdf_name("FunctionType"), 2)
    fn.set_item(COSName.get_pdf_name("Domain"), _arr(*domain))
    a0 = COSArray()
    for v in c0:
        a0.add(COSFloat(v))
    fn.set_item(COSName.get_pdf_name("C0"), a0)
    a1 = COSArray()
    for v in c1:
        a1.add(COSFloat(v))
    fn.set_item(COSName.get_pdf_name("C1"), a1)
    fn.set_int(COSName.get_pdf_name("N"), 1)
    return fn


def _stitch_function() -> COSStream:
    """Type-3 stitching: red->green over ``[0,0.5]``, green->blue over
    ``[0.5,1]`` — two equal sub-domains, identity ``/Encode``."""
    fn = COSStream()
    fn.set_int(COSName.get_pdf_name("FunctionType"), 3)
    fn.set_item(COSName.get_pdf_name("Domain"), _arr(0.0, 1.0))
    funcs = COSArray()
    funcs.add(_exp_function([1.0, 0.0, 0.0], [0.0, 1.0, 0.0]))
    funcs.add(_exp_function([0.0, 1.0, 0.0], [0.0, 0.0, 1.0]))
    fn.set_item(COSName.get_pdf_name("Functions"), funcs)
    fn.set_item(COSName.get_pdf_name("Bounds"), _arr(0.5))
    fn.set_item(COSName.get_pdf_name("Encode"), _arr(0.0, 1.0, 0.0, 1.0))
    return fn


def _save(
    doc: PDDocument,
    page: PDPage,
    shading: PDShadingType2 | PDShadingType3,
    out: Path,
) -> Path:
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Shading"),
        COSName.get_pdf_name("Sh0"),
        shading.get_cos_object(),
    )
    stream = COSStream()
    stream.set_raw_data(b"0 0 100 100 re W n /Sh0 sh\n")
    page.get_cos_object().set_item(COSName.CONTENTS, stream)
    doc.save(str(out))
    doc.close()
    return out


def _axial(
    coords: tuple[float, ...],
    fn: COSStream,
    extend: tuple[bool, bool],
    domain: tuple[float, float] | None = None,
):
    def build(out: Path) -> Path:
        doc, page = _new_doc()
        sh = PDShadingType2()
        sh.set_color_space(COSName.get_pdf_name("DeviceRGB"))
        sh.set_coords(_arr(*coords))
        sh.set_function(fn)
        sh.set_extend(*extend)
        if domain is not None:
            sh.set_domain(list(domain))
        return _save(doc, page, sh, out)

    return build


def _radial(
    coords: tuple[float, ...],
    fn: COSStream,
    extend: tuple[bool, bool],
    domain: tuple[float, float] | None = None,
):
    def build(out: Path) -> Path:
        doc, page = _new_doc()
        sh = PDShadingType3()
        sh.set_color_space(COSName.get_pdf_name("DeviceRGB"))
        sh.set_coords(_arr(*coords))
        sh.set_function(fn)
        sh.set_extend(*extend)
        if domain is not None:
            sh.set_domain(list(domain))
        return _save(doc, page, sh, out)

    return build


# ---------------------------------------------------------------------------
# cases — (builder, expected_facts) where expected_facts mirrors the probe's
# coarse projection of the live PDFBox 3.0.7 render. ``bbox`` is None when the
# page is unpainted; ``colors`` is "flat" (==1 distinct) or "gradient" (>1).
# ---------------------------------------------------------------------------


def _c(
    bbox: tuple[int, int, int, int] | None,
    painted: int,
    colors: str,
    points: list[tuple[int, int, int]],
) -> dict:
    return {"bbox": bbox, "painted": painted, "colors": colors, "points": points}


_CASES: dict[str, tuple] = {
    # ---- axial: direction / extend ----
    "axial_diag": (
        _axial((10.0, 10.0, 90.0, 90.0), _exp_function([1, 0, 0], [0, 0, 1]),
               (True, True)),
        _c((0, 0, 99, 99), 10000, "gradient",
           [(128, 0, 127), (56, 0, 199), (200, 0, 55), (200, 0, 55),
            (56, 0, 199), (128, 0, 127), (0, 0, 255), (255, 0, 0),
            (128, 0, 127)]),
    ),
    "axial_full": (
        _axial((0.0, 50.0, 100.0, 50.0), _exp_function([1, 0, 0], [0, 0, 1]),
               (True, True)),
        _c((0, 0, 99, 99), 10000, "gradient",
           [(128, 0, 127), (128, 0, 127), (128, 0, 127), (243, 0, 12),
            (13, 0, 242), (243, 0, 12), (13, 0, 242), (243, 0, 12),
            (13, 0, 242)]),
    ),
    "axial_vert": (
        _axial((50.0, 20.0, 50.0, 80.0), _exp_function([0, 1, 0], [1, 0, 1]),
               (True, True)),
        _c((0, 0, 99, 99), 10000, "gradient",
           [(127, 128, 127), (255, 0, 255), (0, 255, 0), (127, 128, 127),
            (127, 128, 127), (255, 0, 255), (255, 0, 255), (0, 255, 0),
            (0, 255, 0)]),
    ),
    "axial_antidiag": (
        _axial((90.0, 10.0, 10.0, 90.0), _exp_function([0, 0, 1], [1, 1, 0]),
               (True, True)),
        _c((0, 0, 99, 99), 10000, "gradient",
           [(127, 127, 128), (199, 199, 56), (55, 55, 200), (199, 199, 56),
            (55, 55, 200), (255, 255, 0), (127, 127, 128), (127, 127, 128),
            (0, 0, 255)]),
    ),
    "axial_ext_tf": (
        _axial((30.0, 0.0, 70.0, 0.0), _exp_function([1, 0, 0], [0, 0, 1]),
               (True, False)),
        # extend[0] only: left half (x<30) extends red, right half (x>70) blank.
        _c((0, 0, 70, 99), 7200, "gradient",
           [(128, 0, 127), (128, 0, 127), (128, 0, 127), (255, 0, 0),
            (255, 255, 255), (255, 0, 0), (255, 255, 255), (255, 0, 0),
            (255, 255, 255)]),
    ),
    "axial_ext_ft": (
        _axial((30.0, 0.0, 70.0, 0.0), _exp_function([1, 0, 0], [0, 0, 1]),
               (False, True)),
        # extend[1] only: right half (x>70) extends blue, left half blank.
        _c((30, 0, 99, 99), 7000, "gradient",
           [(128, 0, 127), (128, 0, 127), (128, 0, 127), (255, 255, 255),
            (0, 0, 255), (255, 255, 255), (0, 0, 255), (255, 255, 255),
            (0, 0, 255)]),
    ),
    "axial_ext_ff": (
        _axial((30.0, 0.0, 70.0, 0.0), _exp_function([1, 0, 0], [0, 0, 1]),
               (False, False)),
        # no extend: only the 30..70 band painted.
        _c((30, 0, 70, 99), 4200, "gradient",
           [(128, 0, 127), (128, 0, 127), (128, 0, 127), (255, 255, 255),
            (255, 255, 255), (255, 255, 255), (255, 255, 255), (255, 255, 255),
            (255, 255, 255)]),
    ),
    "axial_short_noext": (
        _axial((45.0, 50.0, 55.0, 50.0), _exp_function([1, 0, 0], [0, 1, 0]),
               (False, False)),
        _c((45, 0, 55, 99), 1200, "gradient",
           [(128, 127, 0), (128, 127, 0), (128, 127, 0), (255, 255, 255),
            (255, 255, 255), (255, 255, 255), (255, 255, 255), (255, 255, 255),
            (255, 255, 255)]),
    ),
    "axial_offpage": (
        _axial((-20.0, 50.0, 120.0, 50.0), _exp_function([1, 0, 0], [0, 0, 1]),
               (False, False)),
        # axis runs off both page edges: full page painted, no extend needed.
        _c((0, 0, 99, 99), 10000, "gradient",
           [(128, 0, 127), (128, 0, 127), (128, 0, 127), (210, 0, 45),
            (46, 0, 209), (210, 0, 45), (46, 0, 209), (210, 0, 45),
            (46, 0, 209)]),
    ),
    # ---- axial: domain ----
    "axial_dom_sub": (
        _axial((20.0, 50.0, 80.0, 50.0), _exp_function([1, 0, 0], [0, 0, 1]),
               (True, True), domain=(0.25, 0.75)),
        _c((0, 0, 99, 99), 10000, "gradient",
           [(128, 0, 127), (128, 0, 127), (128, 0, 127), (160, 0, 95),
            (96, 0, 159), (160, 0, 95), (96, 0, 159), (160, 0, 95),
            (96, 0, 159)]),
    ),
    "axial_dom_full2": (
        # function domain [0,2] but shading /Domain [0,1] — the function is
        # sampled over its own [0,2], remapped via the shading domain.
        _axial((20.0, 50.0, 80.0, 50.0),
               _exp_function([1, 0, 0], [0, 0, 1], (0.0, 2.0)),
               (True, True), domain=(0.0, 1.0)),
        _c((0, 0, 99, 99), 10000, "gradient",
           [(128, 0, 127), (128, 0, 127), (128, 0, 127), (255, 0, 0),
            (0, 0, 255), (255, 0, 0), (0, 0, 255), (255, 0, 0), (0, 0, 255)]),
    ),
    # ---- axial: stitching function ----
    "axial_stitch": (
        _axial((0.0, 50.0, 100.0, 50.0), _stitch_function(), (False, False)),
        _c((0, 0, 99, 99), 10000, "gradient",
           [(1, 254, 0), (1, 254, 0), (1, 254, 0), (231, 24, 0), (0, 26, 229),
            (231, 24, 0), (0, 26, 229), (231, 24, 0), (0, 26, 229)]),
    ),
    "axial_stitch_ext": (
        _axial((0.0, 50.0, 100.0, 50.0), _stitch_function(), (True, True)),
        _c((0, 0, 99, 99), 10000, "gradient",
           [(1, 254, 0), (1, 254, 0), (1, 254, 0), (231, 24, 0), (0, 26, 229),
            (231, 24, 0), (0, 26, 229), (231, 24, 0), (0, 26, 229)]),
    ),
    # ---- axial: degenerate (zero-length axis) ----
    "axial_zero": (
        # x0==x1, y0==y1: denom==0, no /Background -> nothing painted (matches
        # AxialShadingContext getRaster's denom==0 + bg==null continue branch).
        _axial((50.0, 50.0, 50.0, 50.0), _exp_function([1, 0, 0], [0, 0, 1]),
               (True, True)),
        _c(None, 0, "flat",
           [(255, 255, 255)] * 9),
    ),
    # ---- radial: concentric ----
    "radial_conc_ff": (
        _radial((50.0, 50.0, 5.0, 50.0, 50.0, 40.0),
                _exp_function([1, 0, 0], [0, 0, 1]), (False, False)),
        # only the annulus between r0=5 and r1=40 painted; corners/centre blank.
        _c((10, 10, 90, 90), 5000, "gradient",
           [(255, 255, 255), (255, 255, 255), (255, 255, 255), (255, 255, 255),
            (255, 255, 255), (255, 255, 255), (255, 255, 255), (255, 255, 255),
            (255, 255, 255)]),
    ),
    "radial_conc_tt": (
        _radial((50.0, 50.0, 5.0, 50.0, 50.0, 40.0),
                _exp_function([1, 0, 0], [0, 0, 1]), (True, True)),
        _c((0, 0, 99, 99), 10000, "gradient",
           [(255, 0, 0), (0, 0, 255), (0, 0, 255), (0, 0, 255), (0, 0, 255),
            (0, 0, 255), (0, 0, 255), (0, 0, 255), (0, 0, 255)]),
    ),
    "radial_conc_ext_tf": (
        _radial((50.0, 50.0, 10.0, 50.0, 50.0, 40.0),
                _exp_function([1, 1, 0], [1, 0, 0]), (True, False)),
        # extend[0] inward -> outside both circles the start (yellow) shows.
        _c((0, 0, 99, 99), 10000, "gradient",
           [(255, 255, 0), (255, 255, 0), (255, 255, 0), (255, 255, 0),
            (255, 255, 0), (255, 255, 0), (255, 255, 0), (255, 255, 0),
            (255, 255, 0)]),
    ),
    "radial_inner_big": (
        # r0=40 > r1=10: the start circle is the larger one.
        _radial((50.0, 50.0, 40.0, 50.0, 50.0, 10.0),
                _exp_function([0, 1, 1], [1, 0, 0]), (True, True)),
        _c((0, 0, 99, 99), 10000, "gradient",
           [(255, 0, 0), (255, 0, 0), (255, 0, 0), (255, 0, 0), (255, 0, 0),
            (255, 0, 0), (255, 0, 0), (255, 0, 0), (255, 0, 0)]),
    ),
    # ---- radial: eccentric (offset centres) ----
    "radial_ecc": (
        _radial((35.0, 50.0, 5.0, 55.0, 50.0, 40.0),
                _exp_function([1, 1, 0], [0, 0, 1]), (True, True)),
        _c((0, 0, 99, 99), 10000, "gradient",
           [(209, 209, 46), (0, 0, 255), (0, 0, 255), (0, 0, 255), (0, 0, 255),
            (0, 0, 255), (0, 0, 255), (0, 0, 255), (0, 0, 255)]),
    ),
    "radial_ecc_noext": (
        _radial((35.0, 50.0, 5.0, 55.0, 50.0, 40.0),
                _exp_function([1, 1, 0], [0, 0, 1]), (False, False)),
        _c((15, 10, 95, 90), 5000, "gradient",
           [(209, 209, 46), (255, 255, 255), (255, 255, 255), (255, 255, 255),
            (0, 0, 255), (255, 255, 255), (255, 255, 255), (255, 255, 255),
            (255, 255, 255)]),
    ),
    "radial_ecc_ft": (
        _radial((35.0, 50.0, 5.0, 55.0, 50.0, 40.0),
                _exp_function([1, 1, 0], [0, 0, 1]), (False, True)),
        _c((0, 0, 99, 99), 10000, "gradient",
           [(209, 209, 46), (0, 0, 255), (0, 0, 255), (0, 0, 255), (0, 0, 255),
            (0, 0, 255), (0, 0, 255), (0, 0, 255), (0, 0, 255)]),
    ),
    "radial_far_ecc": (
        _radial((20.0, 20.0, 5.0, 75.0, 75.0, 10.0),
                _exp_function([0, 1, 0], [1, 0, 1]), (True, True)),
        _c((0, 0, 99, 99), 2000, "gradient",
           [(166, 89, 166), (255, 255, 255), (255, 255, 255), (255, 255, 255),
            (255, 255, 255), (255, 255, 255), (255, 0, 255), (0, 255, 0),
            (255, 255, 255)]),
    ),
    # ---- radial: stitching function ----
    "radial_stitch": (
        _radial((50.0, 50.0, 5.0, 50.0, 50.0, 45.0), _stitch_function(),
                (True, True)),
        _c((0, 0, 99, 99), 10000, "gradient",
           [(255, 0, 0), (0, 0, 255), (0, 0, 255), (0, 0, 255), (0, 0, 255),
            (0, 0, 255), (0, 0, 255), (0, 0, 255), (0, 0, 255)]),
    ),
    # ---- radial: degenerate / tiny ----
    "radial_zero": (
        # r0==0: the start "circle" is a point; the cone fills out to r1=40.
        _radial((50.0, 50.0, 0.0, 50.0, 50.0, 40.0),
                _exp_function([1, 0, 0], [0, 0, 1]), (False, False)),
        _c((10, 10, 90, 90), 5000, "gradient",
           [(255, 0, 0), (255, 255, 255), (255, 255, 255), (255, 255, 255),
            (255, 255, 255), (255, 255, 255), (255, 255, 255), (255, 255, 255),
            (255, 255, 255)]),
    ),
    "radial_tiny": (
        _radial((50.0, 50.0, 2.0, 50.0, 50.0, 8.0),
                _exp_function([1, 0, 0], [0, 1, 0]), (False, False)),
        _c((42, 42, 58, 58), 200, "gradient",
           [(255, 255, 255), (255, 255, 255), (255, 255, 255), (255, 255, 255),
            (255, 255, 255), (255, 255, 255), (255, 255, 255), (255, 255, 255),
            (255, 255, 255)]),
    ),
}

_POINTS = [
    (50, 50), (50, 5), (50, 95), (5, 50), (95, 50),
    (5, 5), (95, 5), (5, 95), (95, 95),
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _py_facts(fixture: Path) -> dict:
    """Project the same coarse facts the Java probe emits, from pypdfbox."""
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    w, h = img.size
    px = img.load()
    min_x, min_y, max_x, max_y = w, h, -1, -1
    painted = 0
    distinct: set[int] = set()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if not (r >= 250 and g >= 250 and b >= 250):
                painted += 1
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
                distinct.add(((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4))
    bbox = None if max_x < 0 else (min_x, min_y, max_x, max_y)
    painted_bucket = ((painted + 100) // 200) * 200
    colors = "flat" if len(distinct) <= 1 else "gradient"
    points = [px[x, y] for (x, y) in _POINTS]
    return {
        "dims": (w, h),
        "bbox": bbox,
        "painted": painted_bucket,
        "colors": colors,
        "points": points,
    }


def _java_facts(dir_path: Path, names: list[str]) -> dict[str, dict]:
    """Run the probe over all fixtures in ``dir_path`` (one render per case) and
    parse the coarse-fact lines into a name->facts mapping."""
    (dir_path / "manifest.txt").write_text("\n".join(names) + "\n", encoding="utf-8")
    text = run_probe_text("ShadingPaintFuzzProbe", str(dir_path))
    out: dict[str, dict] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("CASE "):
            continue
        toks = line.split()
        name = toks[1]
        facts: dict = {}
        for tok in toks[2:]:
            key, _, val = tok.partition("=")
            if key == "dims":
                w, h = (int(v) for v in val.split("x"))
                facts["dims"] = (w, h)
            elif key == "bbox":
                facts["bbox"] = None if val == "none" else tuple(
                    int(v) for v in val.split(",")
                )
            elif key == "painted":
                facts["painted"] = int(val)
            elif key == "colors":
                facts["colors"] = "flat" if val == "1" else "gradient"
            elif key == "p":
                facts["points"] = [
                    tuple(int(c) for c in trip.split(","))
                    for trip in val.split(";")
                ]
        out[name] = facts
    return out


def _bbox_close(a, b) -> bool:
    if a is None or b is None:
        return a == b
    return all(abs(x - y) <= _BBOX_TOL for x, y in zip(a, b, strict=True))


# ---------------------------------------------------------------------------
# oracle-free regression pins
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_pypdfbox_paint_facts(label: str, tmp_path: Path) -> None:
    """pypdfbox renders the pinned coarse facts for each shading. Guards the
    gradient direction, the extend region, the painted bbox, and the
    flat-vs-gradient distinction without needing the live oracle."""
    builder, expected = _CASES[label]
    fixture = builder(tmp_path / f"{label}.pdf")
    got = _py_facts(fixture)
    assert got["dims"] == (100, 100), f"{label}: render dims {got['dims']}"
    assert _bbox_close(got["bbox"], expected["bbox"]), (
        f"{label}: bbox {got['bbox']} != ~{expected['bbox']}"
    )
    assert got["painted"] == expected["painted"], (
        f"{label}: painted bucket {got['painted']} != {expected['painted']}"
    )
    assert got["colors"] == expected["colors"], (
        f"{label}: colors {got['colors']} != {expected['colors']}"
    )
    for (x, y), exp_rgb, act_rgb in zip(_POINTS, expected["points"], got["points"],
                                        strict=True):
        diff = max(abs(a - b) for a, b in zip(exp_rgb, act_rgb, strict=True))
        assert diff <= _CHANNEL_TOL, (
            f"{label}: point ({x},{y}) = {act_rgb}, expected ~{exp_rgb} "
            f"(diff {diff} > {_CHANNEL_TOL})"
        )


# ---------------------------------------------------------------------------
# live differential — render the same bytes on both engines, compare coarse
# facts. ``few`` vs ``many`` distinct-colour bucketing is AA-sensitive and is
# folded into "gradient"; bbox is compared with a 2px AA slop.
# ---------------------------------------------------------------------------


@requires_oracle
def test_paint_facts_match_pdfbox(tmp_path: Path) -> None:
    """Every case's coarse render facts match Apache PDFBox 3.0.7. A wrong
    gradient direction, a dropped extend region, or a degenerate shading that
    paints when it should not (or vice-versa) would diverge the bbox / painted
    bucket / sample RGBs far beyond the AA tolerances."""
    names = list(_CASES)
    for label in names:
        builder, _expected = _CASES[label]
        builder(tmp_path / f"{label}.pdf")
    java = _java_facts(tmp_path, names)
    assert set(java) == set(names), f"probe missed cases: {set(names) - set(java)}"
    for label in names:
        jf = java[label]
        pf = _py_facts(tmp_path / f"{label}.pdf")
        assert jf["dims"] == pf["dims"], (
            f"{label}: dims java={jf['dims']} pypdfbox={pf['dims']}"
        )
        assert _bbox_close(jf["bbox"], pf["bbox"]), (
            f"{label}: bbox java={jf['bbox']} pypdfbox={pf['bbox']}"
        )
        assert jf["painted"] == pf["painted"], (
            f"{label}: painted java={jf['painted']} pypdfbox={pf['painted']}"
        )
        assert jf["colors"] == pf["colors"], (
            f"{label}: colors java={jf['colors']} pypdfbox={pf['colors']}"
        )
        for (x, y), jc, pc in zip(_POINTS, jf["points"], pf["points"],
                                  strict=True):
            diff = max(abs(a - b) for a, b in zip(jc, pc, strict=True))
            assert diff <= _CHANNEL_TOL, (
                f"{label}: point ({x},{y}) java={jc} pypdfbox={pc} "
                f"diff {diff} > {_CHANNEL_TOL}"
            )


@requires_oracle
def test_extend_region_discriminates(tmp_path: Path) -> None:
    """Guard the gate's discriminating power: the axial ``[true false]`` and
    ``[false true]`` fixtures paint *opposite* halves in both engines, proving
    the bbox / sample facts would catch a swapped or dropped extend side."""
    tf = _axial((30.0, 0.0, 70.0, 0.0), _exp_function([1, 0, 0], [0, 0, 1]),
                (True, False))(tmp_path / "tf.pdf")
    ft = _axial((30.0, 0.0, 70.0, 0.0), _exp_function([1, 0, 0], [0, 0, 1]),
                (False, True))(tmp_path / "ft.pdf")
    java = _java_facts(tmp_path, ["tf", "ft"])
    # left edge painted in tf (extend[0]), white in ft; mirror for right edge.
    assert java["tf"]["points"][3] != java["tf"]["points"][4], "tf both edges same"
    assert _py_facts(tf)["bbox"][0] <= 2, "pypdfbox tf left edge not extended"
    assert _py_facts(ft)["bbox"][2] >= 97, "pypdfbox ft right edge not extended"
    # and Java agrees on which side is the painted one.
    assert java["tf"]["bbox"][2] <= 72, "java tf right edge unexpectedly painted"
    assert java["ft"]["bbox"][0] >= 28, "java ft left edge unexpectedly painted"
