"""Port of ``org.apache.pdfbox.examples.pdmodel.CreateSeparationColorBox`` (lines 39-99).

Creates a separation / spot-colour rectangle as a placeholder for "Gold".
The colorspace's tint transform is a type 2 function that maps tint 0 to
white (1, 1, 1) and tint 1 to yellow (1, 1, 0).
"""

from __future__ import annotations

import sys

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.common.function.pd_function_type2 import PDFunctionType2
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


def _build_tint_transform() -> PDFunctionType2:
    """Build the tint transform function — C0=white, C1=yellow."""
    fdict = COSDictionary()
    fdict.set_int(COSName.get_pdf_name("FunctionType"), 2)
    range_array = COSArray()
    # Range covers three RGB output components: each in [0, 1].
    for _ in range(3):
        range_array.add(COSInteger.ZERO)
        range_array.add(COSInteger.ONE)
    fdict.set_item(COSName.get_pdf_name("Range"), range_array)
    domain = COSArray()
    domain.add(COSInteger.ZERO)
    domain.add(COSInteger.ONE)
    fdict.set_item(COSName.get_pdf_name("Domain"), domain)
    c0 = COSArray()
    c0.add(COSInteger.ONE)
    c0.add(COSInteger.ONE)
    c0.add(COSInteger.ONE)
    fdict.set_item(COSName.get_pdf_name("C0"), c0)
    c1 = COSArray()
    c1.add(COSInteger.ONE)
    c1.add(COSInteger.ONE)
    c1.add(COSInteger.ZERO)
    fdict.set_item(COSName.get_pdf_name("C1"), c1)
    fdict.set_int(COSName.N, 1)
    return PDFunctionType2(fdict)


class CreateSeparationColorBox:
    """Mirrors ``CreateSeparationColorBox`` (line 39)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 45).

        Deviation: when called with no arguments, writes to ``gold.pdf``
        in the current working directory (matches upstream's hard-coded
        ``doc.save("gold.pdf")``). When called with one argument, writes
        to that path — useful for tests that pin output to a ``tmp_path``.
        """
        argv = argv if argv is not None else []
        if len(argv) == 0:
            output_path = "gold.pdf"
        elif len(argv) == 1:
            output_path = argv[0]
        else:
            sys.stderr.write(
                "Usage: CreateSeparationColorBox [<output-pdf>]\n",
            )
            raise SystemExit(1)

        with PDDocument() as doc:
            page = PDPage()
            doc.add_page(page)

            # Build the Separation array: [/Separation /Gold /DeviceRGB <fn>]
            separation_array = COSArray()
            separation_array.add(COSName.get_pdf_name("Separation"))
            # Colorant name — placeholder for a spot colour like "metallic".
            separation_array.add(COSName.get_pdf_name("Gold"))
            # Alternate colorspace — DeviceRGB.
            separation_array.add(COSName.get_pdf_name("DeviceRGB"))
            # Tint transform — type 2 function (white -> yellow).
            func = _build_tint_transform()
            separation_array.add(func.get_cos_object())

            spot_color_space = PDSeparation(separation_array)

            with PDPageContentStream(doc, page) as cs:
                # Half-tint — should render as light yellow on screen.
                color = PDColor([0.5], spot_color_space)
                cs.set_stroking_color(color)
                cs.set_line_width(10)
                cs.add_rect(50, 50, 500, 700)
                cs.stroke()

            doc.save(output_path)
