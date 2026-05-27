"""Live PDFBox differential parity for ANNOTATION optional-content (``/OC``)
*render-time visibility*.

Surface under test: ``pypdfbox.pdmodel.interactive.annotation`` (
``PDAnnotation.get_optional_content`` / ``set_optional_content``) plus the
renderer's annotation-painting gate.

PDF 32000-1 §8.11.4.3: an annotation may carry an ``/OC`` entry naming an
optional-content group (OCG) or membership dictionary (OCMD). When that group
is OFF in the document's default configuration the annotation must NOT be
painted during rendering — exactly as content marked with that OCG via
``/OC ... BDC ... EMC`` is suppressed. This is distinct from the *content
stream* OC gate (``tests/rendering/oracle/test_optional_content_render_oracle.py``)
and from the optional-content *model* parity (``OcgProbe``): here the OCG
membership lives on the annotation dictionary itself.

Each case BUILDS a one-page PDF via pypdfbox with two filled-square markup
annotations that have a Normal Appearance (``/AP /N`` via
``construct_appearances``): one whose ``/OC`` points at an OCG that is ON in the
default config, one whose ``/OC`` points at an OCG that is OFF. The file is
saved ONCE to ``tmp_path``, then rendered through BOTH the Java oracle
(``RenderProbe.java`` at 72 DPI, default render state) and pypdfbox at 72 DPI.
Pixel-EXACT parity is impossible (Pillow vs Java2D AA), so we compare the same
coarse fingerprint as the rest of the render oracle suite: exact dimensions plus
a 16x16 average-luminance grid, gated at ``MAD < 6`` / ``MAXDIFF < 60``. The
OFF-OCG annotation must NOT paint (matching PDFBox).

The flip guard (``test_off_annotation_flipped_on_diverges``) re-renders the same
geometry with the OFF OCG flipped ON and asserts the result is *materially
different* from the OFF reference — proving annotation ``/OC`` visibility is
actually evaluated during rendering, not that every annotation paints.

Accessor parity (``test_get_optional_content_returns_ocg``) asserts
``get_optional_content()`` round-trips the OCG for both annotations.

Divergence FIXED (wave 1441)
----------------------------
``PdfRenderer._render_annotation`` honoured the ``/F`` Hidden/NoView/Print flags
(``_annotation_should_skip``) but ignored the annotation's ``/OC`` optional
content membership: an annotation belonging to an OFF OCG still painted. Upstream
``PageDrawer.showAnnotation`` calls ``isHiddenOCG(annotation.getOptionalContent())``
and returns early when the group is hidden. Fixed by gating ``_render_annotation``
on ``_property_list_is_hidden(annotation.get_optional_content())``.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (
    PDOptionalContentProperties,
)
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationSquare
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate as the rest of the render oracle suite — well above the AA ceiling
# (a correct annotation-OC render scores MAD ~0) yet far below a gross failure
# (an OFF annotation still painted blows a whole band of cells' luminance).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_MB = 200  # media-box side, pt


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint — identical cell mapping to
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
    """Run RenderProbe on page 0 and parse its (dims, 16x16 grid)."""
    lines = run_probe_text("RenderProbe", str(fixture), "0").splitlines()
    width, height = (int(v) for v in lines[0].split())
    grid = [int(v) for v in lines[1].split()]
    assert len(grid) == _GRID * _GRID
    return (width, height), grid


# ----------------------------------------------------------------- builders


def _make_square(rect: PDRectangle) -> PDAnnotationSquare:
    """A filled-square markup annotation with a Normal Appearance — a solid
    black interior with a black stroke, so it paints a strongly non-white block
    (suppressing it shifts whole cells from ~0 luminance to 255)."""
    square = PDAnnotationSquare()
    square.set_rectangle(rect)
    square.set_color([0.0, 0.0, 0.0])
    square.set_interior_color([0.0, 0.0, 0.0])
    return square


def _build_two_annotations(
    path: Path, *, off_present: bool, off_flipped_on: bool = False
) -> None:
    """Two filled-square annotations, each tagged with its own ``/OC`` OCG.

    The first OCG is always ON; the second is OFF in the default config when
    ``off_present`` (and flipped back ON when ``off_flipped_on`` — the guard
    case). Both annotations always carry a Normal Appearance, so the only thing
    that can suppress the second one is the annotation-OC visibility gate."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)

    props = PDOptionalContentProperties()
    g_on = PDOptionalContentGroup("Annot On")
    g_off = PDOptionalContentGroup("Annot Off")
    props.add_group(g_on)
    props.add_group(g_off)
    props.set_base_state("ON")
    if off_present and not off_flipped_on:
        props.set_group_enabled(g_off, False)
    doc.get_document_catalog().set_oc_properties(props)

    a_on = _make_square(PDRectangle(20, 110, 95, 185))
    a_on.set_optional_content(g_on)
    a_on.construct_appearances(doc)
    page.add_annotation(a_on)

    a_off = _make_square(PDRectangle(105, 15, 180, 90))
    a_off.set_optional_content(g_off)
    a_off.construct_appearances(doc)
    page.add_annotation(a_off)

    doc.save(str(path))
    doc.close()


