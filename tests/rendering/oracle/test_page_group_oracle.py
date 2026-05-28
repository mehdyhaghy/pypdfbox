"""Live PDFBox differential parity for **page-level** ``/Group /S /Transparency``
(PDF 32000-1 §11.6.4).

Per spec §11.6.4, a page may carry a ``/Group << /S /Transparency /CS /DeviceRGB
/I true … >>`` dictionary on the page object itself, which causes the page's
contents to be composited as a single transparency group against an initial
backdrop (typically white for output-on-paper rendering). This is distinct
from the Form-XObject / soft-mask group surfaces already pinned by
``test_transparency_group_oracle.py`` and ``test_soft_mask_oracle.py``: those
groups live inside a Form XObject; the page-level group wraps the whole page
content stream.

For purely-opaque content the page-level group is a visual no-op — the
composite is identical to direct paint against a white backdrop. The
interesting case is content that *uses* transparency (``/ca``, ``/CA``,
``/SMask``, blend modes, etc.) — there the group's isolated white backdrop
is what the per-element compositing draws against.

The two fixtures here are kept deliberately simple:

* **with page /Group** — a page carrying ``/Group << /S /Transparency /CS
  /DeviceRGB /I true >>`` whose content paints two overlapping ``/ca 0.5``
  rectangles over the white page backdrop.
* **without page /Group (control)** — the exact same content stream with no
  ``/Group`` entry on the page dict.

For this content PDFBox produces near-identical rasters either way (the
group's isolated white backdrop matches the direct paper backdrop), so the
parity gate is that *each* fixture matches PDFBox within
``MAD < 6 / MAXDIFF < 60`` at 72 DPI. We do not require the two fixtures to
*differ* — the point is that pypdfbox tracks PDFBox's behaviour whether or
not the page declares a transparency group.

Same coarse fingerprint as the page-render oracle: exact rendered dimensions
plus a 16×16 average-luminance grid gated at ``MAD < 6`` / ``MAXDIFF < 60``
against ``oracle/probes/RenderProbe.java`` (72 DPI).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60
_MB = 100  # media-box side, pt (== px at 72 DPI)

# Two overlapping translucent rects (/ca 0.5 each) painted over the white page
# backdrop. With the page /Group present, compositing happens against the
# group's isolated white initial backdrop (per spec §11.6.4); without it,
# directly against the page backdrop. For pure-white backdrops these are
# visually equivalent — the parity claim below is per-fixture against PDFBox.
_PAGE_CONTENT = (
    b"q\n"
    b"/GS0 gs\n"
    b"0.9 0.1 0.1 rg\n"
    b"10 10 60 60 re\nf\n"
    b"0.1 0.8 0.1 rg\n"
    b"30 30 60 60 re\nf\n"
    b"Q\n"
)


def _grid_from_image(img: Image.Image) -> list[int]:
    """16×16 average-luminance fingerprint — identical cell mapping to
    ``RenderProbe.java``."""
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


def _oracle_signature(fixture: Path) -> tuple[tuple[int, int], list[int]]:
    """Run RenderProbe on page 0 and parse its (dims, 16×16 grid)."""
    lines = run_probe_text("RenderProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _assert_parity(label: str, fixture: Path) -> None:
    """Render ``fixture`` via Java + pypdfbox at 72 DPI and assert exact dims
    plus 16×16 luminance-grid parity within the MAD/MAXDIFF gate."""
    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — page /Group handling diverges from PDFBox"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


def _build_page_group_fixture(path: Path, *, with_page_group: bool) -> None:
    """Build a single-page PDF carrying two ``/ca 0.5`` overlapping rectangles,
    with (or without) a page-level ``/Group /S /Transparency /CS /DeviceRGB
    /I true`` dictionary on the page itself."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)

    egs = COSDictionary()
    egs.set_item(COSName.get_pdf_name("ca"), COSFloat(0.5))

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("ExtGState"), COSName.get_pdf_name("GS0"), egs
    )

    contents = COSStream()
    contents.set_raw_data(_PAGE_CONTENT)
    page.get_cos_object().set_item(COSName.CONTENTS, contents)

    if with_page_group:
        group = COSDictionary()
        group.set_item(
            COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency")
        )
        group.set_item(
            COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceRGB")
        )
        group.set_item(COSName.get_pdf_name("I"), COSBoolean.TRUE)
        page.set_group(group)

    doc.save(str(path))
    doc.close()


@requires_oracle
@pytest.mark.parametrize(
    "with_page_group",
    [True, False],
    ids=["with_page_group", "no_page_group_control"],
)
def test_page_group_matches_pdfbox(with_page_group: bool, tmp_path: Path) -> None:
    """Page-level ``/Group /S /Transparency /CS /DeviceRGB /I true`` (PDF
    §11.6.4) must produce the same raster as PDFBox at 72 DPI; the
    no-``/Group`` control must also match. Whether the two fixtures differ
    *from each other* is implementation-dependent for this opaque-backdrop
    content (PDFBox produces visually identical output) — the parity claim
    is per-fixture against PDFBox."""
    suffix = "with_page_group" if with_page_group else "no_page_group"
    fixture = tmp_path / f"page_group_{suffix}.pdf"
    _build_page_group_fixture(fixture, with_page_group=with_page_group)
    _assert_parity(f"page_group/{suffix}", fixture)


@requires_oracle
def test_page_group_round_trip(tmp_path: Path) -> None:
    """The page-/Group dict must survive save→load: the rebuilt fixture is
    read back via :class:`PDDocument` and its ``/Group`` is verified before
    handing it to the renderer. Guards against the silent failure mode where
    ``set_group`` writes the dict but the writer drops it on save (no
    differential signal then, just an unobserved drop)."""
    fixture = tmp_path / "page_group_roundtrip.pdf"
    _build_page_group_fixture(fixture, with_page_group=True)

    with PDDocument.load(fixture) as doc:
        page = doc.get_page(0)
        group = page.get_group()
        assert group is not None, (
            "page /Group dropped on save — writer is not preserving the "
            "page-level transparency group entry"
        )
        s_value = group.get_dictionary_object(COSName.get_pdf_name("S"))
        assert s_value == COSName.get_pdf_name("Transparency"), (
            f"page /Group /S survived but wrong value: {s_value!r}"
        )
        cs_value = group.get_dictionary_object(COSName.get_pdf_name("CS"))
        assert cs_value == COSName.get_pdf_name("DeviceRGB"), (
            f"page /Group /CS survived but wrong value: {cs_value!r}"
        )


