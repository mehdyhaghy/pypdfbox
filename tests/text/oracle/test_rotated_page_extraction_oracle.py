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

The actionable ``/Rotate`` parity gap is a *different* surface: upstream's
``LegacyPDFStreamEngine`` folds ``page.getRotation()`` into the CTM
(``LegacyPDFStreamEngine`` ``pageRotation`` + ``translateMatrix``), so a
rotated page's TextPositions arrive in the *device* (rotated) frame. pypdfbox's
``LegacyPDFStreamEngine.process_page`` reads ``get_rotation()`` but does **not**
build that rotation matrix (only a cropbox translate), so glyphs stay in raw
user space. Consequences pinned below:

* **rot0 / rot180** — both engines land identical text. The 180 case matches
  because neither side re-flows it (upstream's 180 CTM keeps the line-flow axis
  vertical, and the lite raw-user-space path is already upright).
* **rot90 / rot270** — Java fragments the lines (its device-frame line grouping
  splits each rotated row mid-word, e.g. ``"H\neading T\nitle\n…"``), while the
  lite stripper emits clean upright text. This is the documented missing
  page-rotation CTM fold (see DEFERRED.md), tracked, not yet closed. Asserted
  here as a *both-sides* divergence pin so the gap is visible and a future
  CTM-fold fix has a regression target.

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
# rot90 / rot270 — documented divergence (missing page-rotation CTM fold)
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("rotate", [90, 270])
def test_right_angle_rotation_diverges_pending_ctm_fold(
    tmp_path: Path, rotate: int
) -> None:
    """Both-sides pin for the page-rotation CTM-fold gap (DEFERRED.md).

    Java fragments the rotated rows in its device frame; the lite stripper
    keeps clean upright text. We assert *both* sides explicitly so that
    closing the gap (folding ``page.getRotation()`` into the CTM in
    ``LegacyPDFStreamEngine``) flips this from a divergence pin into a
    parity pin — and so an accidental re-flow change on either engine
    trips the test rather than silently passing.
    """
    src = _build(tmp_path, rotate)
    java = _java_extract(src)
    py = _py_extract(src)
    # Lite stripper: clean upright text (raw user-space coordinates).
    assert py == (
        "Heading Title\n"
        "First body line here\n"
        "Second body line continues\n"
        "Indented new paragraph begins\n"
        "and wraps onto the next line\n"
    )
    # Java: device-frame line grouping fragments the rotated rows.
    assert java != py
    # The same glyphs survive on both sides — only the line grouping
    # differs (guards against the divergence masking a dropped glyph).
    assert java.replace("\n", "") == py.replace("\n", "")