@requires_oracle
def test_annotation_oc_off_not_painted_matches_pdfbox(tmp_path: Path) -> None:
    """An annotation whose ``/OC`` OCG is OFF in the default config must NOT
    paint — and pypdfbox's render matches Apache PDFBox within the AA gate."""
    fixture = tmp_path / "annot_oc_off.pdf"
    _build_two_annotations(fixture, off_present=True)

    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity. An OFF annotation still painted lands far
    # outside this gate.
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} (maxdiff={maxdiff}) "
        "— annotation OC visibility diverges from PDFBox, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} (mad={mad:.2f}) "
        "— a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_off_annotation_flipped_on_diverges(tmp_path: Path) -> None:
    """Guard the gate: the SAME page with the second OCG flipped ON must render
    *materially different* from the OFF reference. Proves annotation ``/OC``
    visibility is actually evaluated (the OFF annotation is suppressed), not
    that every annotation paints regardless. pypdfbox-vs-pypdfbox so the guard
    is independent of the Java oracle."""
    off_pdf = tmp_path / "annot_oc_off.pdf"
    on_pdf = tmp_path / "annot_oc_on.pdf"
    _build_two_annotations(off_pdf, off_present=True)
    _build_two_annotations(on_pdf, off_present=True, off_flipped_on=True)

    with PDDocument.load(off_pdf) as doc:
        off_grid = _grid_from_image(PDFRenderer(doc).render_image_with_dpi(0, 72.0))
    with PDDocument.load(on_pdf) as doc:
        on_grid = _grid_from_image(PDFRenderer(doc).render_image_with_dpi(0, 72.0))

    diffs = [abs(a - b) for a, b in zip(off_grid, on_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    # The second 75x75-pt black square is ~14% of the page; suppressing it
    # shifts a whole band of cells from ~0 (black) to 255 (white), MAD ~36.
    assert mad >= _MAD_TOLERANCE, (
        "annotation OC visibility not evaluated: flipping the second OCG ON "
        f"produced a render indistinguishable from the OFF reference (MAD {mad:.2f})"
    )


@requires_oracle
def test_get_optional_content_returns_ocg(tmp_path: Path) -> None:
    """``get_optional_content()`` round-trips the OCG for BOTH annotations —
    the accessor that the render gate consults must resolve the membership."""
    fixture = tmp_path / "annot_oc_off.pdf"
    _build_two_annotations(fixture, off_present=True)

    with PDDocument.load(fixture) as doc:
        annots = doc.get_page(0).get_annotations()
        assert len(annots) == 2
        names = set()
        for annot in annots:
            oc = annot.get_optional_content()
            assert oc is not None, "annotation /OC must resolve to a PDPropertyList"
            assert isinstance(oc, PDOptionalContentGroup), (
                f"expected an OCG, got {type(oc).__name__}"
            )
            names.add(oc.get_name())
    assert names == {"Annot On", "Annot Off"}
