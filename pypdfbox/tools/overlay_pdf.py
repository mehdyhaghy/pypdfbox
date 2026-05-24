"""``OverlayPDF`` class port — adds an overlay to a PDF document.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/OverlayPDF.java
    (lines 42-175)
"""
from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

from pypdfbox.multipdf.overlay import Overlay, Position


class OverlayPDF:
    def __init__(self) -> None:
        self.odd_page_overlay: Path | None = None
        self.even_page_overlay: Path | None = None
        self.first_page_overlay: Path | None = None
        self.last_page_overlay: Path | None = None
        self.use_all_pages: Path | None = None
        self.adjust_rotation: bool = False
        self.specific_page_overlay_file: dict[int, str] = {}
        self.default_overlay: Path | None = None
        self.position: Position = Position.BACKGROUND
        self.infile: Path | None = None
        self.outfile: Path | None = None

    def call(self) -> int:
        retcode = 0
        if self.infile is None or self.outfile is None:
            raise OSError("infile and outfile are required")
        overlayer = Overlay()
        overlayer.set_overlay_position(self.position)
        if self.first_page_overlay is not None:
            overlayer.set_first_page_overlay_file(str(Path(self.first_page_overlay).resolve()))
        if self.last_page_overlay is not None:
            overlayer.set_last_page_overlay_file(str(Path(self.last_page_overlay).resolve()))
        if self.odd_page_overlay is not None:
            overlayer.set_odd_page_overlay_file(str(Path(self.odd_page_overlay).resolve()))
        if self.even_page_overlay is not None:
            overlayer.set_even_page_overlay_file(str(Path(self.even_page_overlay).resolve()))
        if self.use_all_pages is not None:
            overlayer.set_all_pages_overlay_file(str(Path(self.use_all_pages).resolve()))
        if self.default_overlay is not None:
            overlayer.set_default_overlay_file(str(Path(self.default_overlay).resolve()))
        if self.infile is not None:
            overlayer.set_input_file(str(Path(self.infile).resolve()))
        overlayer.set_adjust_rotation(self.adjust_rotation)
        try:
            result = overlayer.overlay(self.specific_page_overlay_file)
            try:
                result.save(self.outfile)
            finally:
                with contextlib.suppress(Exception):
                    result.close()
        except OSError as ioe:
            sys.stderr.write(
                f"Error adding overlay(s) to PDF [{type(ioe).__name__}]: {ioe}\n"
            )
            return 4
        finally:
            try:
                overlayer.close()
            except OSError as ioe:
                sys.stderr.write(
                    f"Error adding overlay(s) to PDF [{type(ioe).__name__}]: {ioe}\n"
                )
                retcode = 4
        return retcode

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="overlaypdf",
            description="Adds an overlay to a PDF document",
        )
        parser.add_argument("-odd", default=None)
        parser.add_argument("-even", default=None)
        parser.add_argument("-first", default=None)
        parser.add_argument("-last", default=None)
        parser.add_argument("-useAllPages", dest="useAllPages", default=None)
        parser.add_argument(
            "-adjustRotation", dest="adjustRotation", action="store_true", default=False,
        )
        parser.add_argument("-default", dest="default_overlay", default=None)
        parser.add_argument("-position", default="BACKGROUND")
        # Upstream picocli ``-page`` is a Map<Integer,String> — accept the
        # ``<page>=<file>`` syntax once per occurrence, mirroring the
        # picocli rendering.
        parser.add_argument(
            "-page", dest="page", action="append", default=[],
            metavar="N=FILE",
            help="overlay file used for the given page number, may occur more than once",
        )
        parser.add_argument("-i", "--input", dest="infile", required=True)
        parser.add_argument("-o", "--output", dest="outfile", required=True)
        ns = parser.parse_args(args)
        runner = OverlayPDF()
        runner.odd_page_overlay = Path(ns.odd) if ns.odd else None
        runner.even_page_overlay = Path(ns.even) if ns.even else None
        runner.first_page_overlay = Path(ns.first) if ns.first else None
        runner.last_page_overlay = Path(ns.last) if ns.last else None
        runner.use_all_pages = Path(ns.useAllPages) if ns.useAllPages else None
        runner.adjust_rotation = ns.adjustRotation
        runner.default_overlay = Path(ns.default_overlay) if ns.default_overlay else None
        runner.position = Position.value_of(ns.position)
        runner.infile = Path(ns.infile)
        runner.outfile = Path(ns.outfile)
        # Parse ``page`` map entries (one per ``-page N=file``).
        page_map: dict[int, str] = {}
        for entry in ns.page:
            if "=" not in entry:
                raise SystemExit(
                    f"-page expects N=FILE format, got: {entry!r}"
                )
            num_str, _, file_path = entry.partition("=")
            page_map[int(num_str)] = file_path
        runner.specific_page_overlay_file = page_map
        return runner.call()


if __name__ == "__main__":
    sys.exit(OverlayPDF.main(sys.argv[1:]))
