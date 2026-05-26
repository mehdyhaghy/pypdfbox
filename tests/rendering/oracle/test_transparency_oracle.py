"""Live PDFBox differential parity for ExtGState transparency compositing.

Covers the three transparency mechanisms an ExtGState (``gs`` operator) can
introduce on top of plain opaque painting (PDF 32000-1 §11.3 / §11.6.4 /
§11.6.5.3):

* **Separable blend modes** (``/BM``, §11.3.5.1) — a green rectangle painted
  over a magenta base under ``Multiply`` / ``Screen``. The overlap must show
  the blended colour, not the opaque top (blend ignored) and not the base
  (top dropped).
* **Constant alpha** (``/ca``, §11.6.4.3) — a yellow rectangle painted with
  ``ca 0.5`` over an opaque blue base, so the overlap is the 50/50 mix of the
  two, not the opaque yellow top.
* **Luminosity soft mask** (``/SMask`` with ``/S /Luminosity``, §11.6.5.3) — a
  full-page near-black fill gated by a luminosity mask group whose left strip
  is white (alpha 1, painted) and whose rest is the black backdrop (alpha 0,
  masked out), over a yellow page. Only the left strip should show the dark
  fill; the rest stays yellow.

Pixel-EXACT parity is impossible (Pillow vs Java2D anti-aliasing — see
``CHANGES.md`` / ``test_render_oracle.py``), so we compare the same coarse
fingerprint the page-render oracle uses: exact rendered dimensions plus a
16x16 average-luminance grid, gated at ``MAD < 6`` / ``MAXDIFF < 60`` against
``oracle/probes/RenderProbe.java`` (renders the page at 72 DPI). The gate is
the proven discriminator from ``test_render_oracle.py``. Measured here, every
correct transparency render lands at MAD <= 0.0 / MAXDIFF <= 0 (the
fixtures are flat-colour so AA contributes nothing), while disabling the
mechanism (``ca 1.0`` instead of ``0.5``, or stripping the ``/SMask``) lands
far outside the gate — proven by the dedicated guard tests below
(``ca 1.0`` vs the ``ca 0.5`` oracle scores MAD~25; an ignored luminosity
SMask scores MAD~130).

Fixtures are synthesised in-memory via pypdfbox's own content-stream / COS
API (no bundled corpus carries all three over a coloured backdrop), so the
test is self-contained and commits no binaries.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer
from tests.oracle.harness import requires_oracle, run_probe_text

_GRID = 16
# Same gate as test_render_oracle.py — comfortably above the AA ceiling
# (correct transparency renders measure MAD<=0.0 on these flat fixtures) yet
# well below the gross-failure floor (a disabled mechanism = MAD 25-130).
_MAD_TOLERANCE = 6.0
_MAXDIFF_TOLERANCE = 60

_MB = 100  # media-box side, pt (== px at 72 DPI)


def _grid_from_image(img: Image.Image) -> list[int]:
    """16x16 average-luminance fingerprint — identical cell mapping to
    ``RenderProbe.java`` (integer-division of pixel coord over image size,
    clamped to the last cell)."""
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


def _assert_parity(label: str, fixture: Path) -> None:
    """Render ``fixture`` via Java + pypdfbox at 72 DPI and assert exact dims
    plus 16x16 luminance-grid parity within the MAD/MAXDIFF gate."""
    (java_w, java_h), java_grid = _oracle_signature(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_w, py_h = img.size
    py_grid = _grid_from_image(img)

    # (a) Exact pixel dimensions — a mismatch is a real bug, not AA.
    assert (py_w, py_h) == (java_w, java_h), (
        f"{label}: rendered dimensions diverge from PDFBox: "
        f"pypdfbox={py_w}x{py_h} java={java_w}x{java_h}"
    )

    # (b) Perceptual grid parity within tolerance. A blend/alpha/mask that is
    # ignored, dropped, or computed with the wrong formula lands far outside
    # this gate (see the guard tests below).
    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    maxdiff = max(diffs)
    assert mad < _MAD_TOLERANCE, (
        f"{label}: mean abs cell diff {mad:.2f} >= {_MAD_TOLERANCE} "
        f"(maxdiff={maxdiff}) — transparency ignored/wrong, not just AA"
    )
    assert maxdiff < _MAXDIFF_TOLERANCE, (
        f"{label}: worst cell diff {maxdiff} >= {_MAXDIFF_TOLERANCE} "
        f"(mad={mad:.2f}) — a region diverges far beyond anti-aliasing"
    )


# ---------------------------------------------------------------------------
# (a) Separable blend modes — /BM
# ---------------------------------------------------------------------------

# Magenta base + green top: chosen so the §11.3.5 blended luminance differs
# materially from the opaque-top luminance for both modes here.
_BLEND_BASE_RGB = (0.9, 0.15, 0.9)
_BLEND_TOP_RGB = (0.55, 0.9, 0.55)
_BLEND_MODES = ["Multiply", "Screen"]


def _build_blend_fixture(path: Path, mode: str) -> None:
    """Magenta base rect over the whole page, then a green rect painted under
    ``mode`` (set via an ExtGState ``/BM``) overlapping the centre."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)
    cs = PDPageContentStream(doc, page)
    cs.set_non_stroking_color(*_BLEND_BASE_RGB)
    cs.add_rect(0, 0, _MB, _MB)
    cs.fill()
    cs.set_blend_mode(mode)
    cs.set_non_stroking_color(*_BLEND_TOP_RGB)
    cs.add_rect(20, 20, 60, 60)
    cs.fill()
    cs.close()
    doc.save(str(path))
    doc.close()


