"""Live PDFBox differential parity for ``PDPage`` UserUnit + boundary-box
default-precedence/clip resolution.

Complements ``test_page_box_oracle.py`` (which pins the explicit-value path
and the absent-box default chain inside the media box). This module pins the
two facets that file leaves open, both verified against the Apache PDFBox
3.0.7 oracle (``oracle/probes/PageUserUnitBoxProbe.java``):

* **``/UserUnit``** (PDF 32000-1 §10.10.3) — the existing box test never sets
  ``/UserUnit``, so a non-1.0 value is unexercised. Upstream
  ``PDPage.getUserUnit()`` reads ``getFloat(USER_UNIT, 1f)`` and returns it
  only when ``> 0``; a stored zero or negative value is treated as absent and
  reported as ``1.0``. We cover an integer unit, a fractional float unit, the
  absent default, and the non-positive clamp.

* **Box clip to MediaBox** (§14.11.2) — every fixture in the sibling test
  keeps its optional boxes *inside* the media box, so the clipToMediaBox snap
  never fires. Here an explicit CropBox/Bleed/Trim/Art each overflow the
  MediaBox on every edge; upstream clips lower-left up and upper-right down,
  and the cascade (Art/Trim/Bleed default to the already-clipped CropBox) must
  inherit the clipped — not the raw — crop rectangle.

Fixtures are built programmatically so we control the exact COS layout.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
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
    a = COSArray([COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)])
    a.set_direct(True)
    return a


def _save(doc: PDDocument, path: Path) -> None:
    buf = io.BytesIO()
    try:
        doc.save(buf)
    finally:
        doc.close()
    path.write_bytes(buf.getvalue())


def _build_user_unit_int(path: Path) -> None:
    """Large-format page with an integer ``/UserUnit`` of 72 (1 unit = 1
    inch) — pins the non-1.0 unit read for a COSInteger."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    page.get_cos_object().set_item(_USER_UNIT, COSInteger.get(72))
    doc.add_page(page)
    _save(doc, path)


def _build_user_unit_float(path: Path) -> None:
    """Fractional ``/UserUnit`` (5.08, ~36 pt to a cm at 50%) — pins the
    non-1.0 unit read for a COSFloat through canonical float formatting."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 300.0))
    page.get_cos_object().set_item(_USER_UNIT, COSFloat(5.08))
    doc.add_page(page)
    _save(doc, path)


def _build_user_unit_zero(path: Path) -> None:
    """Malformed non-positive ``/UserUnit`` (0) — upstream treats it as
    absent and reports 1.0; a literal pass-through would report 0."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 400.0, 500.0))
    page.get_cos_object().set_item(_USER_UNIT, COSInteger.get(0))
    doc.add_page(page)
    _save(doc, path)


def _build_user_unit_negative(path: Path) -> None:
    """Malformed negative ``/UserUnit`` (-3.5) — clamped to 1.0 upstream."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 400.0, 500.0))
    page.get_cos_object().set_item(_USER_UNIT, COSFloat(-3.5))
    doc.add_page(page)
    _save(doc, path)


def _build_user_unit_absent(path: Path) -> None:
    """No ``/UserUnit`` — default 1.0."""
    doc = PDDocument()
    doc.add_page(PDPage(PDRectangle(0.0, 0.0, 300.0, 400.0)))
    _save(doc, path)


def _build_clip_crop_overflow(path: Path) -> None:
    """CropBox overflows the MediaBox on every edge; no optional boxes.

    The crop must clip to the media box (lower-left snaps up to (0,0),
    upper-right snaps down to (612,792)), and Art/Trim/Bleed must default to
    that *clipped* crop rectangle — not the raw overflowing one."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    page.get_cos_object().set_item(_CROP_BOX, _arr(-50.0, -40.0, 700.0, 850.0))
    doc.add_page(page)
    _save(doc, path)


def _build_clip_all_overflow(path: Path) -> None:
    """Every optional box overflows the MediaBox on its own edges — each is
    independently clipped to the media box, not to the crop box."""
    doc = PDDocument()
    page = PDPage(PDRectangle(10.0, 20.0, 510.0, 720.0))
    cos = page.get_cos_object()
    cos.set_item(_CROP_BOX, _arr(0.0, 0.0, 600.0, 800.0))
    cos.set_item(_BLEED_BOX, _arr(-5.0, 15.0, 520.0, 700.0))
    cos.set_item(_TRIM_BOX, _arr(50.0, 0.0, 600.0, 600.0))
    cos.set_item(_ART_BOX, _arr(5.0, 25.0, 800.0, 900.0))
    doc.add_page(page)
    _save(doc, path)


_BUILDERS = {
    "unit_int": _build_user_unit_int,
    "unit_float": _build_user_unit_float,
    "unit_zero": _build_user_unit_zero,
    "unit_negative": _build_user_unit_negative,
    "unit_absent": _build_user_unit_absent,
    "clip_crop_overflow": _build_clip_crop_overflow,
    "clip_all_overflow": _build_clip_all_overflow,
}


def _fmt(value: float) -> str:
    """Canonical float rendering matching ``PageUserUnitBoxProbe.fmt``."""
    if value == int(value):
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _box(rect: PDRectangle) -> str:
    return (
        f"{_fmt(rect.lower_left_x)} {_fmt(rect.lower_left_y)} "
        f"{_fmt(rect.upper_right_x)} {_fmt(rect.upper_right_y)}"
    )


def _py_read(fixture: Path) -> str:
    doc = PDDocument.load(fixture)
    try:
        page = doc.get_page(0)
        return (
            f"page 0 media {_box(page.get_media_box())} "
            f"crop {_box(page.get_crop_box())} "
            f"bleed {_box(page.get_bleed_box())} "
            f"trim {_box(page.get_trim_box())} "
            f"art {_box(page.get_art_box())} "
            f"unit {_fmt(page.get_user_unit())}"
        ) + "\n"
    finally:
        doc.close()


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_page_user_unit_and_box_clip_match_pdfbox(label: str, tmp_path: Path) -> None:
    fixture = tmp_path / f"{label}.pdf"
    _BUILDERS[label](fixture)
    java = run_probe_text("PageUserUnitBoxProbe", str(fixture))
    py = _py_read(fixture)
    assert py == java, (
        f"{label}: page UserUnit / box-clip diverge from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )
