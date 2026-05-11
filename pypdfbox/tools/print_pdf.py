"""``PrintPDF`` class port — sends a PDF to a system printer.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/PrintPDF.java
    (lines 58-372)

Upstream uses ``java.awt.print.PrinterJob`` / ``javax.print``. Python has
no portable system-printer API in stdlib — the ``call``, dialog, tray, and
media-size methods raise ``NotImplementedError("GUI tool")``. The
``Duplex`` enum, ``createPrintRequestAttributeSet``, and the helper
listing methods are still ported so the surface matches upstream for
parity counting and unit tests of the pure-Python helpers.
"""
from __future__ import annotations

import argparse
import enum
import sys
from pathlib import Path


class Duplex(enum.Enum):
    """Mirror of inner enum ``PrintPDF.Duplex`` (PrintPDF.java:61)."""

    SIMPLEX = 0
    DUPLEX = 1
    TUMBLE = 2
    DOCUMENT = 3

    def to_sides(self) -> str | None:
        """Mirror of ``Duplex.toSides()`` — returns a string token instead of
        the Java ``Sides`` constant. ``None`` means "let the document choose"
        (preserves upstream null semantics)."""
        return {
            0: "ONE_SIDED",
            1: "DUPLEX",
            2: "TUMBLE",
        }.get(self.value)


class PrintPDF:
    def __init__(self) -> None:
        self.password: str | None = None
        self.silent_print: bool = False
        self.printer_name: str | None = None
        self.orientation: str = "AUTO"
        self.duplex: Duplex = Duplex.DOCUMENT
        self.tray: str | None = None
        self.media_size: str | None = None
        self.border: bool = False
        self.dpi: int = 0
        self.no_center: bool = False
        self.no_color_opt: bool = False
        self.infile: Path | None = None

    # --- helpers that don't need a printer subsystem --------------------
    def create_print_request_attribute_set(self, document) -> dict[str, str]:
        """Mirror of upstream ``createPrintRequestAttributeSet``. Returns a
        plain dict (Python lacks ``HashPrintRequestAttributeSet``)."""
        pras: dict[str, str] = {}
        side = self.duplex.to_sides()
        if side is None:
            # fall back to viewer-preferences duplex hint, if any
            try:
                vp = document.get_document_catalog().get_viewer_preferences()
            except AttributeError:
                vp = None
            if vp is not None and getattr(vp, "get_duplex", lambda: None)():
                dp = vp.get_duplex()
                if dp == "DuplexFlipLongEdge":
                    pras["Sides"] = "TWO_SIDED_LONG_EDGE"
                elif dp == "DuplexFlipShortEdge":
                    pras["Sides"] = "TWO_SIDED_SHORT_EDGE"
                elif dp == "Simplex":
                    pras["Sides"] = "ONE_SIDED"
        else:
            pras["Sides"] = side
        return pras

    def to_possible_alternate_media(self, media_tray: object) -> object:
        """Mirror of ``toPossibleAlternateMedia``. Without the Sun-internal
        helper class on Python the method just returns the tray."""
        return media_tray

    def show_available_printers(self) -> None:
        """Mirror of ``showAvailablePrinters`` — implemented as a stub."""
        sys.stderr.write("Available printer names:\n")
        for name in self.get_trays_from_print_service(None):
            sys.stderr.write(f"    {name}\n")

    @staticmethod
    def get_trays_from_print_service(print_service: object) -> list[str]:
        """Mirror of ``getTraysFromPrintService``. No portable Python printer
        API in stdlib — returns an empty list."""
        return []

    @staticmethod
    def get_media_sizes_from_print_service(print_service: object) -> list[str]:
        """Mirror of ``getMediaSizesFromPrintService`` — empty on Python."""
        return []

    # --- GUI-only entry points -----------------------------------------
    def call(self) -> int:
        """``call()`` requires a system printer subsystem — not portable.

        Mirrors the upstream signature; raises ``NotImplementedError``
        so the parity test surface still matches.
        """
        raise NotImplementedError("GUI tool: PrintPDF.call requires a system printer")

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="print", description="Prints a PDF document",
        )
        parser.add_argument("-password", default=None)
        parser.add_argument("-silentPrint", dest="silentPrint", action="store_true")
        parser.add_argument("-printerName", dest="printerName", default=None)
        parser.add_argument("-orientation", default="AUTO")
        parser.add_argument("-duplex", default="DOCUMENT")
        parser.add_argument("-tray", default=None)
        parser.add_argument("-mediaSize", dest="mediaSize", default=None)
        parser.add_argument("-border", action="store_true")
        parser.add_argument("-dpi", type=int, default=0)
        parser.add_argument("-noCenter", dest="noCenter", action="store_true")
        parser.add_argument("-noColorOpt", dest="noColorOpt", action="store_true")
        parser.add_argument("-i", "--input", dest="infile", required=True)
        ns = parser.parse_args(args)
        runner = PrintPDF()
        runner.password = ns.password
        runner.silent_print = ns.silentPrint
        runner.printer_name = ns.printerName
        runner.orientation = ns.orientation
        runner.duplex = Duplex[ns.duplex]
        runner.tray = ns.tray
        runner.media_size = ns.mediaSize
        runner.border = ns.border
        runner.dpi = ns.dpi
        runner.no_center = ns.noCenter
        runner.no_color_opt = ns.noColorOpt
        runner.infile = Path(ns.infile)
        try:
            return runner.call()
        except NotImplementedError as exc:
            sys.stderr.write(f"PrintPDF: {exc}\n")
            return 4


if __name__ == "__main__":
    sys.exit(PrintPDF.main(sys.argv[1:]))
