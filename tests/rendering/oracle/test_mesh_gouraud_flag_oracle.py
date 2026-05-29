"""Live PDFBox differential parity for Type 4 free-form Gouraud meshes that
use **flag-1 / flag-2 vertex continuation** (triangle strip / fan), compared
**per RGB channel**.

Companion to ``test_mesh_shading_oracle.py``. That module pins Types 4-7 via a
16x16 *luminance* grid, but every triangle it builds carries flag 0 (three
fresh vertices each) — the continuation topology (PDF 32000-1 §8.7.4.5.5:
flag 1 reuses the previous triangle's (vb, vc) edge, flag 2 reuses its
(va, vc) edge) is never exercised. A luminance grid also collapses RGB into
one channel, so an R<->B colour swap in the Gouraud interpolation would slip
through. This module closes both gaps:

* The fixture is one ``/Sh0 sh`` Type 4 mesh whose triangles are emitted as a
  *strip*: an initial flag-0 triangle followed by flag-1 / flag-2 vertices
  that re-use prior corners. Decoding the strip correctly requires the
  flag-continuation path in ``PDShadingType4.collect_triangles``.
* The corners carry strongly chromatic, per-channel-distinct colours (red /
  green / blue / yellow) so the comparison discriminates colour, not just
  brightness.
* The fingerprint is the per-channel RGB grid emitted by
  ``oracle/probes/MeshGouraudFlagProbe.java`` — three 16x16 grids (R, G, B),
  each compared by mean-absolute and worst-cell diff.

Measured against PDFBox 3.0.7 the channels land at MAD ~1 / MAXDIFF ~3: both
engines do plain per-vertex Gouraud interpolation over the same decoded strip.
The guard test proves an R<->B-swapped grid scores MAD far outside tolerance,
so the gate genuinely discriminates correct per-channel colour from a swap.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Per-channel Gouraud parity: both engines interpolate per vertex identically;
# the residual is anti-aliasing at the shared triangle edges.
_MAD_TOLERANCE = 6.0
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
    of the mesh decoder's ``_interpolate``)."""
    if hi == lo:
        return 0
    raw = round((value - lo) / (hi - lo) * src_max)
    return max(0, min(src_max, raw))


def _vtx(flag: int, x: float, y: float, r: float, g: float, b: float) -> bytes:
    return bytes(
        [flag, _q(x, 0, 100), _q(y, 0, 100), _q(r, 0, 1), _q(g, 0, 1), _q(b, 0, 1)]
    )


def _build_flag_strip(out: Path) -> Path:
    """Free-form Gouraud mesh emitted as a flag-continuation strip covering
    the page. The four page corners carry red / green / blue / yellow:

        (0,0)   red     (100,0)   green
        (0,100) blue    (100,100) yellow

    Triangle 1 (flag 0): (0,0)R (100,0)G (0,100)B.
    Triangle 2 (flag 2): re-use (va=(0,0)R, vc=(0,100)B) + new (100,100)Y.
        => after flag 2 the assembled triangle is (0,0)R (0,100)B (100,100)Y.
    Triangle 3 (flag 1): re-use the last edge (vb,vc)=((0,100)B,(100,100)Y)
        + new (100,0)G => (0,100)B (100,100)Y (100,0)G.

    The three triangles tile the unit square via shared edges, so decoding the
    flags wrong (or ignoring them) leaves a hole or a mis-coloured wedge.
    """
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)

    sh = COSStream()
    sh.set_int(COSName.get_pdf_name("ShadingType"), 4)
    sh.set_item(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB"))
    sh.set_int(COSName.get_pdf_name("BitsPerCoordinate"), 8)
    sh.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    sh.set_int(COSName.get_pdf_name("BitsPerFlag"), 8)
    sh.set_item(COSName.get_pdf_name("Decode"), _decode_array())

    data = b""
    # Triangle 1 (flag 0): three fresh vertices.
    data += _vtx(0, 0, 0, 1, 0, 0)  # red
    data += _vtx(0, 100, 0, 0, 1, 0)  # green
    data += _vtx(0, 0, 100, 0, 0, 1)  # blue
    # Triangle 2 (flag 2): re-use (va, vc) = red, blue; add yellow.
    data += _vtx(2, 100, 100, 1, 1, 0)  # yellow
    # Triangle 3 (flag 1): re-use last edge (vb, vc) = blue, yellow; add green.
    data += _vtx(1, 100, 0, 0, 1, 0)  # green
    sh.set_raw_data(data)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(COSName.get_pdf_name("Shading"), COSName.get_pdf_name("Sh0"), sh)
    contents = COSStream()
    contents.set_raw_data(b"/Sh0 sh\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    doc.save(str(out))
    doc.close()
    return out


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
    lines = run_probe_text("MeshGouraudFlagProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    r = [int(v) for v in lines[1].split()]
    g = [int(v) for v in lines[2].split()]
    b = [int(v) for v in lines[3].split()]
    for ch in (r, g, b):
        assert len(ch) == _GRID * _GRID
    return (width, height), (r, g, b)


@requires_oracle
def test_flag_continuation_mesh_matches_pdfbox(tmp_path: Path) -> None:
    fixture = _build_flag_strip(tmp_path / "flag_strip.pdf")
    (java_w, java_h), (jr, jg, jb) = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    pr, pg, pb = _channel_grids(img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"rendered dimensions diverge: pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    for name, java_ch, py_ch in (("R", jr, pr), ("G", jg, pg), ("B", jb, pb)):
        diffs = [abs(a - b) for a, b in zip(java_ch, py_ch, strict=True)]
        mad = sum(diffs) / len(diffs)
        maxdiff = max(diffs)
        assert mad < _MAD_TOLERANCE, (
            f"channel {name}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
            f"(maxdiff={maxdiff}) — flag-continuation mesh colour grossly "
            f"divergent (hole / wrong topology / channel swap)"
        )
        assert maxdiff < _MAXDIFF_TOLERANCE, (
            f"channel {name}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
            f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
        )


@requires_oracle
def test_channel_swap_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: swapping the R and B channels of PDFBox's own render
    (the failure mode a luminance-only grid cannot see) scores far outside
    tolerance. Proves the per-channel gate discriminates correct colour from a
    channel swap."""
    fixture = _build_flag_strip(tmp_path / "flag_strip.pdf")
    _dims, (jr, jg, jb) = _oracle_signature(fixture)
    # Compare the real R grid against the swapped-in B grid.
    diffs = [abs(a - b) for a, b in zip(jr, jb, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        f"tolerance too loose — an R<->B channel swap passes the MAD gate "
        f"({mad:.2f})"
    )
