"""Live Apache PDFBox parity for multi-line text extraction on pages whose
``/Rotate`` is a right angle (0 / 90 / 180 / 270).

This pins the *page-rotation* extraction boundary differentially against Java
PDFBox 3.0.7. The fixture is a single LETTER page painting a heading, two body
lines on the same left margin, an indented (blank-line-separated) paragraph
start and its wrapped continuation — all in **unrotated** user-space
coordinates (identity text matrix), so the only rotation is the page
``/Rotate``. ``RotatedMultiLineProbe build`` produces the PDF with PDFBox
itself (known-good input bytes) and ``RotatedMultiLineProbe extract`` emits
PDFBox's ``PDFTextStripper().getText`` for it.

Why this is the carve-out's real boundary
------------------------------------------
There is **no** ``flip-axes`` concept in upstream PDFBox (a full scan of
``pdfbox-app-3.0.7.jar`` finds no ``setShouldFlipAxes`` / ``flipAxes`` symbol).
``PDFTextStripper.set_should_flip_axes`` is a lite-only *manual* toggle that
transposes X/Y in the line/word heuristics; it is **not** driven by ``/Rotate``
and carries no rotation in the coordinate matrix (``dir`` stays 0, so
``get_x_dir_adj`` / ``get_y_dir_adj`` are identity). It therefore cannot be
unified onto the dir-adjusted ``_classify_paragraph_separation`` path — there is
no rotation in the coordinates for those fields to normalise. The flip-axes
carve-outs documented inline in ``pdf_text_stripper.py`` are correct as-is.

The page-rotation parity surface (closed wave 1495): upstream does **not** fold
``page.getRotation()`` into the CTM (``PDPage.getMatrix()`` returns the identity
— PDPage.java:385-389); instead every ``TextPosition`` is constructed with the
page rotation + page dimensions (``LegacyPDFStreamEngine.showGlyph`` →
``new TextPosition(pageRotation, …)``) and the page-rotation-adjusted
coordinates are derived by ``TextPosition``'s ``getX``/``getY``/``getWidth``
(via ``getXRot``/``getYLowerLeftRot``/``getWidthRot``). The default extraction
path (``sortByPosition`` false) groups on exactly those accessors
(PDFTextStripper.java:585-591), so a rotated page's glyphs land in the rotated
*device* frame.

pypdfbox now reproduces this with ``PDFTextStripper._apply_page_rotation``: a
per-page post-pass that rewrites each run's stored ``x``/``y``/``width`` into
the page-rotation-adjusted frame, plus per-glyph emission on 90/270 pages so
the rotated rows fragment glyph-by-glyph the way upstream's per-glyph
``showGlyph`` feeds ``writePage``. Result:

* **rot0 / rot180** — byte-exact (the fold is a verbatim no-op for rot0; rot180
  re-points the coordinates but the grouping is unchanged).
* **rot90 / rot270** — byte-exact: the rotated rows fragment exactly as Java
  does (the 90 and 270 patterns differ because upstream's ``maxYForLine`` line
  accumulation is not symmetric under the rotation direction).

``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_PROBE = "RotatedMultiLineProbe"


def _build(tmp_path: Path, rotate: int) -> Path:
    out = tmp_path / f"rotated_multiline_{rotate}.pdf"
    run_probe(_PROBE, "build", str(out), str(rotate))
    return out


def _py_extract(src: Path) -> str:
    with PDDocument.load(src) as doc:
        return PDFTextStripper().get_text(doc)


def _java_extract(src: Path) -> str:
    return run_probe_text(_PROBE, "extract", str(src))


# ---------------------------------------------------------------------------
# rot0 / rot180 — byte-exact parity (no re-flow on either side)
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("rotate", [0, 180])
def test_unflipped_rotation_extraction_byte_exact(
    tmp_path: Path, rotate: int
) -> None:
    src = _build(tmp_path, rotate)
    java = _java_extract(src)
    py = _py_extract(src)
    assert py == java


@requires_oracle
def test_rot0_multiline_layout_preserved(tmp_path: Path) -> None:
    """The unrotated baseline keeps the heading, two body lines, the
    indented paragraph break and its wrap as distinct lines — the layout
    the lite stripper reproduces at full parity."""
    src = _build(tmp_path, 0)
    py = _py_extract(src)
    assert py == (
        "Heading Title\n"
        "First body line here\n"
        "Second body line continues\n"
        "Indented new paragraph begins\n"
        "and wraps onto the next line\n"
    )


# ---------------------------------------------------------------------------
# rot90 / rot270 — byte-exact parity (page-rotation fold, wave 1495)
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("rotate", [90, 270])
def test_right_angle_rotation_byte_exact(tmp_path: Path, rotate: int) -> None:
    """Page-rotation parity for the right angles (closed wave 1495).

    The lite stripper now folds the page ``/Rotate`` into each run's stored
    coordinates (``PDFTextStripper._apply_page_rotation``), reproducing
    upstream's default-path grouping on the page-rotation-adjusted
    ``getX()``/``getY()``/``getWidth()`` (PDFTextStripper.java:585-591). On a
    90/270 page a horizontal row therefore advances along the grouping's line
    axis with zero rotated width, fragmenting the row exactly the way Apache
    PDFBox does — byte-for-byte. (The fragmentation pattern differs between 90
    and 270 because upstream's ``maxYForLine`` line accumulation is not
    symmetric under the rotation direction; both reproduced.)
    """
    src = _build(tmp_path, rotate)
    java = _java_extract(src)
    py = _py_extract(src)
    assert py == java
    # Sanity: the rotated rows really are fragmented in the device frame (not
    # the upright text), so this is a true device-frame parity rather than an
    # accidental match against the rot0 layout.
    assert java != (
        "Heading Title\n"
        "First body line here\n"
        "Second body line continues\n"
        "Indented new paragraph begins\n"
        "and wraps onto the next line\n"
    )


@requires_oracle
@pytest.mark.parametrize("rotate", [90, 270])
def test_right_angle_rotation_no_glyph_dropped(tmp_path: Path, rotate: int) -> None:
    """The page-rotation fold only regroups glyphs — it never drops one.

    The whitespace-stripped payload of the rotated extraction equals the
    upright (rot0) payload, guarding against a fold bug that silently loses a
    glyph while still matching Java's (also-fragmented) output.
    """
    src = _build(tmp_path, rotate)
    py = _py_extract(src)
    upright = (
        "Heading Title"
        "First body line here"
        "Second body line continues"
        "Indented new paragraph begins"
        "and wraps onto the next line"
    )
    assert "".join(py.split()) == "".join(upright.split())
