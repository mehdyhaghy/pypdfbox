"""Live PDFBox differential parity for image-XObject extraction.

Two layers of comparison against Apache PDFBox's own accessors
(``oracle/probes/ImageExtractProbe.java``):

* **Exact-match metadata** — ``getWidth()``, ``getHeight()``,
  ``getBitsPerComponent()``, and the resolved ``getColorSpace().getName()``
  for every ``PDImageXObject`` reachable from each page's
  ``PDResources.getXObjectNames()``. A mismatch is a real bug.
* **Tolerance-comparable raster fingerprint** — the decoded image
  (``getImage()``) downsampled to a 16x16 average Rec.601 luminance grid
  (0..255), row-major, with the same cell mapping as
  ``oracle/probes/RenderProbe.java``. Pixel-exact parity across Java2D's
  sample model and Pillow is impossible (rounding in colour-space
  conversion, sub-pixel codec behaviour), so we compare by mean-absolute
  cell difference (MAD) and worst single-cell difference (MAXDIFF).

Tolerance rationale (measured against PDFBox 3.0.7 over the fixtures below):
these are *direct sample decodes* — no rasterisation, no anti-aliasing — so
divergence is confined to per-channel rounding. Measured: Indexed
MAD=0.000/MAXDIFF=0, DeviceRGB MAD=0.008/MAXDIFF=1, ICCBased MAD=0.043/
MAXDIFF=1. We gate at ``MAD < 2.0`` and ``MAXDIFF < 8`` — comfortably above
the rounding ceiling yet far below any gross-failure floor (a blank/wrong
decode of these fixtures measures MAD in the tens to >100). The looser-than-
rounding margin documents that small codec/colour-conversion differences are
*expected* while still failing a structurally wrong decode.

Fixtures cover three distinct colour spaces: Indexed (palette), DeviceRGB
(direct), and ICCBased (profile-tagged, treated as its N-component device
alternate).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"

_GRID = 16
# Tolerances — see module docstring for the measured rationale.
_MAD_TOLERANCE = 2.0
_MAXDIFF_TOLERANCE = 8

# (relative fixture path, page index, xobject name, expected colour space,
#  human label)
_CASES = [
    ("multipdf/PDFBOX-5811-362972.pdf", 0, "Im0", "Indexed", "indexed_palette"),
    ("pdfwriter/unencrypted.pdf", 1, "Im0", "DeviceRGB", "device_rgb"),
    ("text/input/eu-001.pdf", 0, "Im1", "ICCBased", "icc_based"),
]


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint of ``img`` — same cell mapping as
    ``ImageExtractProbe.grid`` / ``RenderProbe.java`` (integer-division of
    pixel coordinate over image size, clamped to the last cell)."""
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


def _oracle_record(
    fixture: Path, page: int, name: str
) -> tuple[int, int, int, str, list[int]]:
    """Run the Java oracle and parse the line for the requested image."""
    out = run_probe_text("ImageExtractProbe", str(fixture))
    needle = f" page {page} name {name} "
    matches = [ln for ln in out.splitlines() if needle in ln]
    assert matches, f"oracle emitted no image record for page {page} name {name}"
    toks = matches[0].split()

    def _after(key: str) -> str:
        return toks[toks.index(key) + 1]

    width = int(_after("w"))
    height = int(_after("h"))
    bpc = int(_after("bpc"))
    cs = _after("cs")
    gidx = toks.index("grid")
    grid = [int(v) for v in toks[gidx + 1 :]]
    assert len(grid) == _GRID * _GRID
    return width, height, bpc, cs, grid


@requires_oracle
@pytest.mark.parametrize(
    ("rel_path", "page", "name", "expected_cs", "label"),
    _CASES,
    ids=[c[4] for c in _CASES],
)
def test_image_extract_matches_pdfbox(
    rel_path: str, page: int, name: str, expected_cs: str, label: str
) -> None:
    fixture = _FIXTURES / rel_path
    j_w, j_h, j_bpc, j_cs, j_grid = _oracle_record(fixture, page, name)

    doc = PDDocument.load(fixture)
    try:
        xobject = doc.get_page(page).get_resources().get_x_object(
            COSName.get_pdf_name(name)
        )
        assert isinstance(xobject, PDImageXObject), (
            f"{label}: resource {name} is not a PDImageXObject"
        )
        color_space = xobject.get_color_space()
        py_cs = color_space.get_name() if color_space is not None else "null"
        py_w = xobject.get_width()
        py_h = xobject.get_height()
        py_bpc = xobject.get_bits_per_component()
        image = xobject.get_image()
        assert image is not None, f"{label}: pypdfbox failed to decode the image"
        py_grid = _grid_from_image(image)
    finally:
        doc.close()

    # (a) Exact-match metadata — a mismatch is a real bug.
    assert (py_w, py_h, py_bpc, py_cs) == (j_w, j_h, j_bpc, j_cs), (
        f"{label}: image metadata diverges from PDFBox: "
        f"pypdfbox=({py_w}x{py_h} bpc={py_bpc} cs={py_cs}) "
        f"java=({j_w}x{j_h} bpc={j_bpc} cs={j_cs})"
    )
    # Sanity-check the fixture really is the colour space we think.
    assert py_cs == expected_cs, (
        f"{label}: fixture colour space changed to {py_cs} (expected {expected_cs})"
    )

    # (b) Raster fingerprint within tolerance (expected codec/rounding diff).
    diffs = [abs(a - b) for a, b in zip(j_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.3f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — grossly divergent decode, not just rounding"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.3f}) — a region diverges far beyond codec rounding"
    )


@requires_oracle
def test_blank_decode_would_fail_tolerance() -> None:
    """Guard the threshold: a blank-white raster is far outside tolerance for
    a fixture PDFBox decodes with content. Confirms the gate discriminates
    correct decodes from gross failures rather than passing everything."""
    fixture = _FIXTURES / "pdfwriter/unencrypted.pdf"
    _w, _h, _bpc, _cs, j_grid = _oracle_record(fixture, 1, "Im0")
    blank = [255] * (_GRID * _GRID)
    diffs = [abs(a - b) for a, b in zip(j_grid, blank, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: a blank decode passes the MAD gate"
    )