@requires_oracle
@pytest.mark.parametrize("mode", _BLEND_MODES, ids=_BLEND_MODES)
def test_blend_mode_render_matches_pdfbox(mode: str, tmp_path: Path) -> None:
    fixture = tmp_path / f"blend_{mode}.pdf"
    _build_blend_fixture(fixture, mode)
    _assert_parity(f"blend/{mode}", fixture)


@requires_oracle
def test_blend_overlap_is_actually_multiplied(tmp_path: Path) -> None:
    """Direct-pixel companion to the fingerprint gate: the Multiply overlap
    centre must equal the per-channel product of base and top — not the
    opaque top (blend ignored) and not the unchanged base (top dropped)."""
    fixture = tmp_path / "blend_Multiply.pdf"
    _build_blend_fixture(fixture, "Multiply")

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    cr, cg, cb = img.getpixel((50, 50))  # centre of the 60x60 top rect

    exp = tuple(
        round(_BLEND_BASE_RGB[i] * _BLEND_TOP_RGB[i] * 255) for i in range(3)
    )
    top = tuple(round(_BLEND_TOP_RGB[i] * 255) for i in range(3))
    base = tuple(round(_BLEND_BASE_RGB[i] * 255) for i in range(3))

    assert all(abs((cr, cg, cb)[i] - exp[i]) <= 4 for i in range(3)), (
        f"Multiply overlap pixel {(cr, cg, cb)} != expected blended {exp}"
    )
    assert (cr, cg, cb) != top, "overlap shows opaque top — blend was ignored"
    assert (cr, cg, cb) != base, "overlap shows base — top was dropped"


# ---------------------------------------------------------------------------
# (b) Constant alpha — /ca
# ---------------------------------------------------------------------------

_CA_BASE_RGB = (0.1, 0.2, 0.9)  # opaque blue base
_CA_TOP_RGB = (0.95, 0.85, 0.1)  # yellow top, painted at /ca


