"""Pixel-exact parity for axial/radial shading ``/Background``, asymmetric
``/Extend``, and degenerate-geometry rendering against Apache PDFBox 3.0.7.

Companion to ``test_shading_extend_oracle.py`` (whole-page 16x16 luminance grid
for the basic extend/domain/cone cases). This module samples **specific
pixels' RGB** — via ``oracle/probes/ShadingPixelProbe.java`` — to pin colour
detail the grayscale grid cannot see:

* **axial / radial ``/Background``** — a pixel *outside* the gradient extent
  with ``/Extend`` false must be painted the ``/Background`` colour, not left
  white, when the clip is larger than the gradient (PDF 32000-1 §8.7.4.3;
  upstream ``AxialShadingContext`` / ``RadialShadingContext`` paint
  ``getRgbBackground()`` there). Before this was fixed pypdfbox painted white.
* **radial cylinder ``r0 == r1``** — equal-radius circles with offset centres;
  the quadratic-root selection must pick the correct in-range root (the prior
  "larger root with non-negative radius" heuristic chose the wrong colour past
  the end circle).
* **radial degenerate cone ``denom == 0``** (``|c1-c0| == |r1-r0|``) — the
  apex-at-infinity case where Java float division yields ±Inf / NaN roots; the
  selected colour (``(int)(NaN*factor) == 0`` → the start colour) must match.
* **radial asymmetric ``/Extend [true false]``** — a point outside both nested
  circles is filled with the *start* colour (extend[0] extends inward), not
  left white.

Each fixture is a 100x100 page (1:1 with device pixels at 72 DPI) filled with
one ``/Sh0 sh`` clipped to the full page. The oracle-free tests pin the
pypdfbox RGB at the chosen sample points (so the parity is a regression guard
even on a machine without the live oracle). The ``@requires_oracle`` tests
assert the same pixels match PDFBox within a tight per-channel tolerance
(sub-byte rounding only — these are flat / near-flat sample points by design).
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
# Per-channel tolerance for the live differential. These are flat / near-flat
# sample points, so anything above a couple of bytes is a real divergence
# (wrong background / wrong extend / wrong root), not anti-aliasing.
_CHANNEL_TOL = 4


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


def _coords(*vals: float) -> COSArray:
    arr = COSArray()
    for v in vals:
        arr.add(COSFloat(v))
    return arr


def _exp_function(c0: list[float], c1: list[float]) -> COSStream:
    fn = COSStream()
    fn.set_int(COSName.get_pdf_name("FunctionType"), 2)
    fn.set_item(COSName.get_pdf_name("Domain"), _coords(0.0, 1.0))
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


def _set_background(sh: PDShadingType2 | PDShadingType3, rgb: list[float]) -> None:
    arr = COSArray()
    for v in rgb:
        arr.add(COSFloat(v))
    sh.get_cos_object().set_item(COSName.get_pdf_name("Background"), arr)


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


def _build_axial_background(out: Path) -> Path:
    """Short horizontal axis (x 30..70), ``/Extend [false false]``,
    ``/Background`` mid-gray. Beyond the axis (x<30 / x>70) — inside the
    full-page clip — must be painted gray, not white."""
    doc, page = _new_doc()
    sh = PDShadingType2()
    sh.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    sh.set_coords(_coords(30.0, 0.0, 70.0, 0.0))
    sh.set_function(_exp_function([0.0, 0.0, 1.0], [1.0, 1.0, 0.0]))
    sh.set_extend(False, False)
    _set_background(sh, [0.5, 0.5, 0.5])
    return _save(doc, page, sh, out)


def _build_radial_background(out: Path) -> Path:
    """Small concentric circles (r0=5 -> r1=25), ``/Extend [false false]``,
    ``/Background`` orange. Pixels outside the largest circle must be orange."""
    doc, page = _new_doc()
    sh = PDShadingType3()
    sh.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    sh.set_coords(_coords(50.0, 50.0, 5.0, 50.0, 50.0, 25.0))
    sh.set_domain([0.0, 1.0])
    sh.set_function(_exp_function([0.0, 1.0, 0.0], [0.0, 0.0, 1.0]))
    sh.set_extend(False, False)
    _set_background(sh, [1.0, 0.5, 0.0])
    return _save(doc, page, sh, out)


def _build_radial_cylinder(out: Path) -> Path:
    """Equal-radius circles (r0 == r1 == 15) with offset centres (x 30..70),
    ``/Extend [true true]``. Yellow -> red."""
    doc, page = _new_doc()
    sh = PDShadingType3()
    sh.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    sh.set_coords(_coords(30.0, 50.0, 15.0, 70.0, 50.0, 15.0))
    sh.set_domain([0.0, 1.0])
    sh.set_function(_exp_function([1.0, 1.0, 0.0], [1.0, 0.0, 0.0]))
    sh.set_extend(True, True)
    return _save(doc, page, sh, out)


def _build_radial_degenerate_cone(out: Path) -> Path:
    """Degenerate cone ``|c1-c0| == |r1-r0|`` (denom == 0): c0=(35,50) r0=5,
    c1=(60,50) r1=30 -> |dc|=25, |dr|=25. ``/Extend [true true]`` fills the
    whole clip with the start colour (the Java ``(int)(NaN*factor)==0`` case).
    Yellow start -> blue end."""
    doc, page = _new_doc()
    sh = PDShadingType3()
    sh.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    sh.set_coords(_coords(35.0, 50.0, 5.0, 60.0, 50.0, 30.0))
    sh.set_domain([0.0, 1.0])
    sh.set_function(_exp_function([1.0, 1.0, 0.0], [0.0, 0.0, 1.0]))
    sh.set_extend(True, True)
    return _save(doc, page, sh, out)


def _build_radial_same_circle(out: Path) -> Path:
    """Coincident circles (c0 == c1, r0 == r1 == 30), ``/Extend [true true]``.
    Both quadratic roots are 0/0 == NaN, so upstream's both-NaN early-out
    skips EVERY pixel (inside the circle too) — nothing is painted, the
    extend ladder is never consulted (RadialShadingContext.getRaster L188).
    Wave-1484 regression pin: a blanket NaN->start-colour mapping painted
    the clip red here. Red -> red."""
    doc, page = _new_doc()
    sh = PDShadingType3()
    sh.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    sh.set_coords(_coords(50.0, 50.0, 30.0, 50.0, 50.0, 30.0))
    sh.set_domain([0.0, 1.0])
    sh.set_function(_exp_function([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]))
    sh.set_extend(True, True)
    return _save(doc, page, sh, out)


def _build_radial_extend_tf(out: Path) -> Path:
    """Nested circles (r0=10 inside r1=40), ``/Extend [true false]``. A corner
    pixel outside both circles is filled with the *start* colour (extend[0]
    extends inward), not left white. Yellow start -> red end."""
    doc, page = _new_doc()
    sh = PDShadingType3()
    sh.set_color_space(COSName.get_pdf_name("DeviceRGB"))
    sh.set_coords(_coords(50.0, 50.0, 10.0, 50.0, 50.0, 40.0))
    sh.set_domain([0.0, 1.0])
    sh.set_function(_exp_function([1.0, 1.0, 0.0], [1.0, 0.0, 0.0]))
    sh.set_extend(True, False)
    return _save(doc, page, sh, out)


# (builder, [(x, y, (r, g, b)) expected pypdfbox RGB at that device pixel])
_CASES: dict[str, tuple] = {
    "axial_background": (
        _build_axial_background,
        # left & right of the axis -> /Background gray; mid -> gradient mid.
        [(10, 50, (128, 128, 128)), (90, 50, (128, 128, 128)),
         (50, 50, (128, 128, 127))],
    ),
    "radial_background": (
        _build_radial_background,
        # centre is *inside* the start circle (r0=5) with extend false ->
        # /Background orange; a mid-band pixel -> gradient blend; far corner
        # outside the end circle -> /Background orange.
        [(50, 50, (255, 128, 0)), (50, 40, (0, 191, 64)),
         (95, 5, (255, 128, 0))],
    ),
    "radial_cylinder": (
        _build_radial_cylinder,
        # the previously-wrong sample at the right edge of the band.
        [(30, 50, (255, 159, 0)), (50, 50, (255, 32, 0)),
         (70, 50, (255, 96, 0))],
    ),
    "radial_degenerate_cone": (
        _build_radial_degenerate_cone,
        # the whole clip resolves to the start colour (yellow).
        [(50, 50, (255, 255, 0)), (10, 50, (255, 255, 0)),
         (50, 10, (255, 255, 0))],
    ),
    "radial_same_circle": (
        _build_radial_same_circle,
        # nothing painted anywhere: centre, in-band, and outside all white.
        [(50, 50, (255, 255, 255)), (30, 50, (255, 255, 255)),
         (90, 50, (255, 255, 255))],
    ),
    "radial_extend_tf": (
        _build_radial_extend_tf,
        # centre -> start; far corner outside both circles -> start (extend[0]).
        [(50, 50, (255, 255, 0)), (5, 5, (255, 255, 0)),
         (95, 95, (255, 255, 0))],
    ),
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _py_pixels(
    fixture: Path, pts: list[tuple[int, int]]
) -> tuple[tuple[int, int], list[tuple[int, int, int]]]:
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    px = img.load()
    return img.size, [px[x, y] for (x, y) in pts]


def _java_pixels(
    fixture: Path, pts: list[tuple[int, int]]
) -> tuple[tuple[int, int], list[tuple[int, int, int]]]:
    args = [str(fixture), "0"]
    for x, y in pts:
        args += [str(x), str(y)]
    lines = run_probe_text("ShadingPixelProbe", *args).splitlines()
    w, h = (int(v) for v in lines[0].split())
    out: list[tuple[int, int, int]] = []
    for ln in lines[1:]:
        r, g, b = (int(v) for v in ln.split())
        out.append((r, g, b))
    return (w, h), out


# ---------------------------------------------------------------------------
# oracle-free regression pins
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_pypdfbox_pixel_pins(label: str, tmp_path: Path) -> None:
    """pypdfbox renders the pinned RGB at each sample point. Catches a
    regression in the /Background fill, the radial root selection, or the
    degenerate-cone IEEE-division handling without needing the live oracle."""
    builder, samples = _CASES[label]
    fixture = builder(tmp_path / f"{label}.pdf")
    pts = [(x, y) for (x, y, _rgb) in samples]
    (w, h), got = _py_pixels(fixture, pts)
    assert (w, h) == (100, 100), f"{label}: unexpected render size {w}x{h}"
    for (x, y, expected), actual in zip(samples, got, strict=True):
        diff = max(abs(a - b) for a, b in zip(expected, actual, strict=True))
        assert diff <= 2, (
            f"{label}: pixel ({x},{y}) = {actual}, expected ~{expected} "
            f"(per-channel diff {diff} > 2)"
        )


# ---------------------------------------------------------------------------
# live differential
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_CASES), ids=list(_CASES))
def test_pixel_rgb_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Each sampled pixel's RGB matches Apache PDFBox within sub-byte
    rounding. A wrong /Background, a wrong extend flag, or a wrong radial root
    would shift the channel by tens of levels — far beyond the tolerance."""
    builder, samples = _CASES[label]
    fixture = builder(tmp_path / f"{label}.pdf")
    pts = [(x, y) for (x, y, _rgb) in samples]
    (jw, jh), java = _java_pixels(fixture, pts)
    (pw, ph), py = _py_pixels(fixture, pts)
    assert (pw, ph) == (jw, jh), (
        f"{label}: render dims diverge pypdfbox={pw}x{ph} java={jw}x{jh}"
    )
    for (x, y, _exp), jc, pc in zip(samples, java, py, strict=True):
        diff = max(abs(a - b) for a, b in zip(jc, pc, strict=True))
        assert diff <= _CHANNEL_TOL, (
            f"{label}: pixel ({x},{y}) java={jc} pypdfbox={pc} "
            f"per-channel diff {diff} > {_CHANNEL_TOL}"
        )


@requires_oracle
def test_background_differs_from_white(tmp_path: Path) -> None:
    """Guard: the axial ``/Background`` fixture's out-of-extent region renders
    as the (non-white) background colour in *both* engines — proving the gate
    discriminates a background fill from a dropped (white) one."""
    fixture = _build_axial_background(tmp_path / "axial_bg.pdf")
    pts = [(10, 50)]
    (_jw, _jh), java = _java_pixels(fixture, pts)
    (_pw, _ph), py = _py_pixels(fixture, pts)
    # PDFBox paints ~mid-gray (127); white would be 255.
    assert java[0][0] < 200, "oracle background sample unexpectedly white"
    assert py[0][0] < 200, "pypdfbox dropped the /Background fill (white)"
