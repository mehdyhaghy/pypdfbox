"""Live PDFBox differential parity for the *fill* winding rule.

Renders small PDFs that exercise the even-odd vs nonzero-winding FILL
operators of :class:`PDFRenderer` against Apache PDFBox 3.0.7, comparing
the coarse 16x16 luminance fingerprint emitted by
``oracle/probes/RenderProbe.java``.

This is the FILL-rule counterpart to ``test_clipping_oracle.py`` (which
covers the even-odd *clip* operator ``W*``). Here the discriminating
surface is the fill operators themselves:

* ``f`` / ``F`` / ``fill`` — fill with the *nonzero winding* rule;
* ``f*`` — fill with the *even-odd* rule;
* ``B`` / ``B*`` — fill (winding / even-odd) then stroke;
* ``b`` / ``b*`` — close, fill (winding / even-odd) then stroke.

A self-intersecting or nested-subpath shape fills DIFFERENTLY under the
two rules. The canonical case is two concentric rectangles wound the
*same* direction:

* nonzero winding sees a winding number of 2 over the inner region — so
  it fills the whole outer rectangle as a solid block;
* even-odd toggles inside/outside at every boundary — so the inner
  rectangle becomes a transparent hole, leaving an annulus (donut).

Cases (all built in-process, 200x200pt page, rendered at 72 DPI):

(a) ``concentric_nonzero`` — outer (40..160) + inner (80..120) rects,
    same winding direction, filled ``f``  -> solid block.
(b) ``concentric_evenodd`` — identical geometry filled ``f*`` -> annulus
    with a white centre hole.
(c) ``star_nonzero``       — a self-intersecting 5-point star filled
    ``f``  -> the central pentagon is *inside* (winding 2) so it fills.
(d) ``star_evenodd``       — identical star filled ``f*`` -> the central
    pentagon toggles back to *outside* so it stays a hole.
(e) ``concentric_b_star``  — concentric rects via ``B*`` (even-odd
    fill + stroke): annulus fill plus a stroked boundary on both rects.

Tolerance mirrors ``test_clipping_oracle.py``: gate at ``MAD < 6.0`` and
``MAXDIFF < 60`` — above the AA ceiling, well below any fill-rule failure
floor. A guard test confirms the gate discriminates: the SAME concentric
geometry rendered nonzero vs even-odd by pypdfbox must score far over the
gate against each other, proving the winding rule is genuinely honoured
(an always-nonzero bug would make the two identical and the guard fail).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60
_PAGE = 200.0


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


# --------------------------------------------------------------------------
# PDF builders
# --------------------------------------------------------------------------


def _make_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)
    return doc, page


def _set_contents(page: PDPage, ops: bytes) -> None:
    cs = COSStream()
    cs.set_raw_data(ops)
    page.get_cos_object().set_item(COSName.CONTENTS, cs)


def _save(doc: PDDocument, path: Path) -> None:
    doc.save(str(path))
    doc.close()


# Two concentric rectangles, same winding direction (both lower-left
# origin + width/height, so ``re`` emits them counter-clockwise). Under
# nonzero winding the inner region has winding number 2 -> filled solid;
# under even-odd the inner rect is a hole -> annulus.
_CONCENTRIC_PATH = b"40 40 120 120 re\n80 80 40 40 re\n"

# A 5-point self-intersecting star (the classic pentagram). Traversing
# the points in {0, 2, 4, 1, 3} order makes the edges cross, so the
# central pentagon is enclosed twice: nonzero fills it, even-odd holes it.
_STAR_PATH = (
    b"100 180 m\n"
    b"143 47 l\n"
    b"30 129 l\n"
    b"170 129 l\n"
    b"57 47 l\n"
    b"h\n"
)


def _build_concentric_nonzero(path: Path) -> None:
    doc, page = _make_doc()
    _set_contents(page, b"q\n0 0 0 rg\n" + _CONCENTRIC_PATH + b"f\nQ\n")
    _save(doc, path)


def _build_concentric_evenodd(path: Path) -> None:
    doc, page = _make_doc()
    _set_contents(page, b"q\n0 0 0 rg\n" + _CONCENTRIC_PATH + b"f*\nQ\n")
    _save(doc, path)


def _build_star_nonzero(path: Path) -> None:
    doc, page = _make_doc()
    _set_contents(page, b"q\n0 0 0 rg\n" + _STAR_PATH + b"f\nQ\n")
    _save(doc, path)


def _build_star_evenodd(path: Path) -> None:
    doc, page = _make_doc()
    _set_contents(page, b"q\n0 0 0 rg\n" + _STAR_PATH + b"f*\nQ\n")
    _save(doc, path)


def _build_concentric_b_star(path: Path) -> None:
    # ``B*`` — even-odd fill + stroke. Annulus fill plus a stroked outline
    # on both rectangle boundaries.
    doc, page = _make_doc()
    _set_contents(
        page,
        b"q\n0 0 0 rg\n0 0 0 RG\n3 w\n" + _CONCENTRIC_PATH + b"B*\nQ\n",
    )
    _save(doc, path)


_BUILDERS = {
    "concentric_nonzero": _build_concentric_nonzero,
    "concentric_evenodd": _build_concentric_evenodd,
    "star_nonzero": _build_star_nonzero,
    "star_evenodd": _build_star_evenodd,
    "concentric_b_star": _build_concentric_b_star,
}


def _render_py(pdf: Path) -> Image.Image:
    with PDDocument.load(pdf) as doc:
        return PDFRenderer(doc).render_image_with_dpi(0, 72.0)


# --------------------------------------------------------------------------
# differential tests
# --------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_fill_winding_rule_matches_pdfbox(label: str, tmp_path: Path) -> None:
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
        f"(maxdiff={maxdiff}) — fill winding rule diverges, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


@requires_oracle
def test_nonzero_and_evenodd_concentric_render_differently(tmp_path: Path) -> None:
    """Guard: the SAME concentric-rect path filled ``f`` (nonzero) vs
    ``f*`` (even-odd) must render *materially different* from each other.

    This proves the winding rule is honoured rather than always treated
    as nonzero: a bug that ignored ``f*`` would fill both as a solid
    block, the two fingerprints would coincide, and this guard would
    fail. The hole-vs-solid difference sits far over the parity gate."""
    nonzero = tmp_path / "concentric_nonzero.pdf"
    evenodd = tmp_path / "concentric_evenodd.pdf"
    _build_concentric_nonzero(nonzero)
    _build_concentric_evenodd(evenodd)

    nonzero_grid = _grid_from_image(_render_py(nonzero))
    evenodd_grid = _grid_from_image(_render_py(evenodd))
    mad, maxdiff = _diff(nonzero_grid, evenodd_grid)
    assert mad >= _MAD_TOLERANCE and maxdiff >= _MAXDIFF_TOLERANCE, (
        f"fill winding rule not honoured: nonzero ``f`` and even-odd ``f*`` "
        f"of the same concentric-rect path render identically "
        f"(MAD={mad:.2f}, MAXDIFF={maxdiff}) — even-odd is being treated "
        f"as nonzero"
    )
