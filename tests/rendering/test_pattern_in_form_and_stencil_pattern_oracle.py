"""Live differential for the PDFBOX-5250 / PDFBOX-6077 forward-ports.

The oracle jar is PDFBox 3.0.8, which predates both fixes:

* a pattern inside a *plain* form XObject was already anchored to the form
  space in 3.0.8, so pypdfbox must agree with the oracle there;
* inside a *transparency group* 3.0.8 still anchored the pattern to the
  parent space (PDFBOX-5250), so pypdfbox intentionally diverges and renders
  the group exactly like the plain form;
* a stencil mask filled with a gapped tiling pattern painted the gaps opaque
  black in 3.0.8 (PDFBOX-6077), so pypdfbox intentionally diverges there and
  leaves the gaps white, while agreeing on the masked-out half.

Uses ``RenderProbe`` (16x16 grid of average luminance at 72 dpi).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from tests.oracle.harness import requires_oracle, run_probe_text
from tests.rendering import test_pattern_in_form_and_stencil_pattern as synth

_GRID = 16


def _java_grid(pdf: bytes, tmp_path: Path, name: str) -> np.ndarray:
    path = tmp_path / f"{name}.pdf"
    path.write_bytes(pdf)
    lines = run_probe_text("RenderProbe", str(path), "0").strip().splitlines()
    return np.array([int(v) for v in lines[1].split()]).reshape(_GRID, _GRID)


def _py_grid(pdf: bytes) -> np.ndarray:
    image = np.asarray(synth._render(pdf).convert("L"), dtype=np.float64)
    height, width = image.shape
    grid = np.zeros((_GRID, _GRID))
    for row in range(_GRID):
        for col in range(_GRID):
            y0, y1 = row * height // _GRID, (row + 1) * height // _GRID
            x0, x1 = col * width // _GRID, (col + 1) * width // _GRID
            grid[row, col] = image[y0:y1, x0:x1].mean()
    return np.rint(grid).astype(int)


@requires_oracle
def test_pattern_in_plain_form_matches_pdfbox(tmp_path: Path) -> None:
    pdf = synth._pattern_in_form_pdf(synth._SPLIT_TILE, group=False)
    java = _java_grid(pdf, tmp_path, "plain")
    py = _py_grid(pdf)
    assert np.abs(java - py).max() <= 8


@requires_oracle
def test_pattern_in_transparency_group_diverges_from_308(tmp_path: Path) -> None:
    group_pdf = synth._pattern_in_form_pdf(synth._SPLIT_TILE, group=True)
    plain_pdf = synth._pattern_in_form_pdf(synth._SPLIT_TILE, group=False)
    java_group = _java_grid(group_pdf, tmp_path, "group")
    java_plain = _java_grid(plain_pdf, tmp_path, "plain")
    py_group = _py_grid(group_pdf)
    # Intentional divergence (PDFBOX-5250 forward-port): 3.0.8 renders the
    # group differently from the plain form; pypdfbox renders them alike and
    # matches 3.0.8's plain-form output.
    assert np.abs(java_group - java_plain).max() > 40
    assert np.abs(py_group - java_plain).max() <= 8


@requires_oracle
def test_stencil_with_gapped_pattern_diverges_only_in_gaps(tmp_path: Path) -> None:
    pdf = synth._stencil_pdf(synth._GAPPED_TILE)
    java = _java_grid(pdf, tmp_path, "stencil")
    py = _py_grid(pdf)
    # The masked-out right half of the image (page x 50..100, grid columns
    # 4..7) and everything outside the image agree with 3.0.8.
    outside = np.ones((_GRID, _GRID), dtype=bool)
    outside[8:16, 0:4] = False
    assert np.abs(java[outside] - py[outside]).max() <= 8
    # Intentional divergence (PDFBOX-6077 forward-port): inside the painted
    # half 3.0.8 turns the gaps between tiles opaque black, pypdfbox keeps
    # them transparent, so the area is markedly lighter.
    lighter = py[8:16, 0:4] - java[8:16, 0:4]
    assert lighter.min() > 20
    assert lighter.mean() > 80


@requires_oracle
def test_small_stencil_with_pattern_polarity_matches_pdfbox(tmp_path: Path) -> None:
    pdf = synth._stencil_pdf(synth._GAPPED_TILE, stencil=synth._SMALL_STENCIL)
    java = _java_grid(pdf, tmp_path, "small_stencil")
    py = _py_grid(pdf)
    # Upstream's small-mask branch paints the decoded-1 sample (right half,
    # grid columns 4..7); the left half stays white in both renderers.
    painted = np.zeros((_GRID, _GRID), dtype=bool)
    painted[8:16, 4:8] = True
    assert np.abs(java[~painted] - py[~painted]).max() <= 8
    assert (java[painted] < 128).all()
    assert (py[painted] < 255).all()
