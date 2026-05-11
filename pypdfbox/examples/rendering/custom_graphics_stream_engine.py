"""Custom :class:`PDFGraphicsStreamEngine` subclass.

Ported from
``examples/src/main/java/org/apache/pdfbox/examples/rendering/CustomGraphicsStreamEngine.java``
(lines 45-200). The Java demo prints every drawing operation to stdout;
the port preserves that behaviour by writing to ``sys.stdout`` so the
example reads identically to a PDFBox user.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pypdfbox.contentstream.pdf_graphics_stream_engine import (
    PDFGraphicsStreamEngine,
)
from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_name import COSName
from pypdfbox.loader import Loader
from pypdfbox.pdmodel.pd_page import PDPage


class CustomGraphicsStreamEngine(PDFGraphicsStreamEngine):
    """Example custom stream engine — prints every operation to stdout."""

    def __init__(self, page: PDPage) -> None:
        super().__init__(page)

    @staticmethod
    def main(args: list[str] | None = None) -> None:
        """CLI entry point — mirrors the Java ``main`` (line 57)."""
        del args
        file_path = (
            Path("src/main/resources/org/apache/pdfbox/examples/rendering")
            / "custom-render-demo.pdf"
        )
        doc = Loader.load_pdf(str(file_path))
        try:
            page = doc.get_page(0)
            engine = CustomGraphicsStreamEngine(page)
            engine.run()
        finally:
            doc.close()

    def run(self) -> None:
        """Process the current page and any annotations (line 75)."""
        self.process_page(self.get_page())
        for annotation in self.get_page().get_annotations():
            self.show_annotation(annotation)

    def append_rectangle(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
        p3: tuple[float, float],
    ) -> None:
        print(
            f"appendRectangle {p0[0]:.2f} {p0[1]:.2f}, "
            f"{p1[0]:.2f} {p1[1]:.2f}, "
            f"{p2[0]:.2f} {p2[1]:.2f}, "
            f"{p3[0]:.2f} {p3[1]:.2f}",
            file=sys.stdout,
        )

    def draw_image(self, pd_image: Any) -> None:
        print("drawImage", file=sys.stdout)

    def clip(self, winding_rule: int) -> None:
        print("clip", file=sys.stdout)

    def move_to(self, x: float, y: float) -> None:
        print(f"moveTo {x:.2f} {y:.2f}", file=sys.stdout)

    def line_to(self, x: float, y: float) -> None:
        print(f"lineTo {x:.2f} {y:.2f}", file=sys.stdout)

    def curve_to(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        x3: float,
        y3: float,
    ) -> None:
        print(
            f"curveTo {x1:.2f} {y1:.2f}, {x2:.2f} {y2:.2f}, {x3:.2f} {y3:.2f}",
            file=sys.stdout,
        )

    def get_current_point(self) -> tuple[float, float]:
        # As in the upstream sample (line 124): the demo doesn't track paths.
        return (0.0, 0.0)

    def close_path(self) -> None:
        print("closePath", file=sys.stdout)

    def end_path(self) -> None:
        print("endPath", file=sys.stdout)

    def stroke_path(self) -> None:
        print("strokePath", file=sys.stdout)

    def fill_path(self, winding_rule: int) -> None:
        print("fillPath", file=sys.stdout)

    def fill_and_stroke_path(self, winding_rule: int) -> None:
        print("fillAndStrokePath", file=sys.stdout)

    def shading_fill(self, shading_name: COSName) -> None:
        print(f"shadingFill {shading_name}", file=sys.stdout)

    def show_text_string(self, string: bytes) -> None:
        sys.stdout.write('showTextString "')
        try:
            super_method = super().show_text_string  # type: ignore[attr-defined]
        except AttributeError:
            super_method = None
        if super_method is not None:
            super_method(string)
        print('"', file=sys.stdout)

    def show_text_strings(self, array: COSArray) -> None:
        sys.stdout.write('showTextStrings "')
        try:
            super_method = super().show_text_strings  # type: ignore[attr-defined]
        except AttributeError:
            super_method = None
        if super_method is not None:
            super_method(array)
        print('"', file=sys.stdout)

    def show_glyph(
        self,
        text_rendering_matrix: Any,
        font: Any,
        code: int,
        displacement: Any,
    ) -> None:
        sys.stdout.write(f"showGlyph {code}")
        try:
            super_method = super().show_glyph  # type: ignore[attr-defined]
        except AttributeError:
            super_method = None
        if super_method is not None:
            super_method(text_rendering_matrix, font, code, displacement)
