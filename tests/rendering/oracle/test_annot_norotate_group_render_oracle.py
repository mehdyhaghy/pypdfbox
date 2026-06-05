"""Live PDFBox differential parity for a **NoRotate** annotation
(PDF 32000-1 §12.5.3 ``/F`` bit 5, value 16) whose Normal Appearance is a
**transparency-group** form XObject (``/Group <</S /Transparency>>``), under
page ``/Rotate`` (PDFBOX-4744).

Wave 1484 pinned the NoRotate counter-rotation itself
(``test_annot_norotate_render_oracle.py``) for plain appearances. This module
covers the orthogonal combination flagged in ``DEFERRED.md``: an appearance
that is a transparency group carrying non-trivial alpha (an ExtGState
``/ca 0.5`` plus overlapping fills). Upstream ``PageDrawer.showAnnotation``
rebuilds transparency-group appearances and *then* applies the PDFBOX-4744
counter-rotation about the rect's upper-left corner; pypdfbox folds the
counter-rotation onto the user-space CTM *before* the appearance stream is
walked, so when the appearance form is a transparency group its off-screen
group canvas is painted *through* the already-counter-rotated CTM. The two
orderings are geometrically equivalent — this module proves that empirically
against Apache PDFBox 3.0.7.

Two probes drive the comparison:

* ``AnnotApStateProbe`` — the page-0 16x16 average-luminance fingerprint
  (same coarse gate as ``test_annot_norotate_render_oracle.py``,
  ``MAD < 6`` / ``MAXDIFF < 60``), guarding against gross divergence (blank,
  wrong scale/rotation, wrong placement).
* ``PixelSampleProbe`` — exact per-channel RGB at the group's overlap /
  single-colour regions, which a grey-luminance average can mask. The
  discriminating fixture paints the group over a *black* page backdrop so a
  per-element (rather than per-group) constant-alpha application would show as
  a darkened overlap; we assert exact (``maxdiff <= 1``) per-channel parity.

Oracle-free contract pins (``test_*_pin``) also assert the NoRotate-vs-control
*distinctness* under rotation and the no-op on an unrotated page, so the
behavioural contract regression-tests on machines without Java.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
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
# Per-channel exact-colour tolerance for PixelSampleProbe (sRGB rounding only).
_PX_TOLERANCE = 1

# Non-square media box so the 90/270 width/height swap is observable.
_PAGE_W = 200.0
_PAGE_H = 300.0

_BBOX = (0.0, 0.0, 100.0, 100.0)
# Rect placed off-centre; BBox is the 0..100 square so the §12.5.5 map is a
# pure translate (1x scale: rect is 100x100).
_RECT = (40.0, 50.0, 140.0, 150.0)

# /F flag bits (PDF 32000-1 Table 165): NoRotate = bit 5, value 16.
_FLAG_NO_ROTATE = 16

# Appearance content: two overlapping opaque fills, both painted under an
# ExtGState ``/ca 0.5``. When the form is a transparency group the constant
# alpha applies to the group *as a whole*; the overlap therefore composites
# once, not twice. Red box (0..70) then blue box (30..100): the overlap
# (30..70) is the last-painted blue.
_SHAPE = b"/GS gs\n1 0 0 rg\n0 0 70 70 re\nf\n0 0 1 rg\n30 30 70 70 re\nf\n"
# Discriminating variant painted over a black page backdrop with two
# *different* colours that don't fully overlap, so the group constant alpha
# is visible on each colour against black.
_SHAPE_ON_BLACK = b"/GS gs\n0 1 0 rg\n0 0 70 70 re\nf\n0 0 1 rg\n30 30 70 70 re\nf\n"

_BLANK_THRESHOLD = 250  # cell luminance at/above this == effectively white


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


def _oracle_pixels(
    pdf: Path, points: list[tuple[int, int]]
) -> tuple[tuple[int, int], list[tuple[int, int, int]]]:
    args = [f"{x},{y}" for x, y in points]
    lines = run_probe_text("PixelSampleProbe", str(pdf), "0", *args).splitlines()
    width, height = (int(v) for v in lines[0].split())
    rgb = [tuple(int(v) for v in ln.split()) for ln in lines[1:]]
    return (width, height), rgb  # type: ignore[return-value]


def _diff(a: list[int], b: list[int]) -> tuple[float, int]:
    diffs = [abs(x - y) for x, y in zip(a, b, strict=True)]
    return sum(diffs) / len(diffs), max(diffs)


def _is_blank(grid: list[int]) -> bool:
    return all(v >= _BLANK_THRESHOLD for v in grid)


def _render_py(pdf: Path) -> Image.Image:
    with PDDocument.load(pdf) as doc:
        return PDFRenderer(doc).render_image_with_dpi(0, 72.0)


# ----------------------------------------------------------------- builders


def _group_substream(content: bytes, *, group: bool) -> COSStream:
    """A Form XObject appearance whose content fills overlap under a
    ``/ca 0.5`` ExtGState, optionally tagged as a ``/Group /S /Transparency``."""
    stream = COSStream()
    stream.set_raw_data(content)
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Form"))
    bbox_arr = COSArray()
    for v in _BBOX:
        bbox_arr.add(COSFloat(v))
    stream.set_item(COSName.get_pdf_name("BBox"), bbox_arr)
    # ExtGState /GS with /ca + /CA 0.5.
    ext_gs = COSDictionary()
    ext_gs.set_item(COSName.get_pdf_name("ca"), COSFloat(0.5))
    ext_gs.set_item(COSName.get_pdf_name("CA"), COSFloat(0.5))
    ext_gs.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("ExtGState"))
    ext_gs_dict = COSDictionary()
    ext_gs_dict.set_item(COSName.get_pdf_name("GS"), ext_gs)
    resources = COSDictionary()
    resources.set_item(COSName.get_pdf_name("ExtGState"), ext_gs_dict)
    stream.set_item(COSName.get_pdf_name("Resources"), resources)
    if group:
        grp = COSDictionary()
        grp.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
        grp.set_item(COSName.get_pdf_name("I"), COSBoolean.TRUE)
        grp.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Group"))
        stream.set_item(COSName.get_pdf_name("Group"), grp)
    return stream


def _fresh_doc(rotation: int, *, black_bg: bool = False) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE_W, _PAGE_H))
    page.set_rotation(rotation)
    if black_bg:
        bg = COSStream()
        bg.set_raw_data(b"0 0 0 rg\n0 0 200 300 re\nf\n")
        page.set_contents(bg)
    doc.add_page(page)
    return doc, page


def _widget(
    ap_n: object,
    *,
    no_rotate: bool,
) -> PDAnnotationWidget:
    widget = PDAnnotationWidget()
    widget.set_rectangle(
        PDRectangle(_RECT[0], _RECT[1], _RECT[2] - _RECT[0], _RECT[3] - _RECT[1])
    )
    ap = PDAppearanceDictionary()
    ap.get_cos_object().set_item(COSName.get_pdf_name("N"), ap_n)
    widget.set_appearance(ap)
    if no_rotate:
        widget.get_cos_object().set_item(
            COSName.get_pdf_name("F"), COSInteger.get(_FLAG_NO_ROTATE)
        )
    return widget


def _build(
    path: Path,
    rotation: int,
    *,
    no_rotate: bool,
    group: bool,
    content: bytes = _SHAPE,
    black_bg: bool = False,
) -> None:
    doc, page = _fresh_doc(rotation, black_bg=black_bg)
    page.add_annotation(
        _widget(_group_substream(content, group=group), no_rotate=no_rotate)
    )
    doc.save(str(path))
    doc.close()


# ----------------------------------------------------------------- oracle parity

_ROTATIONS = [0, 90, 180, 270]


@requires_oracle
@pytest.mark.parametrize("rotation", _ROTATIONS, ids=[str(r) for r in _ROTATIONS])
def test_norotate_transparency_group_matches_pdfbox(
    rotation: int, tmp_path: Path
) -> None:
    """A NoRotate Widget whose appearance is a /Group /S /Transparency form
    must composite + counter-rotate exactly as Apache PDFBox (coarse grid)."""
    pdf = tmp_path / f"norot_grp_{rotation}.pdf"
    _build(pdf, rotation, no_rotate=True, group=True)

    (java_w, java_h), java_grid = _oracle_signature(pdf)
    img = _render_py(pdf)
    assert img.size == (java_w, java_h), (
        f"rotation {rotation}: rendered dimensions diverge: "
        f"pypdfbox={img.size} java={java_w}x{java_h}"
    )
    assert not _is_blank(java_grid), "oracle precondition: annotation must paint"
    mad, maxdiff = _diff(java_grid, _grid_from_image(img))
    assert mad < _MAD_TOLERANCE and maxdiff < _MAXDIFF_TOLERANCE, (
        f"rotation {rotation}: NoRotate transparency-group appearance diverges "
        f"from PDFBox (MAD={mad:.2f}, MAXDIFF={maxdiff})"
    )


@requires_oracle
@pytest.mark.parametrize("rotation", _ROTATIONS, ids=[str(r) for r in _ROTATIONS])
def test_norotate_transparency_group_overlap_pixels_match_pdfbox(
    rotation: int, tmp_path: Path
) -> None:
    """Exact per-channel parity at the group's single-colour regions over a
    black backdrop — the discriminating test that the group constant alpha is
    applied per-group (not per-element) under the NoRotate counter-rotation."""
    pdf = tmp_path / f"norot_grp_blk_{rotation}.pdf"
    _build(
        pdf,
        rotation,
        no_rotate=True,
        group=True,
        content=_SHAPE_ON_BLACK,
        black_bg=True,
    )
    img = _render_py(pdf).convert("RGB")
    width, height = img.size
    pixels = img.load()

    # Locate a green-only pixel and a blue-only pixel in the rendered output.
    found: dict[str, tuple[int, int]] = {}
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            if g > 60 and r < 40 and b < 40 and "green" not in found:
                found["green"] = (x, y)
            if b > 60 and r < 40 and g < 40 and "blue" not in found:
                found["blue"] = (x, y)
            if "green" in found and "blue" in found:
                break
        if "green" in found and "blue" in found:
            break
    assert "green" in found and "blue" in found, (
        f"rotation {rotation}: could not locate group fill pixels — the "
        f"appearance did not paint"
    )

    points = list(found.values())
    (java_w, java_h), java_rgb = _oracle_pixels(pdf, points)
    assert (width, height) == (java_w, java_h)
    for (name, pt), jrgb in zip(found.items(), java_rgb, strict=True):
        prgb = pixels[pt[0], pt[1]]
        maxd = max(abs(p - j) for p, j in zip(prgb, jrgb, strict=True))
        assert maxd <= _PX_TOLERANCE, (
            f"rotation {rotation}: {name} pixel {pt} diverges — "
            f"pypdfbox={prgb} java={jrgb} (maxdiff={maxd})"
        )


@requires_oracle
@pytest.mark.parametrize("rotation", [90, 270], ids=["90", "270"])
def test_norotate_group_overlap_matches_nongroup_against_pdfbox(
    rotation: int, tmp_path: Path
) -> None:
    """The transparency-group appearance and the otherwise-identical
    non-group appearance must BOTH match PDFBox at the overlap region — i.e.
    tagging the appearance as a group does not perturb the counter-rotated
    composite relative to the upstream reference."""
    grp_pdf = tmp_path / f"grp_{rotation}.pdf"
    plain_pdf = tmp_path / f"plain_{rotation}.pdf"
    _build(grp_pdf, rotation, no_rotate=True, group=True)
    _build(plain_pdf, rotation, no_rotate=True, group=False)

    # Find the overlap pixel (last-painted blue at /ca 0.5 over white ->
    # ~ (127,127,255)) in the group render, then sample both PDFs there.
    img = _render_py(grp_pdf).convert("RGB")
    width, height = img.size
    pixels = img.load()
    overlap: tuple[int, int] | None = None
    for y in range(height):
        for x in range(width):
            if pixels[x, y] == (127, 127, 255):
                overlap = (x, y)
                break
        if overlap is not None:
            break
    assert overlap is not None, f"rotation {rotation}: no overlap pixel painted"

    for pdf in (grp_pdf, plain_pdf):
        (_jw, _jh), java_rgb = _oracle_pixels(pdf, [overlap])
        py_img = _render_py(pdf).convert("RGB")
        prgb = py_img.getpixel(overlap)
        maxd = max(abs(p - j) for p, j in zip(prgb, java_rgb[0], strict=True))
        assert maxd <= _PX_TOLERANCE, (
            f"rotation {rotation}: {pdf.name} overlap {overlap} diverges — "
            f"pypdfbox={prgb} java={java_rgb[0]} (maxdiff={maxd})"
        )


# ----------------------------------------------------------------- oracle-free pins


@pytest.mark.parametrize("rotation", [90, 180, 270], ids=["90", "180", "270"])
def test_norotate_group_distinct_from_control_pin(
    rotation: int, tmp_path: Path
) -> None:
    """Oracle-free contract: on a rotated page a NoRotate transparency-group
    appearance must render *differently* from the same group without the flag
    (the counter-rotation is applied), and both must paint."""
    plain = tmp_path / f"plain_{rotation}.pdf"
    norot = tmp_path / f"norot_{rotation}.pdf"
    _build(plain, rotation, no_rotate=False, group=True)
    _build(norot, rotation, no_rotate=True, group=True)

    plain_grid = _grid_from_image(_render_py(plain))
    norot_grid = _grid_from_image(_render_py(norot))

    assert not _is_blank(plain_grid), f"rotation {rotation}: control must paint"
    assert not _is_blank(norot_grid), f"rotation {rotation}: NoRotate must paint"
    _mad, maxdiff = _diff(plain_grid, norot_grid)
    assert maxdiff >= _MAXDIFF_TOLERANCE, (
        f"rotation {rotation}: NoRotate group produced the same image as the "
        f"control (maxdiff={maxdiff}) — counter-rotation was not applied"
    )


def test_norotate_group_on_unrotated_page_matches_control_pin(
    tmp_path: Path,
) -> None:
    """Oracle-free contract: with /Rotate 0 the NoRotate flag is a no-op — a
    transparency-group appearance must render identically with and without it."""
    plain = tmp_path / "plain_0.pdf"
    norot = tmp_path / "norot_0.pdf"
    _build(plain, 0, no_rotate=False, group=True)
    _build(norot, 0, no_rotate=True, group=True)

    plain_grid = _grid_from_image(_render_py(plain))
    norot_grid = _grid_from_image(_render_py(norot))
    assert plain_grid == norot_grid, (
        "NoRotate transparency-group on an unrotated page must be a no-op "
        "(identical render)"
    )


def test_norotate_group_matches_nongroup_render_pin(tmp_path: Path) -> None:
    """Oracle-free contract: for these opaque-fill appearances the group tag
    must not change the rendered result versus the untagged form (the group
    constant alpha applies once either way) — pins the inline-vs-group-buffer
    equivalence the surface relies on."""
    for rotation in (0, 90, 180, 270):
        grp = tmp_path / f"g_{rotation}.pdf"
        plain = tmp_path / f"p_{rotation}.pdf"
        _build(grp, rotation, no_rotate=True, group=True)
        _build(plain, rotation, no_rotate=True, group=False)
        grp_grid = _grid_from_image(_render_py(grp))
        plain_grid = _grid_from_image(_render_py(plain))
        assert grp_grid == plain_grid, (
            f"rotation {rotation}: group vs non-group appearance diverged "
            f"in the lite renderer"
        )
