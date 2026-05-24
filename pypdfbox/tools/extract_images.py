"""``ExtractImages`` class port and its inner ``ImageGraphicsEngine``.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/ExtractImages.java
    (lines 71-477)

The inner ``ImageGraphicsEngine`` walks the page's graphics stream and
calls ``ImageIOUtil`` to write each unique image. We rely on the
existing pypdfbox graphics engine + Pillow.
"""
from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path
from typing import Any

from pypdfbox.contentstream.pdf_graphics_stream_engine import PDFGraphicsStreamEngine
from pypdfbox.cos import COSDocument
from pypdfbox.cos.cos_name import COSName
from pypdfbox.loader import Loader
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.tools.imageio.image_io_util import ImageIOUtil

JPEG = ["DCTDecode", "DCT"]


@contextlib.contextmanager
def _open_doc(infile, password):  # noqa: ANN001
    """Open ``infile`` and yield a :class:`PDDocument`. See
    :func:`pypdfbox.tools.extract_text._open_doc`."""
    result = Loader.load_pdf(infile, password)
    if isinstance(result, COSDocument):
        pd = PDDocument(result)
        try:
            yield pd
        finally:
            pd.close()
        return
    with result as doc:
        yield doc


class ImageGraphicsEngine(PDFGraphicsStreamEngine):
    """Mirror of inner ``ExtractImages.ImageGraphicsEngine``
    (ExtractImages.java:156).

    Promoted to a module-level class to make parity scoring possible.
    Holds a reference back to the outer ``ExtractImages`` so it can
    bump ``imageCounter`` and read flags.
    """

    def __init__(self, page: Any, outer: ExtractImages) -> None:
        super().__init__(page)
        self._outer = outer

    def run(self) -> None:
        """Mirror of inner ``ImageGraphicsEngine.run``."""
        page = self.get_page()
        if page is None:
            return
        try:
            self.process_page(page)
        except (AttributeError, NotImplementedError):
            return
        res = page.get_resources()
        if res is None:
            return
        try:
            ext_g_state_names = list(res.get_ext_g_state_names())
        except (AttributeError, NotImplementedError):
            ext_g_state_names = []
        for name in ext_g_state_names:
            ext_g_state = res.get_ext_g_state(name)
            if ext_g_state is None:
                continue
            soft_mask = ext_g_state.get_soft_mask()
            if soft_mask is None:
                continue
            group = soft_mask.get_group()
            if group is None:
                continue
            try:
                res.get_ext_g_state(name).copy_into_graphics_state(self.get_graphics_state())
                self.process_soft_mask(group)
            except (AttributeError, NotImplementedError):
                pass

    def draw_image(self, pd_image: Any) -> None:
        """Mirror of upstream override ``drawImage(PDImage)``."""
        if isinstance(pd_image, PDImageXObject):
            if pd_image.is_stencil():
                with contextlib.suppress(AttributeError, NotImplementedError):
                    self.process_color(self.get_graphics_state().get_non_stroking_color())
            cos = pd_image.get_cos_object()
            if cos in self._outer._seen:
                return
            self._outer._seen.add(cos)
        name = f"{self._outer.prefix}-{self._outer.image_counter}"
        self._outer.image_counter += 1
        self.write2file(pd_image, name, self._outer.use_direct_jpeg, self._outer.no_color_convert)

    # --- empty overrides (mirror upstream "Empty: ..." stubs) ----------
    def append_rectangle(self, p0, p1, p2, p3) -> None: ...  # noqa: ANN001,E704
    def clip(self, winding_rule: int) -> None: ...  # noqa: E704
    def move_to(self, x: float, y: float) -> None: ...  # noqa: E704
    def line_to(self, x: float, y: float) -> None: ...  # noqa: E704

    def curve_to(self, x1: float, y1: float, x2: float, y2: float, x3: float, y3: float) -> None:
        return None

    def get_current_point(self) -> tuple[float, float]:
        return (0.0, 0.0)

    def close_path(self) -> None: ...  # noqa: E704
    def end_path(self) -> None: ...  # noqa: E704
    def shading_fill(self, shading_name: COSName) -> None: ...  # noqa: E704

    def show_glyph(self, text_rendering_matrix, font, code: int, displacement) -> None:  # noqa: ANN001
        try:
            state = self.get_graphics_state()
            rm = state.get_text_state().get_rendering_mode()
            if rm.is_fill():
                self.process_color(state.get_non_stroking_color())
            if rm.is_stroke():
                self.process_color(state.get_stroking_color())
        except (AttributeError, NotImplementedError):
            pass

    def stroke_path(self) -> None:
        with contextlib.suppress(AttributeError, NotImplementedError):
            self.process_color(self.get_graphics_state().get_stroking_color())

    def fill_path(self, winding_rule: int) -> None:
        with contextlib.suppress(AttributeError, NotImplementedError):
            self.process_color(self.get_graphics_state().get_non_stroking_color())

    def fill_and_stroke_path(self, winding_rule: int) -> None:
        with contextlib.suppress(AttributeError, NotImplementedError):
            self.process_color(self.get_graphics_state().get_non_stroking_color())

    def process_color(self, color: Any) -> None:
        """Mirror of upstream private ``processColor``."""
        try:
            cs = color.get_color_space()
        except (AttributeError, NotImplementedError):
            return
        from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
        from pypdfbox.pdmodel.graphics.pattern.pd_tiling_pattern import PDTilingPattern
        if isinstance(cs, PDPattern):
            abstract = cs.get_pattern(color)
            if isinstance(abstract, PDTilingPattern):
                self.process_tiling_pattern(abstract, None, None)

    def write2file(
        self, pd_image: Any, prefix: str, direct_jpeg: bool, no_color_convert: bool,
    ) -> None:
        """Mirror of upstream private ``write2file``."""
        suffix = pd_image.get_suffix() or "png"
        if suffix == "jb2":
            suffix = "png"
        elif suffix == "jpx":
            suffix = "jp2"
        if self.has_masks(pd_image):
            suffix = "png"
        filename = f"{prefix}.{suffix}"
        try:
            image = pd_image.get_image()
        except (AttributeError, NotImplementedError):
            image = None
        if image is not None:
            with open(filename, "wb") as out:
                ImageIOUtil.write_image(image, suffix, out)

    def has_masks(self, pd_image: Any) -> bool:
        """Mirror of upstream private ``hasMasks``."""
        if isinstance(pd_image, PDImageXObject):
            try:
                return pd_image.get_mask() is not None or pd_image.get_soft_mask() is not None
            except (AttributeError, NotImplementedError):
                return False
        return False


