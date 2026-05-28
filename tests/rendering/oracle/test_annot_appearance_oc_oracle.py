"""Live PDFBox differential parity for *marked-content optional-content*
suppression **inside an annotation appearance stream**.

Wave 1430 wired ``BMC`` / ``BDC`` / ``EMC`` dispatch + ``/OC`` visibility for
page content streams (``tests/rendering/oracle/test_optional_content_render_oracle.py``);
the same dispatch path must also fire while the renderer is walking an
annotation's Normal Appearance (``/AP /N``) form XObject. PDF 32000-1 §12.5.5
makes ``/AP /N`` a self-contained Form XObject — anything the page-level
content stream can do (graphics state, XObjects, marked content) the appearance
stream can do too, and the renderer's optional-content gate must honour it.

This file builds a one-page PDF whose only annotation is a ``/Subtype /Stamp``
whose appearance content stream wraps PART of its drawing in
``/OC <ocg-ref> BDC ... EMC`` where the OCG is OFF in the default config. The
unmarked half must still paint; the OC-marked half must NOT paint. We then:

1. render through Apache PDFBox 3.0.7 (``oracle/probes/RenderProbe.java``) and
   pypdfbox at 72 DPI;
2. compare dims exact + 16x16 average-luminance grid at ``MAD < 6`` /
   ``MAXDIFF < 60`` (the standard render-oracle gate — well above the AA ceiling,
   well below an entire OC-suppressed region painting / not painting);
3. flip-guard: re-render the same geometry with the OCG flipped ON and assert
   the pypdfbox-vs-pypdfbox grids diverge materially (proves the gate is real —
   if everything painted regardless, flipping the OCG would be a no-op and the
   grids would be identical).

The OC-marked block hugs the appearance lower-left and the unmarked block hugs
the appearance upper-right; suppression collapses ~25% of the appearance to
white, which lights up the MAD gate brightly when the dispatch fails.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (
    PDOptionalContentProperties,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_rubber_stamp import (
    PDAnnotationRubberStamp,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60
_PAGE = 200.0
_RECT = (40.0, 40.0, 160.0, 160.0)  # 120x120 appearance rectangle on a 200x200 page
_BBOX = (0.0, 0.0, 100.0, 100.0)  # appearance-space bbox


# --------------------------------------------------------------------------
# Appearance content bytes. The OC-marked block hugs the appearance
# lower-left (0..50 x 0..50); the unmarked block hugs the upper-right
# (50..100 x 50..100). Each is ~25% of the appearance area, so suppressing
# the OC block clears a whole quadrant of the rendered annotation — easily
# detectable in the 16x16 luminance fingerprint.
# --------------------------------------------------------------------------
_UNMARKED = b"0 0 0 rg\n50 50 50 50 re\nf\n"
_OC_MARKED = b"/OC /MC0 BDC\n0 0 0 rg\n0 0 50 50 re\nf\nEMC\n"


# --------------------------------------------------------------------------
# fingerprint helpers (must match RenderProbe.java's cell mapping exactly)
# --------------------------------------------------------------------------


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
    lines = run_probe_text("RenderProbe", str(pdf), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


def _diff(a: list[int], b: list[int]) -> tuple[float, int]:
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


def _render_py(pdf: Path) -> Image.Image:
    with PDDocument.load(pdf) as doc:
        return PDFRenderer(doc).render_image_with_dpi(0, 72.0)


# --------------------------------------------------------------------------
# PDF builder. ``second_off`` toggles whether the OCG named in the
# appearance's MC0 property list is OFF (default; OC-marked block hidden)
# or ON (flip guard; everything paints).
# --------------------------------------------------------------------------


def _build(path: Path, *, ocg_off: bool) -> None:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)

    # Catalog OCProperties — one OCG, default base-state ON. When
    # ``ocg_off`` is true the OCG is explicitly disabled in the default
    # config so the appearance's /OC /MC0 BDC sequence suppresses its half.
    props = PDOptionalContentProperties()
    ocg = PDOptionalContentGroup("Annot Appearance OC")
    props.add_group(ocg)
    props.set_base_state("ON")
    if ocg_off:
        props.set_group_enabled(ocg, False)
    doc.get_document_catalog().set_oc_properties(props)

    # Appearance stream. Build it directly as a COSStream so we can write
    # raw bytes mixing the unmarked + OC-marked blocks. Then wrap it in
    # PDAppearanceStream and attach a /Resources with /Properties/MC0 →
    # the OCG so the BDC operand resolves at render time.
    stream = COSStream()
    stream.set_raw_data(_UNMARKED + _OC_MARKED)
    appearance = PDAppearanceStream(stream)
    appearance.set_b_box(
        PDRectangle(_BBOX[0], _BBOX[1], _BBOX[2] - _BBOX[0], _BBOX[3] - _BBOX[1])
    )
    resources = PDResources()
    properties_sub = COSDictionary()
    properties_sub.set_item(COSName.get_pdf_name("MC0"), ocg.get_cos_object())
    resources.get_cos_object().set_item(
        COSName.get_pdf_name("Properties"), properties_sub
    )
    appearance.set_resources(resources)

    # Stamp annotation hosting the appearance.
    stamp = PDAnnotationRubberStamp()
    stamp.set_rectangle(
        PDRectangle(
            _RECT[0], _RECT[1], _RECT[2] - _RECT[0], _RECT[3] - _RECT[1]
        )
    )
    ap = PDAppearanceDictionary()
    ap.set_normal_appearance(appearance)
    stamp.set_appearance(ap)
    page.add_annotation(stamp)

    doc.save(str(path))
    doc.close()


# --------------------------------------------------------------------------
# differential tests
# --------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", ["oc_off", "oc_on"], ids=["oc_off", "oc_on"])
def test_annot_appearance_oc_matches_pdfbox(label: str, tmp_path: Path) -> None:
    """Both the OC-OFF (suppress one block) and OC-ON (paint both blocks)
    appearance-stream renders match PDFBox at the standard 16x16 luminance
    gate."""
    pdf = tmp_path / f"{label}.pdf"
    _build(pdf, ocg_off=(label == "oc_off"))

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
        f"(maxdiff={maxdiff}) — annotation-appearance /OC dispatch diverges "
        "from PDFBox, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_oc_flip_diverges(tmp_path: Path) -> None:
    """Guard the gate: rendering the SAME appearance with the OCG flipped
    ON produces a materially different pypdfbox grid than the OFF
    reference. Proves the BDC/EMC dispatch inside the appearance stream is
    actually evaluated — a renderer that ignored marked content (or always
    painted) would render the two cases identically and this assertion
    would fail."""
    off_pdf = tmp_path / "oc_off.pdf"
    on_pdf = tmp_path / "oc_on.pdf"
    _build(off_pdf, ocg_off=True)
    _build(on_pdf, ocg_off=False)

    off_grid = _grid_from_image(_render_py(off_pdf))
    on_grid = _grid_from_image(_render_py(on_pdf))
    mad, _maxdiff = _diff(off_grid, on_grid)
    # Suppressing one 50x50 (of 100x100) appearance block clears ~25% of the
    # annotation rect (which is itself ~36% of the page); the resulting
    # MAD-vs-painted is far above the AA gate.
    assert mad >= _MAD_TOLERANCE, (
        f"annotation-appearance /OC dispatch not evaluated: flipping the "
        f"OCG ON produced a render indistinguishable from the OFF "
        f"reference (MAD {mad:.2f})"
    )
