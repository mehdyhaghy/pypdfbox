"""``ImageToPDF`` class port — wraps images into a PDF document.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/ImageToPDF.java
    (lines 38-227)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


class ImageToPDF:
    def __init__(self) -> None:
        self.media_box: PDRectangle = PDRectangle.LETTER
        self.auto_orientation: bool = False
        self.landscape: bool = False
        self.page_size: str = "Letter"
        self.resize: bool = False
        self.infiles: list[Path] = []
        self.outfile: Path | None = None

    def call(self) -> int:
        self.set_media_box(self.create_rectangle(self.page_size))
        try:
            with PDDocument() as doc:
                for image_file in self.infiles:
                    pd_image = PDImageXObject.create_from_file(str(Path(image_file).resolve()), doc)
                    actual = self.media_box
                    needs_rotate = (
                        self.auto_orientation
                        and pd_image.get_width() > pd_image.get_height()
                    ) or self.landscape
                    if needs_rotate:
                        actual = PDRectangle(
                            self.media_box.get_height(),
                            self.media_box.get_width(),
                        )
                    page = PDPage(actual)
                    doc.add_page(page)
                    with PDPageContentStream(doc, page) as contents:
                        if self.resize:
                            contents.draw_image(
                                pd_image, 0, 0,
                                actual.get_width(), actual.get_height(),
                            )
                        else:
                            contents.draw_image(
                                pd_image, 0, 0,
                                pd_image.get_width(), pd_image.get_height(),
                            )
                if self.outfile is None:
                    raise OSError("outfile is required")
                doc.save(self.outfile)
        except OSError as ioe:
            sys.stderr.write(
                f"Error converting image to PDF [{type(ioe).__name__}]: {ioe}\n"
            )
            return 4
        return 0

    @staticmethod
    def create_rectangle(paper_size: str) -> PDRectangle:
        """Mirror of upstream private static ``createRectangle``."""
        table = {
            "letter": PDRectangle.LETTER,
            "legal": PDRectangle.LEGAL,
            "a0": PDRectangle.A0,
            "a1": PDRectangle.A1,
            "a2": PDRectangle.A2,
            "a3": PDRectangle.A3,
            "a4": PDRectangle.A4,
            "a5": PDRectangle.A5,
            "a6": PDRectangle.A6,
        }
        return table.get(paper_size.lower(), PDRectangle.LETTER)

    def get_media_box(self) -> PDRectangle:
        return self.media_box

    def set_media_box(self, media_box: PDRectangle) -> None:
        self.media_box = media_box

    def is_landscape(self) -> bool:
        return self.landscape

    def set_landscape(self, landscape: bool) -> None:
        self.landscape = landscape

    def is_auto_orientation(self) -> bool:
        return self.auto_orientation

    def set_auto_orientation(self, auto_orientation: bool) -> None:
        self.auto_orientation = auto_orientation

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="imagetopdf", description="Creates a PDF document from images",
        )
        parser.add_argument(
            "-autoOrientation", dest="autoOrientation", action="store_true",
        )
        parser.add_argument("-landscape", action="store_true")
        parser.add_argument("-pageSize", dest="pageSize", default="Letter")
        parser.add_argument("-resize", action="store_true")
        parser.add_argument("-i", "--input", dest="infiles", nargs="+", required=True)
        parser.add_argument("-o", "--output", dest="outfile", required=True)
        ns = parser.parse_args(args)
        runner = ImageToPDF()
        runner.auto_orientation = ns.autoOrientation
        runner.landscape = ns.landscape
        runner.page_size = ns.pageSize
        runner.resize = ns.resize
        runner.infiles = [Path(p) for p in ns.infiles]
        runner.outfile = Path(ns.outfile)
        return runner.call()


if __name__ == "__main__":
    sys.exit(ImageToPDF.main(sys.argv[1:]))
