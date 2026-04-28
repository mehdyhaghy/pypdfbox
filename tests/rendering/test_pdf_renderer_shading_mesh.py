"""Smoke tests for the deferred mesh shadings (Types 4-7).

These shadings (free-form Gouraud, lattice Gouraud, Coons patch, tensor
patch) require fairly involved geometry rasterisation that's tracked in
``CHANGES.md`` as deferred. The lite renderer logs a debug message and
falls back to a uniform fill at the function's value at ``f(0)`` — this
ensures pages don't crash when a mesh shading appears."""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer


def _make_doc(
    width: float = 50.0, height: float = 50.0
) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _is_close(
    actual: tuple[int, int, int],
    expected: tuple[int, int, int],
    tol: int = 12,
) -> bool:
    return all(
        abs(a - e) <= tol for a, e in zip(actual[:3], expected, strict=True)
    )


def test_mesh_shading_type4_falls_back_without_crash() -> None:
    """A Type 4 (free-form Gouraud) shading must render without raising
    even though full mesh rasterisation is deferred. The fallback path
    paints a solid fill at f(0) over the requested region."""
    doc, page = _make_doc(40.0, 40.0)

    # Build a minimal Type 4 shading stream. We don't expect the
    # renderer to actually decode the mesh data — it should hit the
    # mesh-shading fallback and log a debug message.
    shading = COSStream()
    shading.set_int(COSName.get_pdf_name("ShadingType"), 4)
    shading.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    shading.set_int(COSName.get_pdf_name("BitsPerCoordinate"), 8)
    shading.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    shading.set_int(COSName.get_pdf_name("BitsPerFlag"), 8)
    decode = COSArray()
    for v in (0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0):
        decode.add(COSFloat(v))
    shading.set_item(COSName.get_pdf_name("Decode"), decode)
    shading.set_raw_data(b"")  # No mesh data — fallback should still kick in.

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Shading"),
        COSName.get_pdf_name("Sh4"),
        shading,
    )
    contents = COSStream()
    contents.set_raw_data(b"/Sh4 sh\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    # Should not raise.
    img = PDFRenderer(doc).render_image(0)
    assert img.size == (40, 40)
