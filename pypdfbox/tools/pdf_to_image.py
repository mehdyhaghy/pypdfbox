"""``PDFToImage`` class port — renders PDF pages to image files.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/PDFToImage.java
    (lines 52-221)

We use the existing pypdfbox renderer and the ``ImageIOUtil`` codec
helper. Pillow + ``ImageIOUtil`` cover JPEG / PNG / TIFF output.
"""
from __future__ import annotations

import argparse
import contextlib
import sys
import time
from pathlib import Path

from pypdfbox.loader import Loader
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.rendering.pdf_renderer import PDFRenderer
from pypdfbox.tools.imageio.image_io_util import ImageIOUtil


class PDFToImage:
    def __init__(self) -> None:
        self.password: str | None = None
        self.image_format: str = "jpg"
        self.output_prefix: str | None = None
        self.page: int = -1
        self.start_page: int = 1
        self.end_page: int = 2**31 - 1
        self.image_type: str = "RGB"
        self.dpi: int = 0
        self.quality: float = -1.0
        self.cropbox: list[int] | None = None
        self.show_time: bool = False
        self.subsampling: bool = False
        self.infile: Path | None = None

    def call(self) -> int:
        if self.infile is None:
            raise OSError("infile is required")
        if self.output_prefix is None:
            self.output_prefix = str(Path(self.infile).resolve().with_suffix(""))

        supported = ImageIOUtil.get_writer_format_names()
        if self.image_format not in supported:
            sys.stderr.write(
                f"Error: Invalid image format {self.image_format} - "
                f"supported formats: {', '.join(supported)}\n"
            )
            return 2

        if self.quality < 0:
            self.quality = 0.0 if self.image_format == "png" else 1.0

        if self.dpi == 0:
            # Headless environments default to 96 (matches upstream HeadlessException branch).
            self.dpi = 96

        try:
            with Loader.load_pdf(self.infile, self.password) as document:
                try:
                    form = document.get_document_catalog().get_acro_form()
                    if form is not None and getattr(form, "get_need_appearances", lambda: False)():
                        form.refresh_appearances()
                except (AttributeError, NotImplementedError):
                    pass

                if self.cropbox is not None and len(self.cropbox) == 4:
                    self.change_crop_box(document, *self.cropbox)

                start = time.perf_counter_ns()
                if self.page != -1:
                    self.start_page = self.page
                    self.end_page = self.page
                success = True
                end_page = min(self.end_page, document.get_number_of_pages())
                renderer = PDFRenderer(document)
                with contextlib.suppress(AttributeError):
                    renderer.set_subsampling_allowed(self.subsampling)
                for i in range(self.start_page - 1, end_page):
                    image = renderer.render_image_with_dpi(i, self.dpi, self.image_type)
                    filename = f"{self.output_prefix}-{i + 1}.{self.image_format}"
                    ok = ImageIOUtil.write_image(image, filename, self.dpi, self.quality)
                    success = success and ok

                end = time.perf_counter_ns()
                duration_ms = (end - start) // 1_000_000
                count = 1 + end_page - self.start_page
                if self.show_time:
                    plural = "" if count == 1 else "s"
                    sys.stderr.write(
                        f"Rendered {count} page{plural} in {duration_ms}ms\n"
                    )
                if not success:
                    sys.stderr.write(
                        f"Error: no writer found for image format '{self.image_format}'\n"
                    )
                    return 1
        except OSError as ioe:
            sys.stderr.write(
                f"Error converting document [{type(ioe).__name__}]: {ioe}\n"
            )
            return 4
        return 0

    @staticmethod
    def change_crop_box(document, a: float, b: float, c: float, d: float) -> None:  # noqa: ANN001
        """Mirror of upstream private static ``changeCropBox``."""
        for page in document.get_pages():
            rect = PDRectangle()
            rect.set_lower_left_x(a)
            rect.set_lower_left_y(b)
            rect.set_upper_right_x(c)
            rect.set_upper_right_y(d)
            page.set_crop_box(rect)

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="pdftoimage", description="Converts a PDF document to image(s)",
        )
        parser.add_argument("-password", default=None)
        parser.add_argument("-format", dest="format", default="jpg")
        parser.add_argument("-prefix", "-outputPrefix", dest="prefix", default=None)
        parser.add_argument("-page", type=int, default=-1)
        parser.add_argument("-startPage", dest="startPage", type=int, default=1)
        parser.add_argument(
            "-endPage", dest="endPage", type=int, default=2**31 - 1,
        )
        parser.add_argument("-color", dest="color", default="RGB")
        parser.add_argument("-dpi", "-resolution", dest="dpi", type=int, default=0)
        parser.add_argument("-quality", type=float, default=-1.0)
        parser.add_argument("-cropbox", nargs=4, type=int, default=None)
        parser.add_argument("-time", action="store_true", dest="show_time")
        parser.add_argument("-subsampling", action="store_true")
        parser.add_argument("-i", "--input", dest="infile", required=True)
        ns = parser.parse_args(args)
        runner = PDFToImage()
        runner.password = ns.password
        runner.image_format = ns.format
        runner.output_prefix = ns.prefix
        runner.page = ns.page
        runner.start_page = ns.startPage
        runner.end_page = ns.endPage
        runner.image_type = ns.color
        runner.dpi = ns.dpi
        runner.quality = ns.quality
        runner.cropbox = ns.cropbox
        runner.show_time = ns.show_time
        runner.subsampling = ns.subsampling
        runner.infile = Path(ns.infile)
        return runner.call()


if __name__ == "__main__":
    sys.exit(PDFToImage.main(sys.argv[1:]))
