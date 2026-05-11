"""Port of ``org.apache.pdfbox.examples.pdmodel.CreateGradientShadingPDF`` (lines 46-220).

Creates a PDF with type 2 (axial) and type 3 (radial) shadings driven by
a type 2 (exponential) function, plus a type 4 (Gouraud) free-form
triangle-mesh shading whose vertex stream is built by hand.
"""

from __future__ import annotations

import io
import struct
import sys

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.common.function.pd_function_type2 import PDFunctionType2
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.shading.pd_shading import PDShading
from pypdfbox.pdmodel.graphics.shading.pd_shading_type2 import PDShadingType2
from pypdfbox.pdmodel.graphics.shading.pd_shading_type3 import PDShadingType3
from pypdfbox.pdmodel.graphics.shading.pd_shading_type4 import PDShadingType4
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import AppendMode, PDPageContentStream


def _cos_float_array(values: list[float]) -> COSArray:
    """Build a ``COSArray`` from a list of numeric values."""
    array = COSArray()
    array.set_float_array(values)
    return array


def _build_exp_function() -> PDFunctionType2:
    """Mirror upstream's type 2 exponential function dictionary
    construction (Java lines 65-82)."""
    fdict = COSDictionary()
    fdict.set_int(COSName.get_pdf_name("FunctionType"), 2)
    domain = COSArray()
    domain.add(COSInteger.ZERO)
    domain.add(COSInteger.ONE)
    c0 = _cos_float_array([1.0, 0.0, 0.0])
    c1 = _cos_float_array([0.5, 1.0, 0.5])
    fdict.set_item(COSName.get_pdf_name("Domain"), domain)
    fdict.set_item(COSName.get_pdf_name("C0"), c0)
    fdict.set_item(COSName.get_pdf_name("C1"), c1)
    fdict.set_int(COSName.N, 1)
    return PDFunctionType2(fdict)


def _gouraud_vertex_stream() -> bytes:
    """Build the mesh body for the type 4 shading.

    Matches upstream's hand-emitted byte layout (Java lines 144-178):
    one flag byte, two 16-bit big-endian coordinates, then three 8-bit
    color components per vertex.
    """
    buf = io.BytesIO()
    # Vertex 1 — bottom-left corner, red.
    buf.write(struct.pack(">B", 0))
    buf.write(struct.pack(">HH", 0, 0))
    buf.write(struct.pack(">BBB", 0xFF, 0x00, 0x00))
    # Vertex 2 — top corner, green.
    buf.write(struct.pack(">B", 0))
    buf.write(struct.pack(">HH", 100, 100))
    buf.write(struct.pack(">BBB", 0x00, 0xFF, 0x00))
    # Vertex 3 — bottom-right corner, blue.
    buf.write(struct.pack(">B", 0))
    buf.write(struct.pack(">HH", 200, 0))
    buf.write(struct.pack(">BBB", 0x00, 0x00, 0xFF))
    return buf.getvalue()


class CreateGradientShadingPDF:
    """Mirrors ``CreateGradientShadingPDF`` (line 46)."""

    def __init__(self) -> None:
        pass

    def create(self, file_: str) -> None:
        """Mirrors ``create(String file)`` (line 56)."""
        with PDDocument() as document:
            page = PDPage()
            document.add_page(page)

            func = _build_exp_function()

            # Axial (type 2) shading.
            axial_shading = PDShadingType2(COSDictionary())
            axial_shading.set_color_space(PDDeviceRGB.INSTANCE.get_cos_object())
            axial_shading.set_shading_type(PDShading.SHADING_TYPE2)
            coords1 = COSArray()
            for value in (100, 400, 400, 600):
                coords1.add(COSInteger.get(value))
            axial_shading.set_coords(coords1)
            axial_shading.set_function(func)

            # Radial (type 3) shading.
            radial_shading = PDShadingType3(COSDictionary())
            radial_shading.set_color_space(PDDeviceRGB.INSTANCE.get_cos_object())
            radial_shading.set_shading_type(PDShading.SHADING_TYPE3)
            coords2 = COSArray()
            for value in (100, 400, 50, 400, 600, 150):
                coords2.add(COSInteger.get(value))
            radial_shading.set_coords(coords2)
            radial_shading.set_function(func)

            # Gouraud (type 4) shading — vertex stream is hand-built.
            gouraud_shading = PDShadingType4(
                document.get_document().create_cos_stream()
            )
            gouraud_shading.set_shading_type(PDShading.SHADING_TYPE4)
            # Multiples of 8 → no bit-padding required.
            gouraud_shading.set_bits_per_flag(8)
            gouraud_shading.set_bits_per_coordinate(16)
            gouraud_shading.set_bits_per_component(8)
            # /Decode array: x/y span 0..FFFF mapped to 0..FFFF (identity);
            # rgb spans 0..FF mapped to 0..1.
            decode_array = COSArray()
            decode_array.add(COSInteger.ZERO)
            decode_array.add(COSInteger.get(0xFFFF))
            decode_array.add(COSInteger.ZERO)
            decode_array.add(COSInteger.get(0xFFFF))
            decode_array.add(COSInteger.ZERO)
            decode_array.add(COSInteger.ONE)
            decode_array.add(COSInteger.ZERO)
            decode_array.add(COSInteger.ONE)
            decode_array.add(COSInteger.ZERO)
            decode_array.add(COSInteger.ONE)
            gouraud_shading.set_decode(decode_array)
            gouraud_shading.set_color_space(PDDeviceRGB.INSTANCE.get_cos_object())

            # Fill the vertex stream — write raw, no filter applied so the
            # bytes round-trip verbatim through the saved PDF (matches the
            # ``compress=false`` posture of the upstream content stream).
            mesh_bytes = _gouraud_vertex_stream()
            cos_stream = gouraud_shading.get_cos_object()
            cos_stream.set_raw_data(mesh_bytes)

            # Paint all three shadings onto the page.
            with PDPageContentStream(
                document, page, AppendMode.APPEND, compress=False,
            ) as content_stream:
                content_stream.shading_fill(axial_shading)
                content_stream.shading_fill(radial_shading)
                content_stream.shading_fill(gouraud_shading)

            document.save(file_)

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 200)."""
        argv = argv if argv is not None else []
        if len(argv) != 1:
            CreateGradientShadingPDF.usage()
            return
        creator = CreateGradientShadingPDF()
        creator.create(argv[0])

    @staticmethod
    def usage() -> None:
        """Mirrors ``usage()`` (upstream line 215)."""
        sys.stderr.write(
            "usage: CreateGradientShadingPDF <outputfile.pdf>\n",
        )
