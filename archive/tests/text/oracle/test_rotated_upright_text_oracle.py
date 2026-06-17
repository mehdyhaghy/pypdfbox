"""Live Apache PDFBox parity for the *upright-reading* rotated-page case.

This is the common real-world rotated document: the page ``/Rotate`` is a
right angle AND the text matrix is counter-rotated by the same angle so the
text reads upright once a viewer applies the page rotation (e.g. a portrait
scan stored sideways). Unlike ``RotatedMultiLineProbe`` — which paints
*unrotated* (identity-``Tm``) text on a ``/Rotate`` page and so fragments in
the device frame — here ``getDir()`` equals the page rotation and the
direction-adjusted coordinates reconstruct the upright reading order, so both
engines extract clean, byte-identical multi-line text at every rotation.

Pins the wave-1495 page-rotation fold (``PDFTextStripper._apply_page_rotation``)
against the live oracle for the upright case at /Rotate 0/90/180/270.

``@requires_oracle`` so it skips cleanly without Java + the jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

_PROBE = "RotatedUprightTextProbe"


def _build(tmp_path: Path, rotate: int) -> Path:
    out = tmp_path / f"rotated_upright_{rotate}.pdf"
    run_probe(_PROBE, "build", str(out), str(rotate))
    return out


def _py_extract(src: Path) -> str:
    with PDDocument.load(src) as doc:
        return PDFTextStripper().get_text(doc)


def _java_extract(src: Path) -> str:
    return run_probe_text(_PROBE, "extract", str(src))


@requires_oracle
@pytest.mark.parametrize("rotate", [0, 90, 180, 270])
def test_upright_rotated_text_byte_exact(tmp_path: Path, rotate: int) -> None:
    """Upright-reading rotated text extracts byte-identically to Java at
    every right-angle ``/Rotate`` — the page rotation is reconstructed into
    the upright reading order by the wave-1495 coordinate fold."""
    src = _build(tmp_path, rotate)
    java = _java_extract(src)
    py = _py_extract(src)
    assert py == java


@requires_oracle
@pytest.mark.parametrize("rotate", [0, 90, 180, 270])
def test_upright_rotated_text_keeps_three_lines(tmp_path: Path, rotate: int) -> None:
    """The upright block stays three distinct reading lines at every
    rotation (no device-frame fragmentation, unlike the identity-Tm case)."""
    src = _build(tmp_path, rotate)
    py = _py_extract(src)
    assert py == (
        "Upright heading line\n"
        "Second upright line\n"
        "Third upright line here\n"
    )
