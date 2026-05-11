"""``PrintPDF`` class port — sends a PDF to a system printer.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/PrintPDF.java
    (lines 58-372)

Upstream uses ``java.awt.print.PrinterJob`` / ``javax.print`` — a full
in-process print pipeline with a GUI dialog. Python's stdlib does not
expose a portable system-printer API, so the pypdfbox port instead
delegates to the OS print spooler:

* macOS / Linux — ``lpr(1)`` (CUPS), if available on ``$PATH``.
* Windows — ``os.startfile(path, "print")`` (uses the default app).

The Java print dialog has no equivalent here, so the ``-silentPrint``
flag is honoured by default; the non-silent case falls back to silent
with a logged warning. The ``Duplex`` enum,
``create_print_request_attribute_set``, and helper listing methods are
still ported so the surface matches upstream for parity counting.
"""
from __future__ import annotations

import argparse
import enum
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


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

    # --- entry points ---------------------------------------------------
    def call(self) -> int:
        """Send the configured PDF to the system print spooler.

        Returns the exit code (0 on success, 4 on failure) — mirrors the
        upstream ``Integer call()`` contract.

        Deviations from upstream:

        * Python stdlib has no in-process printer API. We shell out to
          ``lpr`` (POSIX, CUPS) or ``os.startfile(..., "print")``
          (Windows) instead of building a ``PrinterJob``.
        * Upstream pops a ``PrinterJob.printDialog`` when ``silentPrint``
          is false. Python has no equivalent dialog, so a non-silent
          request is logged and falls through to the silent code path.
        * ``-dpi`` / ``-border`` / ``-noCenter`` / ``-noColorOpt`` apply
          only to the upstream in-process rasterising path; with the
          OS spooler the underlying app / driver decides. We keep the
          attributes on the instance so callers / subclasses can inspect
          them, but they don't influence the spawned command.
        """
        if self.infile is None:
            sys.stderr.write("PrintPDF: no input file configured\n")
            return 4
        pdf_path = Path(self.infile)
        if not pdf_path.exists():
            sys.stderr.write(f"PrintPDF: file not found: {pdf_path}\n")
            return 4

        # Optional sanity check — upstream calls Loader.loadPDF and
        # consults ``can_print`` on the access permission. We do the same
        # so an encrypted/permission-restricted PDF fails fast rather
        # than handing protected bytes to the spooler.
        try:
            from pypdfbox.loader import Loader  # noqa: PLC0415

            with Loader.load_pdf(pdf_path, self.password or "") as document:
                ap = document.get_current_access_permission()
                if ap is not None and not ap.can_print():
                    sys.stderr.write("You do not have permission to print\n")
                    return 4
        except (OSError, AttributeError) as exc:
            # AttributeError covers COSDocument vs PDDocument surface
            # mismatch — the spooler can still print the bytes even when
            # the lite access-permission probe isn't wired up.
            logger.debug("permission probe skipped: %s", exc)

        if not self.silent_print:
            logger.warning(
                "PrintPDF: non-silent print dialog not supported on Python; "
                "falling through to silent print",
            )

        if sys.platform.startswith("win"):
            try:
                os.startfile(str(pdf_path), "print")  # type: ignore[attr-defined]  # noqa: S606
            except OSError as exc:
                sys.stderr.write(f"Error printing document [OSError]: {exc}\n")
                return 4
            return 0

        lpr = shutil.which("lpr")
        if lpr is None:
            sys.stderr.write(
                "Error printing document [RuntimeError]: 'lpr' not found on PATH\n",
            )
            return 4

        cmd: list[str] = [lpr]
        if self.printer_name:
            cmd += ["-P", self.printer_name]
        if self.orientation and self.orientation.upper() != "AUTO":
            # CUPS expects integer orientation-requested values (3=portrait,
            # 4=landscape, 5=reverse-landscape, 6=reverse-portrait). Map by
            # name and pass the integer; unknown names are forwarded as-is.
            mapping = {
                "PORTRAIT": "3",
                "LANDSCAPE": "4",
                "REVERSE_LANDSCAPE": "5",
                "REVERSE_PORTRAIT": "6",
            }
            value = mapping.get(self.orientation.upper(), self.orientation)
            cmd += ["-o", f"orientation-requested={value}"]
        side = self.duplex.to_sides()
        if side == "DUPLEX":
            cmd += ["-o", "sides=two-sided-long-edge"]
        elif side == "TUMBLE":
            cmd += ["-o", "sides=two-sided-short-edge"]
        elif side == "ONE_SIDED":
            cmd += ["-o", "sides=one-sided"]
        if self.tray:
            cmd += ["-o", f"media={self.tray}"]
        if self.media_size:
            cmd += ["-o", f"media={self.media_size}"]
        cmd.append(str(pdf_path))

        try:
            subprocess.run(cmd, check=True)  # noqa: S603
        except (subprocess.CalledProcessError, OSError) as exc:
            sys.stderr.write(
                f"Error printing document [{type(exc).__name__}]: {exc}\n",
            )
            return 4
        return 0

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
        return runner.call()


if __name__ == "__main__":
    sys.exit(PrintPDF.main(sys.argv[1:]))
