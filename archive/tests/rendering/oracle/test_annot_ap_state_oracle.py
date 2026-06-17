"""Live PDFBox differential parity for annotation appearance-STATE selection
when rendering an annotation onto the page (PDF 32000-1 §12.5.5 / §12.7.3.3).

``test_annotation_appearance_transform_oracle.py`` already pins the §12.5.5
``/BBox``-after-``/Matrix`` → ``/Rect`` *placement* algorithm using a Stamp
annotation with a single direct ``/AP /N`` stream. The orthogonal surface
NOT covered there is the **appearance-state subdictionary**: a widget whose
``/AP /N`` is a *dictionary mapping state names to substreams* (the checkbox /
radio idiom — ``/Off``, ``/On``/``/Yes`` …). When the renderer paints such an
annotation it must select the substream named by the annotation's ``/AS``
entry (``PDAnnotation.getNormalAppearanceStream`` resolves ``/N`` → the
``/AS``-keyed substream) and composite *only that one* at the ``/Rect``.

A renderer that ignored ``/AS`` (e.g. grabbed the first substream, or painted
none because ``/N`` is a dict rather than a stream) would paint the wrong
shape — or nothing — landing far outside the fingerprint gate against Apache
PDFBox's correct render of the same widget.

Each fixture is a tiny one-page PDF built in-process via pypdfbox (a
``/Subtype /Widget`` annotation whose ``/AP /N`` carries two visually distinct
substreams). We render through Apache PDFBox 3.0.7
(``oracle/probes/AnnotApStateProbe.java``) and through pypdfbox's
:class:`PDFRenderer`, comparing the coarse 16x16 average-luminance grid.

Pixel-EXACT parity is impossible (Pillow vs Java2D AA — see ``CHANGES.md``);
we gate the proven coarse fingerprint at ``MAD < 6`` / ``MAXDIFF < 60``,
mirroring ``test_annotation_appearance_transform_oracle.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60
_PAGE = 200.0

# Two visually distinct substreams, drawn in appearance (BBox) space
# 0..100 x 0..100. ``/On`` = a large dark block filling the lower-left
# 0..70 x 0..70 plus a bar up the left edge; ``/Off`` = a small dark block
# hugging the top-right 80..100 x 80..100. The two states light up opposite
# corners of the downsampled grid, so picking the wrong state — or none —
# is unmistakable in the fingerprint.
_ON_SHAPE = b"0 0 0 rg\n0 0 70 70 re\nf\n0 0 10 100 re\nf\n"
_OFF_SHAPE = b"0 0 0 rg\n80 80 20 20 re\nf\n"

# Rect placed off-centre on the 200x200 page; BBox is the 0..100 square so
# the §12.5.5 map is a translate + uniform scale (1x here: rect is 100x100).
_RECT = (50.0, 50.0, 150.0, 150.0)
_BBOX = (0.0, 0.0, 100.0, 100.0)


def _grid_from_image(img: Image.Image) -> list[int]:
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


def _oracle_signature(pdf: Path) -> tuple[tuple[int, int], list[int]]:
    lines = run_probe_text("AnnotApStateProbe", str(pdf), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split(",")]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _diff(a: list[int], b: list[int]) -> tuple[float, int]:
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


def _render_py(pdf: Path) -> Image.Image:
    with PDDocument.load(pdf) as doc:
        return PDFRenderer(doc).render_image_with_dpi(0, 72.0)


def _make_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)
    return doc, page


def _appearance_substream(content: bytes) -> COSStream:
    """A /Subtype /Form appearance substream drawing ``content`` with the
    shared ``/BBox`` (identity ``/Matrix``)."""
    stream = COSStream()
    stream.set_raw_data(content)
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Form"))
    bbox_arr = COSArray()
    for v in _BBOX:
        bbox_arr.add(COSFloat(v))
    stream.set_item(COSName.get_pdf_name("BBox"), bbox_arr)
    return stream


def _build_widget(path: Path, as_state: str) -> None:
    """A widget annotation whose ``/AP /N`` is a state subdictionary mapping
    ``/On`` and ``/Off`` to distinct substreams; ``/AS`` = ``as_state``
    selects which one paints at the ``/Rect``."""
    doc, page = _make_doc()
    widget = PDAnnotationWidget()
    widget.set_rectangle(
        PDRectangle(
            _RECT[0], _RECT[1], _RECT[2] - _RECT[0], _RECT[3] - _RECT[1]
        )
    )

    # Build the /AP /N subdictionary directly (set_normal_appearance only
    # takes a single entry; a state-mapped /N is a COSDictionary of streams).
    normal_sub = COSDictionary()
    normal_sub.set_item(COSName.get_pdf_name("On"), _appearance_substream(_ON_SHAPE))
    normal_sub.set_item(
        COSName.get_pdf_name("Off"), _appearance_substream(_OFF_SHAPE)
    )

    ap = PDAppearanceDictionary()
    ap.get_cos_object().set_item(COSName.get_pdf_name("N"), normal_sub)
    widget.set_appearance(ap)
    widget.set_appearance_state(as_state)
    page.add_annotation(widget)

    doc.save(str(path))
    doc.close()


_BUILDERS = {
    "as_on": lambda p: _build_widget(p, "On"),
    "as_off": lambda p: _build_widget(p, "Off"),
}


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_annot_ap_state_render_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """The substream selected by ``/AS`` must be the one PDFBox composites
    onto the page, within the 16x16 fingerprint gate."""
    pdf = tmp_path / f"{label}.pdf"
    _BUILDERS[label](pdf)

    (java_w, java_h), java_grid = _oracle_signature(pdf)
    img = _render_py(pdf)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    mad, maxdiff = _diff(java_grid, py_grid)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — /AS substream selection diverges, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_as_state_actually_selects_substream(tmp_path: Path) -> None:
    """Guard: the two states paint materially different shapes. Comparing
    PDFBox's ``/AS = /On`` reference against pypdfbox rendering the same
    widget with ``/AS = /Off`` must blow past the gate — proving the
    renderer honours ``/AS`` rather than always grabbing the same substream
    (a renderer that ignored ``/AS`` would score near zero here)."""
    on_pdf = tmp_path / "as_on.pdf"
    off_pdf = tmp_path / "as_off.pdf"
    _build_widget(on_pdf, "On")
    _build_widget(off_pdf, "Off")

    _dims, java_on_grid = _oracle_signature(on_pdf)
    py_off_grid = _grid_from_image(_render_py(off_pdf))
    mad, maxdiff = _diff(java_on_grid, py_off_grid)
    assert mad >= _MAD_TOLERANCE and maxdiff >= _MAXDIFF_TOLERANCE, (
        f"/AS-selection gate too loose: the /Off render matches the /On "
        f"reference (MAD={mad:.2f}, MAXDIFF={maxdiff}) — substreams not "
        f"distinct enough or /AS ignored"
    )
