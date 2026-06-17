"""Live Apache PDFBox parity for ``org.apache.pdfbox.tools.PDFToImage``.

Drives the render-to-image surface of the tool: each page in the
``[startPage, endPage]`` window is rasterised with
``PDFRenderer.renderImageWithDPI(i, dpi, ImageType.RGB)`` and written as one
output image. The ``PdfToImageProbe`` Java probe runs that exact per-page loop
against Apache PDFBox 3.0.7 and emits a canonical summary::

    count=<number of images>
    page=<1-based index> <width>x<height>
    ...

pypdfbox's :class:`pypdfbox.tools.pdf_to_image.PDFToImage` runs the full CLI
(``PDFToImage.main``) on the same fixture; we then count the produced files and
measure each with Pillow and rebuild the same summary. This pins, at parity:

* the number of output images (= the ``startPage``/``endPage`` page subset),
* each image's pixel dimensions (= page size at the chosen DPI), and
* the 1-based output filename indexing (``<prefix>-<n>.<fmt>``).

A 4-page Letter fixture is used so the full document, a mid-document subset, and
a single-page selection all exercise the count + dimension contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.tools.pdf_to_image import PDFToImage
from tests.oracle.harness import requires_oracle, run_probe_text

PIL = pytest.importorskip("PIL.Image")

# 4-page document, every page US Letter (612x792 pt).
_PDF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "pdmodel"
    / "page_tree_multiple_levels.pdf"
)


def _pypdfbox_summary(dpi: int, start_page: int, end_page: int, tmp_path: Path) -> str:
    """Run the pypdfbox PDFToImage CLI and rebuild the probe's summary from
    the PNG files it wrote."""
    prefix = tmp_path / "out"
    rc = PDFToImage.main(
        [
            "-i", str(_PDF),
            "-format", "png",
            "-dpi", str(dpi),
            "-startPage", str(start_page),
            "-endPage", str(end_page),
            "-prefix", str(prefix),
        ]
    )
    assert rc == 0, f"pypdfbox PDFToImage.main returned {rc}"

    files = sorted(
        tmp_path.glob("out-*.png"),
        key=lambda p: int(p.stem.rsplit("-", 1)[1]),
    )
    lines = [f"count={len(files)}"]
    for f in files:
        index = int(f.stem.rsplit("-", 1)[1])
        with PIL.open(f) as im:
            lines.append(f"page={index} {im.width}x{im.height}")
    return "\n".join(lines) + "\n"


@requires_oracle
@pytest.mark.parametrize(
    ("dpi", "start_page", "end_page"),
    [
        (96, 1, 2**31 - 1),  # full document
        (96, 2, 3),          # mid-document subset
        (150, 1, 1),         # single page at a non-default DPI
    ],
    ids=["full_96dpi", "subset_2to3_96dpi", "single_150dpi"],
)
def test_render_to_image_matches_pdfbox(
    dpi: int, start_page: int, end_page: int, tmp_path: Path
) -> None:
    java_summary = run_probe_text(
        "PdfToImageProbe", str(_PDF), str(dpi), str(start_page), str(end_page)
    )
    py_summary = _pypdfbox_summary(dpi, start_page, end_page, tmp_path)

    assert py_summary == java_summary, (
        "PDFToImage render-to-image divergence:\n"
        f"  java: {java_summary!r}\n"
        f"  py:   {py_summary!r}"
    )
