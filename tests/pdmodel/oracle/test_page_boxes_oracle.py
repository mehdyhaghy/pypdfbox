"""Live PDFBox differential parity for page boundary boxes.

Covers the full ``PDPage`` box surface — ``/MediaBox``, ``/CropBox``,
``/BleedBox``, ``/TrimBox``, ``/ArtBox`` and ``/UserUnit`` — including the
spec default-and-clip rules that the public getters apply:

* ``getCropBox()``  — ``/CropBox`` (inheritable) clipped to the MediaBox,
  else the MediaBox itself.
* ``getBleedBox()`` / ``getTrimBox()`` / ``getArtBox()`` — the respective own
  entry clipped to the MediaBox, else the (already-resolved) CropBox.
* ``getUserUnit()`` — ``/UserUnit`` defaulting to ``1.0``; non-positive
  values fall back to ``1.0``.

Each box is **exact-match**: four floats after default + clip + inheritable
resolution. There is no rendering slack here, so we assert byte-for-byte
against Apache PDFBox's own accessors via ``oracle/probes/PageBoxProbe.java``.

The fixtures are built programmatically (one PDF per rule) so we control the
exact COS layout that triggers each branch:

* ``only_media``     — page with just a MediaBox; every other box falls back.
* ``crop_oversized`` — /CropBox larger than the MediaBox on every side; must
  clip down to the MediaBox, and Bleed/Trim/Art (absent) inherit the clipped
  crop.
* ``boxes_one_oversized`` — explicit Bleed/Trim/Art, one of them oversized;
  the oversized one clips to the MediaBox, the others stay as written.
* ``user_unit``      — page carrying /UserUnit.
* ``inherited_media`` — page tree where the MediaBox lives on the intermediate
  /Pages node and the page inherits it.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_CROP_BOX = COSName.get_pdf_name("CropBox")
_BLEED_BOX = COSName.get_pdf_name("BleedBox")
_TRIM_BOX = COSName.get_pdf_name("TrimBox")
_ART_BOX = COSName.get_pdf_name("ArtBox")
_USER_UNIT = COSName.get_pdf_name("UserUnit")


def _arr(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    a = COSArray(
        [COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)]
    )
    a.set_direct(True)
    return a


def _save(doc: PDDocument, path: Path) -> None:
    buf = io.BytesIO()
    try:
        doc.save(buf)
    finally:
        doc.close()
    path.write_bytes(buf.getvalue())


def _build_only_media(path: Path) -> None:
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    doc.add_page(page)
    _save(doc, path)


def _build_crop_oversized(path: Path) -> None:
    doc = PDDocument()
    page = PDPage(PDRectangle(10.0, 20.0, 500.0, 700.0))
    # CropBox extends past the MediaBox on every side -> must clip to media.
    page.get_cos_object().set_item(_CROP_BOX, _arr(-100.0, -50.0, 900.0, 1000.0))
    doc.add_page(page)
    _save(doc, path)


def _build_boxes_one_oversized(path: Path) -> None:
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 600.0, 800.0))
    cos = page.get_cos_object()
    # A genuine CropBox inside the media — Bleed/Trim/Art fall back/clip to it
    # only when absent; here all three are explicit.
    cos.set_item(_CROP_BOX, _arr(20.0, 20.0, 580.0, 780.0))
    # BleedBox inside media -> unchanged.
    cos.set_item(_BLEED_BOX, _arr(10.0, 10.0, 590.0, 790.0))
    # TrimBox oversized on the upper-right -> clips to media (600,800).
    cos.set_item(_TRIM_BOX, _arr(30.0, 40.0, 700.0, 900.0))
    # ArtBox inside media -> unchanged.
    cos.set_item(_ART_BOX, _arr(50.0, 60.0, 550.0, 740.0))
    doc.add_page(page)
    _save(doc, path)


def _build_user_unit(path: Path) -> None:
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    page.get_cos_object().set_item(_USER_UNIT, COSFloat(2.5))
    doc.add_page(page)
    _save(doc, path)


def _build_inherited_media(path: Path) -> None:
    doc = PDDocument()
    page = PDPage()
    # Strip the page's own MediaBox so it must inherit from the /Pages node.
    page.get_cos_object().remove_item(COSName.MEDIA_BOX)
    doc.add_page(page)
    pages_node = doc.get_pages().get_cos_object()
    pages_node.set_item(COSName.MEDIA_BOX, _arr(0.0, 0.0, 300.0, 400.0))
    _save(doc, path)


_BUILDERS = {
    "only_media": _build_only_media,
    "crop_oversized": _build_crop_oversized,
    "boxes_one_oversized": _build_boxes_one_oversized,
    "user_unit": _build_user_unit,
    "inherited_media": _build_inherited_media,
}


def _fmt(value: float) -> str:
    """Canonical float rendering matching ``PageBoxProbe.fmt``: integral
    values print without a trailing ``.0``; non-integral values print with
    up to 4 decimals, trailing zeros stripped."""
    if value == int(value):
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _box(rect: PDRectangle) -> str:
    return (
        f"{_fmt(rect.lower_left_x)} {_fmt(rect.lower_left_y)} "
        f"{_fmt(rect.upper_right_x)} {_fmt(rect.upper_right_y)}"
    )


def _py_boxes(fixture: Path) -> str:
    """Build the same multi-line box report the Java probe emits."""
    lines: list[str] = []
    doc = PDDocument.load(fixture)
    try:
        count = doc.get_number_of_pages()
        lines.append(f"pages {count}")
        for i in range(count):
            page = doc.get_page(i)
            lines.append(
                f"page {i} media {_box(page.get_media_box())} "
                f"crop {_box(page.get_crop_box())} "
                f"bleed {_box(page.get_bleed_box())} "
                f"trim {_box(page.get_trim_box())} "
                f"art {_box(page.get_art_box())} "
                f"unit {_fmt(page.get_user_unit())}"
            )
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_page_boxes_match_pdfbox(label: str, tmp_path: Path) -> None:
    fixture = tmp_path / f"{label}.pdf"
    _BUILDERS[label](fixture)

    java = run_probe_text("PageBoxProbe", str(fixture))
    py = _py_boxes(fixture)
    assert py == java, (
        f"{label}: page boxes diverge from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )
