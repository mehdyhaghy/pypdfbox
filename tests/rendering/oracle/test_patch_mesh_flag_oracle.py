"""Live PDFBox differential parity for Type 6 (Coons) / Type 7 (tensor)
patch-mesh shadings that use **flag-driven edge sharing** (flags 1/2/3),
compared **per RGB channel**.

Companion to ``test_mesh_shading_oracle.py``. That module pins Types 4-7 via a
16x16 *luminance* grid, but every patch it builds carries flag 0 — a single
free patch with all 12 / 16 control points and all 4 corner colours read fresh
from the stream. The flag-continuation topology (PDF 32000-1 §8.7.4.5.7-8: a
flag 1/2/3 patch inherits 4 boundary control points and 2 corner colours from
the previous patch's shared edge) is never exercised. A luminance grid also
collapses RGB into one channel, so an R<->B swap in the patch's bilinear
colour interpolation would slip through. This module closes both gaps:

* The fixture is a **two-patch mesh**: an initial flag-0 patch covering the
  bottom half of the page, followed by a **flag-2** patch covering the top
  half whose leading 4 control points and first 2 corner colours are the
  previous patch's top edge (``points[6..9]`` / ``colors[2], colors[3]``).
  Decoding it correctly requires the flag != 0 carry-over path in
  ``parse_patch_stream`` (implicit edge + implicit corner colour). A decoder
  that ignores the carry-over leaves the top patch's bottom edge unset (a
  hole, or a degenerate patch collapsed at the origin).

* The corners carry strongly chromatic, per-channel-distinct colours so the
  comparison discriminates colour, not just brightness. The two patches share
  the mid-page colours, so a correct decode yields a continuous vertical ramp.

* The fingerprint is the per-channel RGB grid emitted by
  ``oracle/probes/PatchMeshFlagProbe.java`` — three 16x16 grids (R, G, B),
  each compared by mean-absolute and worst-cell diff.

Both Type 6 and Type 7 are exercised (the tensor fixture adds the 4 interior
control points to each patch, which only the flag-0 patch supplies fresh; the
flag-2 patch supplies its own 4 interior points after the shared boundary).

Measured against PDFBox 3.0.7 the channels land within the patch-mesh gate
(``MAD < 8`` / ``MAXDIFF < 60``): pypdfbox approximates the patch colour field
with a Gouraud-shaded cell grid while PDFBox interpolates per pixel, leaving
the same small uniform offset documented for the flag-0 case in
``test_mesh_shading_oracle.py`` / ``CHANGES.md``. The guard test proves an
R<->B-swapped grid scores far outside tolerance, so the gate genuinely
discriminates correct per-channel colour from a swap.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Patch-mesh gate (cf. test_mesh_shading_oracle.py's MAD < 8 luminance gate):
# the whole-page render gate loosened to admit the per-pixel-vs-cell-grid
# interpolation offset. Per-channel (not luminance-averaged) the widest-range
# channel — red, high across the whole page in this red->magenta/yellow ramp —
# lands at MAD ~7.8, so the gate carries a touch more headroom than the
# luminance variant while staying far below the banding (12-17), blank (100+),
# and R<->B-swap (~55, see guard test) failure modes.
_MAD_TOLERANCE = 9.0
_MAXDIFF_TOLERANCE = 60
_PAGE = 100.0


def _decode_array() -> COSArray:
    """``/Decode``: x/y in ``[0, 100]``, three colour components in ``[0, 1]``."""
    arr = COSArray()
    for v in (0.0, 100.0, 0.0, 100.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0):
        arr.add(COSFloat(v))
    return arr


def _q(value: float, lo: float, hi: float, src_max: int = 255) -> int:
    """Quantise ``value`` from ``[lo, hi]`` into ``[0, src_max]`` (the inverse
    of the patch decoder's ``_interpolate``)."""
    if hi == lo:
        return 0
    raw = round((value - lo) / (hi - lo) * src_max)
    return max(0, min(src_max, raw))


def _xy(x: float, y: float) -> bytes:
    return bytes([_q(x, 0, 100), _q(y, 0, 100)])


def _col(r: float, g: float, b: float) -> bytes:
    return bytes([_q(r, 0, 1), _q(g, 0, 1), _q(b, 0, 1)])


def _base_shading(shading_type: int) -> COSStream:
    sh = COSStream()
    sh.set_int(COSName.get_pdf_name("ShadingType"), shading_type)
    sh.set_item(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB"))
    sh.set_int(COSName.get_pdf_name("BitsPerCoordinate"), 8)
    sh.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    sh.set_int(COSName.get_pdf_name("BitsPerFlag"), 8)
    sh.set_item(COSName.get_pdf_name("Decode"), _decode_array())
    return sh


def _new_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)
    return doc, page


def _save(doc: PDDocument, page: PDPage, shading: COSStream, out: Path) -> Path:
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Shading"), COSName.get_pdf_name("Sh0"), shading
    )
    contents = COSStream()
    contents.set_raw_data(b"/Sh0 sh\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    doc.save(str(out))
    doc.close()
    return out


# Corner colours used by both patches' shared mid-page edge and their outer
# edges. The vertical ramp runs red (bottom) -> blue (mid) on the left, and
# green (bottom) -> white (mid) on the right; the top patch continues from the
# mid colours up to magenta (top-left) / yellow (top-right).
_BOTTOM_C0 = (1.0, 0.0, 0.0)  # p0 bottom-left   = red
_BOTTOM_C1 = (0.0, 1.0, 0.0)  # p3 bottom-right  = green
_MID_C2 = (1.0, 1.0, 1.0)     # p6 mid-right     = white
_MID_C3 = (0.0, 0.0, 1.0)     # p9 mid-left      = blue
_TOP_C2 = (1.0, 1.0, 0.0)     # top patch p6 top-right = yellow
_TOP_C3 = (1.0, 0.0, 1.0)     # top patch p9 top-left  = magenta


def _bottom_patch_coords() -> list[tuple[float, float]]:
    """12 Coons control points for a straight-edged patch over y in [0, 50]:
    bottom edge L->R at y=0, right edge up to y=50, top edge R->L at y=50,
    left edge back down. (PDF 32000-1 §8.7.4.5.7 Fig. 39 ordering.)"""
    return [
        (0, 0), (33, 0), (66, 0), (100, 0),       # p0..p3 bottom L->R (y=0)
        (100, 17), (100, 33), (100, 50),          # p4..p6 right edge up
        (66, 50), (33, 50),                       # p7..p8 top edge R->L (y=50)
        (0, 50),                                  # p9 top-left
        (0, 33), (0, 17),                         # p10..p11 left edge down
    ]


def _top_patch_new_coords() -> list[tuple[float, float]]:
    """The 8 *new* control points the flag-2 top patch supplies after its
    leading 4 (the shared edge ``points[6..9]`` of the bottom patch, i.e.
    bottom patch top edge at y=50, R->L). In the new patch's own ordering the
    shared edge occupies p0..p3, so these are p4..p11 (right edge up to y=100,
    top edge R->L at y=100, left edge back down to y=50)."""
    return [
        (100, 67), (100, 83), (100, 100),         # p4..p6 right edge up
        (66, 100), (33, 100),                     # p7..p8 top edge R->L (y=100)
        (0, 100),                                 # p9 top-left
        (0, 83), (0, 67),                         # p10..p11 left edge down
    ]


def _build_type6(out: Path) -> Path:
    """Two-patch Coons mesh: flag-0 bottom patch + flag-2 top patch that
    shares the bottom patch's top edge and its two upper corner colours."""
    doc, page = _new_doc()
    sh = _base_shading(6)

    data = bytearray()
    # --- Patch 1 (flag 0): full 12 points + 4 corners. ---
    data.append(0)
    for x, y in _bottom_patch_coords():
        data += _xy(x, y)
    for rgb in (_BOTTOM_C0, _BOTTOM_C1, _MID_C2, _MID_C3):
        data += _col(*rgb)

    # --- Patch 2 (flag 2): shares bottom patch points[6..9] + colors[2,3];
    #     supplies 8 new points + 2 new corner colours. ---
    data.append(2)
    for x, y in _top_patch_new_coords():
        data += _xy(x, y)
    # Flag-2 new corners are the new patch's c2 (top-right) and c3 (top-left).
    for rgb in (_TOP_C2, _TOP_C3):
        data += _col(*rgb)

    sh.set_raw_data(bytes(data))
    return _save(doc, page, sh, out)


def _bottom_patch_interior() -> list[tuple[float, float]]:
    """4 interior control points for the bottom tensor patch (kept inside the
    patch so the surface stays planar)."""
    return [(33, 17), (66, 17), (66, 33), (33, 33)]


def _top_patch_interior() -> list[tuple[float, float]]:
    return [(33, 67), (66, 67), (66, 83), (33, 83)]


def _build_type7(out: Path) -> Path:
    """Two-patch tensor mesh: same geometry / colours as the Coons fixture,
    each patch carrying its 4 interior control points. The flag-2 patch
    still shares only the 4 boundary edge points + 2 corner colours; its
    interior points are supplied fresh."""
    doc, page = _new_doc()
    sh = _base_shading(7)

    data = bytearray()
    # --- Patch 1 (flag 0): 16 points (12 boundary + 4 interior) + 4 corners.
    data.append(0)
    for x, y in (*_bottom_patch_coords(), *_bottom_patch_interior()):
        data += _xy(x, y)
    for rgb in (_BOTTOM_C0, _BOTTOM_C1, _MID_C2, _MID_C3):
        data += _col(*rgb)

    # --- Patch 2 (flag 2): shares 4 boundary points + 2 colours; supplies
    #     8 new boundary points + 4 interior points + 2 corner colours. ---
    data.append(2)
    for x, y in (*_top_patch_new_coords(), *_top_patch_interior()):
        data += _xy(x, y)
    for rgb in (_TOP_C2, _TOP_C3):
        data += _col(*rgb)

    sh.set_raw_data(bytes(data))
    return _save(doc, page, sh, out)


_BUILDERS = {
    "type6_coons_flag2": _build_type6,
    "type7_tensor_flag2": _build_type7,
}


def _channel_grids(img: Image.Image) -> tuple[list[int], list[int], list[int]]:
    rgb = img.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    sums = [[0] * (_GRID * _GRID) for _ in range(3)]
    count = [0] * (_GRID * _GRID)
    for y in range(height):
        cy = min(_GRID - 1, y * _GRID // height)
        for x in range(width):
            cx = min(_GRID - 1, x * _GRID // width)
            idx = cy * _GRID + cx
            r, g, b = pixels[x, y]
            sums[0][idx] += r
            sums[1][idx] += g
            sums[2][idx] += b
            count[idx] += 1

    def grid(ch: list[int]) -> list[int]:
        return [
            round(ch[i] / count[i]) if count[i] else 255
            for i in range(_GRID * _GRID)
        ]

    return grid(sums[0]), grid(sums[1]), grid(sums[2])


def _oracle_signature(
    fixture: Path,
) -> tuple[tuple[int, int], tuple[list[int], list[int], list[int]]]:
    lines = run_probe_text("PatchMeshFlagProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    r = [int(v) for v in lines[1].split()]
    g = [int(v) for v in lines[2].split()]
    b = [int(v) for v in lines[3].split()]
    for ch in (r, g, b):
        assert len(ch) == _GRID * _GRID
    return (width, height), (r, g, b)


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_flag_shared_patch_mesh_matches_pdfbox(label: str, tmp_path: Path) -> None:
    fixture = _BUILDERS[label](tmp_path / f"{label}.pdf")
    (java_w, java_h), (jr, jg, jb) = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    pr, pg, pb = _channel_grids(img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    for name, java_ch, py_ch in (("R", jr, pr), ("G", jg, pg), ("B", jb, pb)):
        diffs = [abs(a - b) for a, b in zip(java_ch, py_ch, strict=True)]
        mad = sum(diffs) / len(diffs)
        maxdiff = max(diffs)
        assert mad < _MAD_TOLERANCE, (
            f"{label} channel {name}: mean abs cell diff {mad:.2f} >= "
            f"{_MAD_TOLERANCE} (maxdiff={maxdiff}) — flag-shared patch mesh "
            f"colour grossly divergent (hole / dropped carry-over / channel swap)"
        )
        assert maxdiff < _MAXDIFF_TOLERANCE, (
            f"{label} channel {name}: worst cell diff {maxdiff} >= "
            f"{_MAXDIFF_TOLERANCE} (mad={mad:.2f}) — a region diverges far "
            f"beyond inter-engine interpolation"
        )


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_channel_swap_would_fail_tolerance(label: str, tmp_path: Path) -> None:
    """Guard the gate: swapping the R and B channels of PDFBox's own render
    (the failure mode a luminance-only grid cannot see) scores far outside
    tolerance. Proves the per-channel gate discriminates correct colour from a
    channel swap in the patch's bilinear interpolation."""
    fixture = _BUILDERS[label](tmp_path / f"{label}.pdf")
    _dims, (jr, _jg, jb) = _oracle_signature(fixture)
    diffs = [abs(a - b) for a, b in zip(jr, jb, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        f"{label}: tolerance too loose — an R<->B channel swap passes the MAD "
        f"gate ({mad:.2f})"
    )


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_top_patch_not_a_hole_proof(label: str, tmp_path: Path) -> None:
    """Direct proof the flag-2 carry-over patch actually paints the top half:
    the top region's average colour must be far from white-background. A
    decoder that dropped the implicit-edge carry-over would collapse the top
    patch (degenerate / origin-anchored), leaving the top half blank white."""
    fixture = _BUILDERS[label](tmp_path / f"{label}.pdf")
    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    w, h = img.size
    px = img.load()
    # Sample the centre of the top half (the flag-2 patch region).
    cx, cy = w // 2, h // 4
    r, g, b = px[cx, cy]
    # The top patch ramps toward yellow/magenta — never near white-background.
    assert not (r > 240 and g > 240 and b > 240), (
        f"{label}: top-half centre {(r, g, b)} is background-white — the "
        f"flag-2 carry-over patch appears dropped (hole)"
    )