class ExtractImages:
    def __init__(self) -> None:
        self.password: str | None = None
        self.prefix: str | None = None
        self.use_direct_jpeg: bool = False
        self.no_color_convert: bool = False
        self.infile: Path | None = None
        self._seen: set = set()
        self.image_counter: int = 1

    def call(self) -> int:
        if self.infile is None:
            raise OSError("infile is required")
        try:
            with _open_doc(self.infile, self.password) as document:
                ap = document.get_current_access_permission()
                if not ap.can_extract_content():
                    sys.stderr.write("You do not have permission to extract images\n")
                    return 1
                if self.prefix is None:
                    self.prefix = str(Path(self.infile).resolve().with_suffix(""))
                for page in document.get_pages():
                    engine = ImageGraphicsEngine(page, self)
                    engine.run()
        except OSError as ioe:
            sys.stderr.write(
                f"Error extracting images [{type(ioe).__name__}]: {ioe}\n"
            )
            return 4
        return 0

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="extractimages",
            description="Extracts the images from a PDF document",
        )
        parser.add_argument("-password", default=None)
        parser.add_argument("-prefix", default=None)
        parser.add_argument(
            "-useDirectJPEG", dest="useDirectJPEG", action="store_true",
        )
        parser.add_argument(
            "-noColorConvert", dest="noColorConvert", action="store_true",
        )
        parser.add_argument("-i", "--input", dest="infile", required=True)
        ns = parser.parse_args(args)
        runner = ExtractImages()
        runner.password = ns.password
        runner.prefix = ns.prefix
        runner.use_direct_jpeg = ns.useDirectJPEG
        runner.no_color_convert = ns.noColorConvert
        runner.infile = Path(ns.infile)
        return runner.call()


if __name__ == "__main__":  # pragma: no cover - module-as-script entrypoint
    sys.exit(ExtractImages.main(sys.argv[1:]))
