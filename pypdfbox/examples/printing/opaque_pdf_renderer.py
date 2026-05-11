"""Renderer that flattens transparency for the printing path.

Ported from
``examples/src/main/java/org/apache/pdfbox/examples/printing/OpaquePDFRenderer.java``
(lines 65-110). The Java demo plugs the
:class:`OpaqueDrawObject` and :class:`OpaqueSetGraphicsStateParameters`
operators into the page drawer so printing pipelines do not pay the
transparency-group cost (PDFBOX-4123, PDFBOX-5605).
"""

from __future__ import annotations

from pypdfbox.examples.printing.opaque_draw_object import OpaqueDrawObject
from pypdfbox.examples.printing.opaque_set_graphics_state_parameters import (
    OpaqueSetGraphicsStateParameters,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.rendering.page_drawer import PageDrawer
from pypdfbox.rendering.page_drawer_parameters import PageDrawerParameters
from pypdfbox.rendering.pdf_renderer import PDFRenderer


class OpaquePDFRenderer(PDFRenderer):
    """PDF renderer that strips transparency for opaque printing."""

    def __init__(self, document: PDDocument) -> None:
        super().__init__(document)

    @staticmethod
    def main(args: list[str] | None = None) -> None:
        """CLI entry point — see ``OpaquePDFRenderer.java:68``.

        The upstream sample fetches a test PDF over HTTPS and dispatches
        the platform print job. Network fetch and printer dispatch are
        out of scope for the parity port; raise ``NotImplementedError``
        so callers know to adapt the surface for their environment.
        """
        del args
        raise NotImplementedError(
            "Printer dispatch is platform-specific — adapt this main() "
            "to your CUPS/IPP/Win32 print stack."
        )

    def create_page_drawer(self, parameters: PageDrawerParameters) -> PageDrawer:
        return _OpaquePageDrawer(parameters)


class _OpaquePageDrawer(PageDrawer):
    """Inner class — see ``OpaquePDFRenderer.java:101``."""

    def __init__(self, parameters: PageDrawerParameters) -> None:
        super().__init__(parameters)
        try:
            self.add_operator(OpaqueDrawObject(self))
            self.add_operator(OpaqueSetGraphicsStateParameters(self))
        except AttributeError:  # pragma: no cover - bare scaffold
            pass
