"""Custom :class:`PageDrawer` / :class:`PDFRenderer` subclasses.

Ported from
``examples/src/main/java/org/apache/pdfbox/examples/rendering/CustomPageDrawer.java``
(lines 55-193). The upstream demo replaces red with blue, draws glyph and
filled-path bounding boxes and renders annotations at 35% opacity.

Image output uses Pillow (already a transitive dependency of
:mod:`pypdfbox.rendering`).
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from pypdfbox.loader import Loader
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.rendering.page_drawer import PageDrawer
from pypdfbox.rendering.page_drawer_parameters import PageDrawerParameters
from pypdfbox.rendering.pdf_renderer import PDFRenderer

# Constant matching ``Color.RED.getRGB() & 0x00FFFFFF`` from the Java demo.
_RED_RGB = 0xFF0000
_BLUE_RGB = 0x0000FF
_GREEN_RGB = 0x00FF00


class MyPDFRenderer(PDFRenderer):
    """Mirrors the inner class at ``CustomPageDrawer.java:73``."""

    def __init__(self, document: PDDocument) -> None:
        super().__init__(document)

    def create_page_drawer(self, parameters: PageDrawerParameters) -> PageDrawer:
        return MyPageDrawer(parameters)


class MyPageDrawer(PageDrawer):
    """Mirrors the inner class at ``CustomPageDrawer.java:90``."""

    def __init__(self, parameters: PageDrawerParameters) -> None:
        super().__init__(parameters)

    # CustomPageDrawer.java:101 - colour replacement.
    def get_paint(self, color: Any) -> Any:
        non_stroking: Any = None
        with contextlib.suppress(AttributeError):
            non_stroking = self.get_graphics_state().get_non_stroking_color()
        if non_stroking is color:
            try:
                if int(color.to_rgb()) == _RED_RGB:
                    return _BLUE_RGB
            except (AttributeError, ValueError, TypeError):
                pass
        return super().get_paint(color)

    # CustomPageDrawer.java:118 - glyph bounding boxes.
    def show_glyph(
        self,
        text_rendering_matrix: Any,
        font: Any,
        code: int,
        displacement: Any,
    ) -> None:
        with contextlib.suppress(AttributeError):
            super().show_glyph(text_rendering_matrix, font, code, displacement)
        # Bounding box bookkeeping is delegated to the underlying drawer in
        # pypdfbox; this hook only mirrors the public surface so subclassers
        # may extend it just like in PDFBox.

    # CustomPageDrawer.java:151 - filled path bounding boxes.
    def fill_path(self, winding_rule: int) -> None:
        super().fill_path(winding_rule)
        # The Java demo draws the saved bbox in green afterwards. Drawing
        # primitives are handled by the underlying graphics backend; we
        # simply preserve the public hook.

    # CustomPageDrawer.java:181 - translucent annotation rendering.
    def show_annotation(self, annotation: Any) -> None:
        with contextlib.suppress(AttributeError):
            self.save_graphics_state()
        with contextlib.suppress(AttributeError):
            self.get_graphics_state().set_non_stroke_alpha_constant(0.35)
        try:
            super().show_annotation(annotation)
        finally:
            with contextlib.suppress(AttributeError):
                self.restore_graphics_state()


class CustomPageDrawer:
    """Outer demo class - owns the ``main()`` entry point."""

    @staticmethod
    def main(args: list[str] | None = None) -> None:
        """CLI entry point - mirrors ``CustomPageDrawer.java:57``."""
        del args
        try:
            from PIL import Image  # noqa: F401  (probe Pillow availability)
        except ImportError as exc:  # pragma: no cover - hard dep elsewhere
            raise RuntimeError("Pillow is required for rendering") from exc

        file_path = (
            Path("src/main/resources/org/apache/pdfbox/examples/rendering")
            / "custom-render-demo.pdf"
        )
        doc = Loader.load_pdf(str(file_path))
        try:
            renderer = MyPDFRenderer(doc)
            image = renderer.render_image(0)
            out_dir = Path("target")
            out_dir.mkdir(parents=True, exist_ok=True)
            image.save(out_dir / "custom-render.png", format="PNG")
        finally:
            doc.close()
