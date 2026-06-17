"""Live PDFBox differential parity for ``PDPage`` ``/Thumb`` accessor.

``/Thumb`` is a page-level image XObject that viewers display as a preview.
Upstream PDFBox resolves it via the COS stream + :class:`PDImageXObject`
``createThumbnail`` factory (special rule: any non-null ``/Subtype`` is
treated as ``/Image``). The pypdfbox accessor is
:meth:`PDPage.get_thumb`, which wraps a present ``/Thumb`` stream in a
:class:`PDImageXObject` and returns ``None`` when the entry is absent or
non-stream.

Two fixtures pin the surface:

* **with-thumb** — a page whose ``/Thumb`` holds a small DeviceGray image
  XObject (3x4, 8 bpc). The accessor must report the same width / height /
  ``/BitsPerComponent`` / colour-space name as PDFBox.
* **no-thumb** — a page without ``/Thumb``. The accessor must return
  ``None`` (pypdfbox) / a "thumb none" line (oracle) — pinning that an
  absent entry never auto-materialises a wrapper.

The probe is ``oracle/probes/PageThumbProbe.java``: per page it reads
``/Thumb`` straight off the COS dictionary, then wraps it via
``PDImageXObject.createThumbnail`` for the width/height/bpc/colour-space
accessors so the exact upstream code path is exercised.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_THUMB = COSName.get_pdf_name("Thumb")
_WIDTH = COSName.get_pdf_name("Width")
_HEIGHT = COSName.get_pdf_name("Height")
_BPC = COSName.get_pdf_name("BitsPerComponent")
_COLORSPACE = COSName.get_pdf_name("ColorSpace")

# 3x4 DeviceGray, 8 bpc — 12 raw decoded sample bytes. Small enough that
# the encoded stream stays well inside a single line; large enough that
# /Width and /Height aren't both 1 (which would mask off-by-one swaps).
_THUMB_WIDTH = 3
_THUMB_HEIGHT = 4
_THUMB_BPC = 8
_THUMB_DATA = bytes(range(_THUMB_WIDTH * _THUMB_HEIGHT))


def _build_thumb_stream() -> COSStream:
    """Hand-author a /Thumb image-XObject stream: DeviceGray, 3x4, 8 bpc."""
    stream = COSStream()
    stream.set_int(_WIDTH, _THUMB_WIDTH)
    stream.set_int(_HEIGHT, _THUMB_HEIGHT)
    stream.set_int(_BPC, _THUMB_BPC)
    stream.set_item(_COLORSPACE, COSName.get_pdf_name("DeviceGray"))
    stream.set_data(_THUMB_DATA)
    return stream


def _build_fixture(path: Path) -> None:
    """Two-page PDF: page 0 carries a /Thumb, page 1 has none."""
    doc = PDDocument()
    page_with = PDPage(PDRectangle(0.0, 0.0, 200.0, 240.0))
    page_with.get_cos_object().set_item(_THUMB, _build_thumb_stream())
    doc.add_page(page_with)
    doc.add_page(PDPage(PDRectangle(0.0, 0.0, 200.0, 240.0)))
    try:
        buf = io.BytesIO()
        doc.save(buf)
    finally:
        doc.close()
    path.write_bytes(buf.getvalue())


def _py_emit(fixture: Path) -> str:
    """Reproduce the probe's output format from pypdfbox accessors."""
    lines: list[str] = []
    with PDDocument.load(fixture) as doc:
        for i in range(doc.get_number_of_pages()):
            page = doc.get_page(i)
            thumb = page.get_thumb()
            if thumb is None:
                lines.append(f"page {i} thumb none")
                continue
            w = thumb.get_width()
            h = thumb.get_height()
            bpc = thumb.get_bits_per_component()
            cs_obj = thumb.get_color_space()
            cs = cs_obj.get_name() if cs_obj is not None else "null"
            lines.append(
                f"page {i} thumb present w {w} h {h} bpc {bpc} cs {cs}"
            )
    return "\n".join(lines) + "\n"


@requires_oracle
def test_page_thumb_matches_pdfbox(tmp_path: Path) -> None:
    """``PDPage.get_thumb`` returns the same dims/bpc/colour-space facts
    as PDFBox's ``PDImageXObject.createThumbnail`` chain — and ``None`` /
    "thumb none" agree when the entry is absent."""
    fixture = tmp_path / "page_thumb.pdf"
    _build_fixture(fixture)
    java = run_probe_text("PageThumbProbe", str(fixture))
    py = _py_emit(fixture)
    assert py == java, (
        f"page /Thumb facts diverge from PDFBox.\n"
        f"--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )


def test_page_thumb_returns_none_when_absent() -> None:
    """Pure pypdfbox guard — no oracle required.

    A fresh ``PDPage`` has no ``/Thumb`` so :meth:`PDPage.get_thumb`
    must return ``None`` and :meth:`PDPage.has_thumb` must agree.
    """
    page = PDPage()
    assert page.get_thumb() is None
    assert page.has_thumb() is False


def test_page_thumb_returns_image_xobject_when_present() -> None:
    """Pure pypdfbox guard — verify the local accessor wraps a present
    ``/Thumb`` stream in a :class:`PDImageXObject` with the dims / bpc /
    colour-space we wrote, without relying on the oracle.
    """
    from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject

    page = PDPage()
    page.get_cos_object().set_item(_THUMB, _build_thumb_stream())
    thumb = page.get_thumb()
    assert isinstance(thumb, PDImageXObject)
    assert thumb.get_width() == _THUMB_WIDTH
    assert thumb.get_height() == _THUMB_HEIGHT
    assert thumb.get_bits_per_component() == _THUMB_BPC
    cs = thumb.get_color_space()
    assert cs is not None
    assert cs.get_name() == "DeviceGray"
