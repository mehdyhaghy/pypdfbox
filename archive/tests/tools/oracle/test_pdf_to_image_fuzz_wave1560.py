"""Live Apache PDFBox differential-fuzz parity for the ``PDFToImage`` /
render-to-image tool surface (wave 1560).

The existing ``test_pdf_to_image_oracle.py`` pins the per-page count + filename
indexing on a Letter fixture, and ``test_pdf_to_image_dpi_oracle.py`` pins the
float32 DPI-scale boundary on A4. This probe sweeps the tool's full option
matrix that a hand-written test cannot enumerate, pinning a STABLE shape per
combo against Apache PDFBox 3.0.7:

* ``-dpi`` 72 / 96(default) / 150 / 300  -> output width/height scale,
* ``-color`` RGB / ARGB / GRAY / BINARY  -> pixel format (AWT type + band count
  mapped to the Pillow mode pypdfbox returns),
* ``-startPage`` / ``-endPage`` in-range / out-of-range / ``start > end``
  -> output image count, and
* a ``/Rotate 90`` page -> swapped output orientation.

``PdfToImageToolFuzzProbe.java`` runs the tool's exact per-page render loop
(``renderImageWithDPI(i, dpi, type)`` over ``[startPage-1, min(endPage, pages))``)
and emits one ``case=`` block per combo with, per rendered page, the pixel
dimensions, the AWT ``BufferedImage`` type int, the raster band count, and a
coarse "ink" fingerprint (count of non-white cells in a 16x16 luminance grid).
pypdfbox runs the same loop through :class:`PDFRenderer` and rebuilds the block.

We compare dimensions + mode (AWT type/bands) + count + (coarse) ink, NOT exact
pixels — Java2D and Pillow anti-alias differently.

Honest divergences (coarse / mode-dependent), pinned with comments:

* **ARGB ink is not comparable.** Java's ``TYPE_INT_ARGB`` BufferedImage starts
  as transparent *black* ``(0,0,0,0)``; ``getRGB`` returns those RGB bits so an
  un-painted ARGB canvas reads luminance 0 -> ink=256 (every cell). pypdfbox's
  Pillow ``RGBA`` canvas starts transparent *white* ``(255,255,255,0)`` ->
  ink~=non-white painted cells only. Dimensions/type/bands still match; the ink
  bucket is skipped for ARGB.
* **ink is a coarse bucket** (count of cells below luminance 250), so AA jitter
  never flips it; we assert the bucket is within a small tolerance, not equal,
  except for the blank-page guard (ink > 0 where the oracle has ink > 0).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.image_type import ImageType
from pypdfbox.tools.pdf_to_image import PDFToImage
from tests.oracle.harness import requires_oracle, run_probe_text

PIL = pytest.importorskip("PIL.Image")

_GRID = 16
_WHITE_CUTOFF = 250
# Coarse ink-bucket tolerance: AA differences between Java2D and Pillow can
# flip a handful of borderline cells. We pin the bucket within this many cells.
_INK_TOLERANCE = 12

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
# 4-page Letter document (612x792 pt every page).
_MULTI = _FIXTURES / "pdmodel" / "page_tree_multiple_levels.pdf"
# 2-page doc; page index 1 carries /Rotate 90 (612x792 -> rendered 792x612).
_ROTATED = _FIXTURES / "pdmodel" / "interactive" / "form" / "AcroFormsRotation.pdf"

# AWT BufferedImage.TYPE_* int -> the Pillow mode pypdfbox returns for it.
_AWT_TYPE_TO_PIL_MODE = {
    1: "RGB",    # TYPE_INT_RGB
    2: "RGBA",   # TYPE_INT_ARGB
    10: "L",     # TYPE_BYTE_GRAY
    12: "1",     # TYPE_BYTE_BINARY
}
# AWT type int -> the ImageType pypdfbox renders for the same -color value.
_AWT_TYPE_TO_IMAGE_TYPE = {
    1: ImageType.RGB,
    2: ImageType.ARGB,
    10: ImageType.GRAY,
    12: ImageType.BINARY,
}


def _ink_bucket(img: PIL.Image) -> int:
    """Count of non-white cells in a 16x16 average-luminance grid — mirrors
    ``PdfToImageToolFuzzProbe.inkBucket`` (Rec.601 luminance, < 250 = ink)."""
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
    ink = 0
    for i in range(_GRID * _GRID):
        avg = round(total[i] / count[i]) if count[i] else 255
        if avg < _WHITE_CUTOFF:
            ink += 1
    return ink


# Each case: (label, dpi, start_page, end_page, awt_type, fixture).
# Mirrors the combo list in PdfToImageToolFuzzProbe.main, in the same order.
_CASES = [
    ("dpi72_full", 72.0, 1, 2**31 - 1, 1, _MULTI),
    ("dpi96_full", 96.0, 1, 2**31 - 1, 1, _MULTI),
    ("dpi150_full", 150.0, 1, 2**31 - 1, 1, _MULTI),
    ("dpi300_full", 300.0, 1, 2**31 - 1, 1, _MULTI),
    ("rgb_p1", 96.0, 1, 1, 1, _MULTI),
    ("argb_p1", 96.0, 1, 1, 2, _MULTI),
    ("gray_p1", 96.0, 1, 1, 10, _MULTI),
    ("binary_p1", 96.0, 1, 1, 12, _MULTI),
    ("mid_2to3", 96.0, 2, 3, 1, _MULTI),
    ("end_clamped_1to99", 96.0, 1, 99, 1, _MULTI),
    ("start_oor_50to99", 96.0, 50, 99, 1, _MULTI),
    ("start_gt_end_3to2", 96.0, 3, 2, 1, _MULTI),
    ("single_last", 96.0, 4, 4, 1, _MULTI),
    ("gray_p1_300", 300.0, 1, 1, 10, _MULTI),
    ("argb_p1_72", 72.0, 1, 1, 2, _MULTI),
    ("binary_p1_150", 150.0, 1, 1, 12, _MULTI),
    ("rotated_p2_72", 72.0, 2, 2, 1, _ROTATED),
    ("rotated_p2_150", 150.0, 2, 2, 1, _ROTATED),
    ("rotated_doc_72", 72.0, 1, 2**31 - 1, 1, _ROTATED),
]


def _parse_oracle() -> dict[str, list[dict]]:
    """Run the probe once and parse its ``case=`` blocks into a per-label map of
    page records ``{page, w, h, type, bands, ink}``."""
    text = run_probe_text("PdfToImageToolFuzzProbe", str(_MULTI), str(_ROTATED))
    blocks: dict[str, list[dict]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("case="):
            parts = line.split()
            current = parts[0].split("=", 1)[1]
            blocks[current] = []
        elif line.startswith("page=") and current is not None:
            fields = dict(tok.split("=", 1) for tok in line.split() if "=" in tok)
            wxh = next(tok for tok in line.split() if "x" in tok and "=" not in tok)
            w, h = (int(v) for v in wxh.split("x"))
            blocks[current].append(
                {
                    "page": int(fields["page"]),
                    "w": w,
                    "h": h,
                    "type": int(fields["type"]),
                    "bands": int(fields["bands"]),
                    "ink": int(fields["ink"]),
                }
            )
    return blocks


def _pypdfbox_pages(
    fixture: Path, dpi: float, start_page: int, end_page: int, awt_type: int
) -> list[dict]:
    """Run the tool's per-page render loop through pypdfbox and build the same
    page records the probe emits."""
    image_type = _AWT_TYPE_TO_IMAGE_TYPE[awt_type]
    records: list[dict] = []
    with PDDocument.load(fixture) as doc:
        pages = doc.get_number_of_pages()
        real_end = min(end_page, pages)
        renderer = PDFRenderer(doc)
        for i in range(start_page - 1, real_end):
            if i < 0:
                continue
            img = renderer.render_image_with_dpi(i, dpi, image_type)
            records.append(
                {
                    "page": i + 1,
                    "w": img.size[0],
                    "h": img.size[1],
                    "mode": img.mode,
                    "ink": _ink_bucket(img),
                }
            )
    return records


@requires_oracle
@pytest.mark.parametrize(
    ("label", "dpi", "start_page", "end_page", "awt_type", "fixture"),
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_pdf_to_image_combo_matches_pdfbox(
    label: str,
    dpi: float,
    start_page: int,
    end_page: int,
    awt_type: int,
    fixture: Path,
) -> None:
    oracle = _parse_oracle()
    assert label in oracle, f"probe emitted no case for {label!r}"
    java_pages = oracle[label]
    py_pages = _pypdfbox_pages(fixture, dpi, start_page, end_page, awt_type)

    # Count contract (page-range windowing incl. clamp / start>end -> 0).
    assert len(py_pages) == len(java_pages), (
        f"{label}: image count diverges: "
        f"pypdfbox={len(py_pages)} java={len(java_pages)}"
    )

    for jp, pp in zip(java_pages, py_pages, strict=True):
        # 1-based output indexing.
        assert pp["page"] == jp["page"], (
            f"{label}: page index diverges: py={pp['page']} java={jp['page']}"
        )
        # Output dimensions (DPI scale incl. the float32 boundary; rotation
        # swaps W/H).
        assert (pp["w"], pp["h"]) == (jp["w"], jp["h"]), (
            f"{label} p{jp['page']}: dimensions diverge: "
            f"pypdfbox={pp['w']}x{pp['h']} java={jp['w']}x{jp['h']}"
        )
        # Pixel format: AWT type/bands map to the Pillow mode pypdfbox returns.
        expected_mode = _AWT_TYPE_TO_PIL_MODE[jp["type"]]
        assert pp["mode"] == expected_mode, (
            f"{label} p{jp['page']}: pixel mode diverges: pypdfbox={pp['mode']} "
            f"java type={jp['type']} bands={jp['bands']} (expected {expected_mode})"
        )
        # Coarse content fingerprint. ARGB skipped: Java's TYPE_INT_ARGB canvas
        # reads transparent-black (ink=256) while Pillow RGBA reads
        # transparent-white — a documented background-fill divergence, not a
        # render bug (dimensions/mode still match).
        if jp["type"] == 2:  # TYPE_INT_ARGB
            continue
        if jp["ink"] > 0:
            assert pp["ink"] > 0, (
                f"{label} p{jp['page']}: pypdfbox rendered a BLANK page "
                f"(ink=0) where PDFBox has content (ink={jp['ink']})"
            )
        assert abs(pp["ink"] - jp["ink"]) <= _INK_TOLERANCE, (
            f"{label} p{jp['page']}: ink bucket diverges beyond AA: "
            f"pypdfbox={pp['ink']} java={jp['ink']} (tol {_INK_TOLERANCE})"
        )


@requires_oracle
def test_cli_writes_one_file_per_page_in_window(tmp_path: Path) -> None:
    """End-to-end CLI count contract: ``PDFToImage.main`` writes exactly one
    ``<prefix>-<n>.<fmt>`` per rendered page, 1-based, matching the probe's
    count for a clamped window and a degenerate ``start > end`` window."""
    oracle = _parse_oracle()

    # Clamped end window: 1..99 over a 4-page doc -> 4 files (1..4).
    prefix = tmp_path / "clamp"
    rc = PDFToImage.main(
        [
            "-i", str(_MULTI), "-format", "png", "-dpi", "72",
            "-startPage", "1", "-endPage", "99", "-prefix", str(prefix),
        ]
    )
    assert rc == 0
    files = sorted(
        tmp_path.glob("clamp-*.png"),
        key=lambda p: int(p.stem.rsplit("-", 1)[1]),
    )
    indices = [int(f.stem.rsplit("-", 1)[1]) for f in files]
    assert indices == [p["page"] for p in oracle["end_clamped_1to99"]]

    # Degenerate start>end -> zero files (matches the probe's count=0).
    prefix2 = tmp_path / "degen"
    rc2 = PDFToImage.main(
        [
            "-i", str(_MULTI), "-format", "png", "-dpi", "72",
            "-startPage", "3", "-endPage", "2", "-prefix", str(prefix2),
        ]
    )
    assert rc2 == 0
    assert list(tmp_path.glob("degen-*.png")) == []
    assert oracle["start_gt_end_3to2"] == []
