"""Live PDFBox differential parity for ``Splitter``'s inherited page-geometry
*materialisation* (``pypdfbox.multipdf.splitter.Splitter``).

Upstream ``Splitter.processPage`` drives ``PDDocument.importPage``, which
re-applies ``setCropBox`` / ``setMediaBox`` / ``setRotation`` from the
*resolved* source values right after detaching the page from its parent tree
(PDDocument.java lines 700-702). So a page that inherited its ``/MediaBox`` /
``/CropBox`` / ``/Rotate`` from a page-tree node still carries concrete values
materialised on its own dict in every split chunk.

pypdfbox's ``PDDocument.import_page`` does a deep-copy + ``/Parent`` strip but
does *not* re-apply those three setters, so wave 1505 added the materialisation
to ``Splitter.process_page`` to close the divergence. This module pins the
result against the Java oracle: for every page of every split part the resolved
MediaBox + CropBox rectangle, the resolved ``/Rotate``, and whether the geometry
keys are materialised directly on the page dict must match PDFBox exactly.

Companion to ``test_splitter_oracle.py`` (partition shape + first-page identity)
and ``test_split_content_oracle.py`` (per-page text); this one pins geometry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pypdfbox.cos import COSName
from pypdfbox.multipdf.splitter import Splitter
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "multipdf"

# (id, fixture, split_at). Chosen to exercise both an inherited-/MediaBox page
# (OrphanPopups, /MediaBox lives on the page-tree node) and a multi-page split
# with per-page rotation that must ride along into each chunk (PDFBOX-6049).
_CASES = [
    ("inherited_mediabox_every1", "PDFBOX-6018-099267-p9-OrphanPopups.pdf", 1),
    ("rotated_every3", "PDFBOX-6049-Source.pdf", 3),
    ("rotated_every1", "PDFBOX-6049-Source.pdf", 1),
    ("rotated_oversize", "PDFBOX-6049-Source.pdf", 99),
]

_MEDIA_BOX = COSName.get_pdf_name("MediaBox")
_CROP_BOX = COSName.get_pdf_name("CropBox")


def _round_rect(rect: object) -> list[int]:
    """Round a PDRectangle to ``[x, y, w, h]`` ints — mirrors the probe's
    ``Math.round`` so the comparison is stable across float formatting."""
    return [
        round(rect.get_lower_left_x()),  # type: ignore[attr-defined]
        round(rect.get_lower_left_y()),  # type: ignore[attr-defined]
        round(rect.get_width()),  # type: ignore[attr-defined]
        round(rect.get_height()),  # type: ignore[attr-defined]
    ]


def _split_py(src_path: Path, split_at: int) -> list[dict]:
    """Split ``src_path`` through pypdfbox; return the same per-part / per-page
    geometry shape the Java probe emits."""
    source = PDDocument.load(src_path)
    try:
        splitter = Splitter()
        splitter.set_split_at_page(split_at)
        parts = splitter.split(source)
        try:
            result: list[dict] = []
            for part in parts:
                pages: list[dict] = []
                for i in range(part.get_number_of_pages()):
                    page = part.get_page(i)
                    page_cos = page.get_cos_object()
                    pages.append(
                        {
                            "mb": _round_rect(page.get_media_box()),
                            "cb": _round_rect(page.get_crop_box()),
                            "rot": page.get_rotation(),
                            "mbKey": page_cos.contains_key(_MEDIA_BOX),
                            "cbKey": page_cos.contains_key(_CROP_BOX),
                        }
                    )
                result.append({"pages": pages})
            return result
        finally:
            for part in parts:
                part.close()
    finally:
        source.close()


@requires_oracle
@pytest.mark.parametrize(
    ("case_id", "name", "split_at"),
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_split_inherited_geometry_matches_pdfbox(
    case_id: str, name: str, split_at: int
) -> None:
    src = _FIXTURES / name
    if not src.is_file():
        pytest.skip(f"fixture missing: {src}")

    java_parts = json.loads(
        run_probe_text("SplitterInheritProbe", str(src), str(split_at))
    )["parts"]
    py_parts = _split_py(src, split_at)

    assert py_parts == java_parts, (
        f"split inherited-geometry divergence for {case_id}:\n"
        f"  pypdfbox: {json.dumps(py_parts)}\n"
        f"  PDFBox:   {json.dumps(java_parts)}"
    )

    # Explicit signal: every page in every part carries a materialised
    # /MediaBox key (upstream importPage's setMediaBox), so the chunk is
    # self-sufficient even when the source page inherited its box.
    for part in py_parts:
        for page in part["pages"]:
            assert page["mbKey"] is True, (
                f"{case_id}: split page lost its materialised /MediaBox key"
            )
