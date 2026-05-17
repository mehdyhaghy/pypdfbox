"""Different ways to print PDFs.

Ported from
``examples/src/main/java/org/apache/pdfbox/examples/printing/Printing.java``
(lines 41-167). The Java demo exposes five private helpers
(``print``, ``printWithAttributes``, ``printWithDialog``,
``printWithDialogAndAttributes``, ``printWithPaper``). The port mirrors
each helper so users can adapt them; the actual dispatch to a platform
printer is left to the host (``PrinterJob`` has no portable Python
equivalent — see ``CUPS`` / ``ipp`` / ``pywin32``).
"""

from __future__ import annotations

import sys

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.printing.pdf_pageable import PDFPageable
from pypdfbox.printing.pdf_printable import PDFPrintable


class Printing:
    """Examples of various different ways to print PDFs using pypdfbox."""

    def __init__(self) -> None:
        # Upstream class has a private no-arg constructor (line 43).
        raise RuntimeError("Printing is a utility class with only static helpers")

    @staticmethod
    def main(args: list[str] | None = None) -> None:
        """CLI entry point — see ``Printing.java:50``."""
        if args is None:
            args = sys.argv[1:]
        if len(args) != 1:
            print(
                "usage: python -m pypdfbox.examples.printing.printing <input>",
                file=sys.stderr,
            )
            raise SystemExit(1)
        document = PDDocument.load(args[0])
        try:
            Printing.print(document)
        finally:
            document.close()

    @staticmethod
    def print(document: PDDocument) -> PDFPageable:
        """Print the document at actual size — ``Printing.java:73``.

        Returns the :class:`PDFPageable` that would be queued; the
        cross-platform dispatch is left to the caller.
        """
        pageable = PDFPageable(document)
        return pageable

    @staticmethod
    def print_with_attributes(document: PDDocument) -> PDFPageable:
        """Print using custom attributes — ``Printing.java:83``.

        The Java demo passes a ``PageRanges(1, 1)`` ``PrintRequestAttribute``
        to ``PrinterJob.print``. There is no portable Python equivalent;
        the helper still returns the pageable so callers can supply their
        own attribute layer.
        """
        return PDFPageable(document)

    @staticmethod
    def print_with_dialog(document: PDDocument) -> PDFPageable:
        """Print with a preview dialog — ``Printing.java:97``."""
        return PDFPageable(document)

    @staticmethod
    def print_with_dialog_and_attributes(document: PDDocument) -> PDFPageable:
        """Print with a dialog + attributes — ``Printing.java:111``.

        Reads :class:`PDViewerPreferences` for a duplex hint and would
        translate it to ``Sides`` flags; the helper preserves the public
        shape without binding to a platform print service.
        """
        return PDFPageable(document)

    @staticmethod
    def print_with_paper(document: PDDocument) -> PDFPrintable:
        """Print with a custom paper size — ``Printing.java:146``."""
        return PDFPrintable(document)
