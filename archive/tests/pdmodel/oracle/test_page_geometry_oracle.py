"""Live PDFBox differential parity for page-tree geometry.

Every field here is **exact-match**: page count, the resolved ``/MediaBox``
and ``/CropBox`` (four floats each, after inheritable-attribute resolution
and clip-to-media-box), the normalised ``/Rotate`` degree, and the per-page
``/Font`` and ``/XObject`` resource name counts. A mismatch on any of these
is a real bug — there is no rendering/anti-aliasing slack to hide behind, so
we assert byte-for-byte against Apache PDFBox's own accessors.

The Java side is ``oracle/probes/PageGeomProbe.java``: it reads
``PDPage.getMediaBox()`` / ``getCropBox()`` (which walk the ``/Parent`` chain
exactly like our :class:`PDPage`), ``getRotation()``, and the resolved
``PDResources`` font/xobject name sets. Floats are rendered canonically
(integral values without a trailing ``.0``); we render the Python floats with
the same rule so the string comparison is exact.

Fixtures are chosen to vary the geometry: every ``/Rotate`` quadrant
(0/90/180/270 — exercises the normalisation), a multi-page document, an
inheritable-attribute page tree (``page_tree_multiple_levels`` — MediaBox
inherited from an intermediate node), and a fractional MediaBox
(``BidiSample`` at 595.28 x 841.89 — exercises non-integral float parity).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

# (relative fixture path, human label)
_CASES = [
    ("multipdf/rot0.pdf", "rotate_0"),
    ("multipdf/rot90.pdf", "rotate_90"),
    ("multipdf/rot180.pdf", "rotate_180"),
    ("multipdf/rot270.pdf", "rotate_270"),
    ("multipdf/PDFBOX-5811-362972.pdf", "multi_page_with_image"),
    ("pdmodel/page_tree_multiple_levels.pdf", "inheritable_page_tree"),
    ("text/BidiSample.pdf", "fractional_mediabox"),
    ("pdfwriter/unencrypted.pdf", "writer_two_page"),
]


def _fmt(value: float) -> str:
    """Canonical float rendering matching ``PageGeomProbe.fmt``: integral
    values print without a trailing ``.0``; non-integral values print with
    up to 4 decimals, trailing zeros stripped."""
    if value == int(value):
        return str(int(value))
    s = f"{value:.4f}".rstrip("0").rstrip(".")
    return s


def _box(rect: object) -> str:
    return (
        f"{_fmt(rect.lower_left_x)} {_fmt(rect.lower_left_y)} "  # type: ignore[attr-defined]
        f"{_fmt(rect.upper_right_x)} {_fmt(rect.upper_right_y)}"  # type: ignore[attr-defined]
    )


def _py_geometry(fixture: Path) -> str:
    """Build the same multi-line geometry report the Java probe emits."""
    lines: list[str] = []
    doc = PDDocument.load(fixture)
    try:
        count = doc.get_number_of_pages()
        lines.append(f"pages {count}")
        for i in range(count):
            page = doc.get_page(i)
            media = page.get_media_box()
            crop = page.get_crop_box()
            rotate = page.get_rotation()
            res = page.get_resources()
            fonts = len(res.get_font_names())
            xobjects = len(res.get_x_object_names())
            lines.append(
                f"page {i} media {_box(media)} crop {_box(crop)} "
                f"rotate {rotate} fonts {fonts} xobjects {xobjects}"
            )
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


@requires_oracle
@pytest.mark.parametrize(
    ("rel_path", "label"),
    _CASES,
    ids=[c[1] for c in _CASES],
)
def test_page_geometry_matches_pdfbox(rel_path: str, label: str) -> None:
    fixture = _FIXTURES / rel_path
    java = run_probe_text("PageGeomProbe", str(fixture))
    py = _py_geometry(fixture)
    assert py == java, (
        f"{label}: page geometry diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )
