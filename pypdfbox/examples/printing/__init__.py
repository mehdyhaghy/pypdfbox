"""Port of ``org.apache.pdfbox.examples.printing``.

These examples drive :class:`pypdfbox.printing.PDFPageable` and
:class:`pypdfbox.printing.PDFPrintable` for various print workflows, plus
an opaque renderer that strips transparency for printer-friendly output
(PDFBOX-4123 / PDFBOX-5605). Printer dispatch itself is platform-native
and intentionally out of scope; the ports preserve the surface so users
can adapt them.
"""

from pypdfbox.examples.printing.opaque_draw_object import OpaqueDrawObject
from pypdfbox.examples.printing.opaque_pdf_renderer import OpaquePDFRenderer
from pypdfbox.examples.printing.opaque_set_graphics_state_parameters import (
    OpaqueSetGraphicsStateParameters,
)
from pypdfbox.examples.printing.printing import Printing

__all__ = [
    "OpaqueDrawObject",
    "OpaquePDFRenderer",
    "OpaqueSetGraphicsStateParameters",
    "Printing",
]