def _build_constant_alpha_fixture(path: Path, alpha: float) -> None:
    """Opaque blue base over the page, then a yellow rect painted under an
    ExtGState ``/ca`` constant alpha overlapping the centre."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)
    cs = PDPageContentStream(doc, page)
    cs.set_non_stroking_color(*_CA_BASE_RGB)
    cs.add_rect(0, 0, _MB, _MB)
    cs.fill()
    cs.set_non_stroking_alpha_constant(alpha)
    cs.set_non_stroking_color(*_CA_TOP_RGB)
    cs.add_rect(20, 20, 60, 60)
    cs.fill()
    cs.close()
    doc.save(str(path))
    doc.close()


@requires_oracle
def test_constant_alpha_render_matches_pdfbox(tmp_path: Path) -> None:
    fixture = tmp_path / "ca_half.pdf"
    _build_constant_alpha_fixture(fixture, 0.5)
    _assert_parity("ca/0.5", fixture)


@requires_oracle
def test_constant_alpha_overlap_is_actually_blended(tmp_path: Path) -> None:
    """The ``ca 0.5`` overlap must equal the 50/50 mix of top over base
    (``out = top*ca + base*(1-ca)``) — not the opaque top (alpha ignored)
    and not the unchanged base (fill dropped)."""
    fixture = tmp_path / "ca_half.pdf"
    _build_constant_alpha_fixture(fixture, 0.5)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    cr, cg, cb = img.getpixel((50, 50))

    exp = tuple(
        round((_CA_TOP_RGB[i] * 0.5 + _CA_BASE_RGB[i] * 0.5) * 255)
        for i in range(3)
    )
    top = tuple(round(_CA_TOP_RGB[i] * 255) for i in range(3))
    base = tuple(round(_CA_BASE_RGB[i] * 255) for i in range(3))

    assert all(abs((cr, cg, cb)[i] - exp[i]) <= 4 for i in range(3)), (
        f"ca=0.5 overlap pixel {(cr, cg, cb)} != expected mix {exp}"
    )
    assert (cr, cg, cb) != top, "overlap shows opaque top — alpha was ignored"
    assert (cr, cg, cb) != base, "overlap shows base — fill was dropped"


@requires_oracle
def test_opaque_alpha_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: rendering the same geometry with ``ca 1.0`` (opaque
    top, alpha disabled) must land outside tolerance versus the ``ca 0.5``
    oracle, proving the gate detects an ignored constant alpha rather than
    passing everything."""
    half = tmp_path / "ca_half.pdf"
    _build_constant_alpha_fixture(half, 0.5)
    _dims, java_grid = _oracle_signature(half)

    opaque = tmp_path / "ca_one.pdf"
    _build_constant_alpha_fixture(opaque, 1.0)
    with PDDocument.load(opaque) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_grid = _grid_from_image(img)

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: an ignored constant alpha passes the MAD gate"
    )


# ---------------------------------------------------------------------------
# (c) Luminosity soft mask — /SMask with /S /Luminosity
# ---------------------------------------------------------------------------

_SMASK_BACKDROP_RGB = (0.95, 0.9, 0.1)  # yellow page fill
_SMASK_FILL_RGB = (0.1, 0.1, 0.1)  # near-black fill, gated by the mask


def _build_luminosity_smask_fixture(path: Path) -> None:
    """Yellow full-page backdrop, then a full-page near-black fill painted
    through a luminosity ``/SMask`` whose mask group is black (alpha 0,
    matching ``/BC`` 0) except a white left strip (alpha 1). Only the left
    strip therefore shows the dark fill; the rest keeps the yellow backdrop."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0, 0, _MB, _MB))
    doc.add_page(page)

    # Luminosity mask group: black over the whole page, white in the left
    # strip (x in 0..30). White luminance → alpha 1; black → alpha 0 (== /BC).
    mask_stream = COSStream()
    mask_stream.set_raw_data(
        b"0 0 0 rg\n0 0 100 100 re\nf\n"
        b"1 1 1 rg\n0 0 30 100 re\nf\n"
    )
    mask_form = PDFormXObject(mask_stream)
    mask_form.set_b_box(PDRectangle(0, 0, _MB, _MB))
    group = COSDictionary()
    group.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
    mask_form.set_group(group)

    smask = COSDictionary()
    smask.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Luminosity"))
    smask.set_item(COSName.get_pdf_name("G"), mask_form.get_cos_object())
    bc = COSArray()
    for v in (0.0, 0.0, 0.0):
        bc.add(COSFloat(v))
    smask.set_item(COSName.get_pdf_name("BC"), bc)

    egs = COSDictionary()
    egs.set_item(COSName.get_pdf_name("SMask"), smask)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("ExtGState"), COSName.get_pdf_name("GS0"), egs
    )

    contents = COSStream()
    contents.set_raw_data(
        b"0.95 0.9 0.1 rg\n0 0 100 100 re\nf\n"
        b"q\n/GS0 gs\n0.1 0.1 0.1 rg\n0 0 100 100 re\nf\nQ\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    doc.save(str(path))
    doc.close()


@requires_oracle
def test_luminosity_smask_render_matches_pdfbox(tmp_path: Path) -> None:
    fixture = tmp_path / "smask_lum.pdf"
    _build_luminosity_smask_fixture(fixture)
    _assert_parity("smask/luminosity", fixture)


@requires_oracle
def test_luminosity_smask_gates_the_fill(tmp_path: Path) -> None:
    """Direct-pixel companion: the masked-in left strip shows the near-black
    fill (mask white → alpha 1) while the masked-out region keeps the yellow
    backdrop (mask black → alpha 0 == /BC)."""
    fixture = tmp_path / "smask_lum.pdf"
    _build_luminosity_smask_fixture(fixture)

    with PDDocument.load(fixture) as doc:
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0).convert("RGB")
    left = img.getpixel((15, 50))  # mask white → fill visible
    right = img.getpixel((70, 50))  # mask black → backdrop visible

    fill = tuple(round(_SMASK_FILL_RGB[i] * 255) for i in range(3))
    backdrop = tuple(round(_SMASK_BACKDROP_RGB[i] * 255) for i in range(3))
    assert all(abs(left[i] - fill[i]) <= 6 for i in range(3)), (
        f"masked-in strip {left} != gated fill {fill}"
    )
    assert all(abs(right[i] - backdrop[i]) <= 6 for i in range(3)), (
        f"masked-out region {right} != backdrop {backdrop}"
    )


@requires_oracle
def test_ignored_luminosity_smask_would_fail_tolerance(tmp_path: Path) -> None:
    """Guard the gate: rendering the luminosity-SMask fixture with the
    ``/SMask`` entry stripped (fill painted fully opaque everywhere) must land
    outside tolerance, proving the gate detects an ignored soft mask rather
    than passing everything."""
    fixture = tmp_path / "smask_lum.pdf"
    _build_luminosity_smask_fixture(fixture)
    _dims, java_grid = _oracle_signature(fixture)

    smask_key = COSName.get_pdf_name("SMask")
    resources_key = COSName.get_pdf_name("Resources")
    ext_g_state_key = COSName.get_pdf_name("ExtGState")
    with PDDocument.load(fixture) as doc:
        page = doc.get_page(0)
        egs = page.get_cos_object().get_dictionary_object(
            resources_key
        ).get_dictionary_object(ext_g_state_key)
        for key in list(egs.key_set()):
            gs = egs.get_dictionary_object(key)
            if gs.get_dictionary_object(smask_key) is not None:
                gs.remove_item(smask_key)
        img = PDFRenderer(doc).render_image_with_dpi(0, 72.0)
    py_grid = _grid_from_image(img)

    diffs = [abs(a - b) for a, b in zip(java_grid, py_grid, strict=True)]
    mad = sum(diffs) / len(diffs)
    assert mad >= _MAD_TOLERANCE, (
        "tolerance too loose: an ignored luminosity SMask passes the MAD gate"
    )
