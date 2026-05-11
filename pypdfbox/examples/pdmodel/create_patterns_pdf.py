"""Port of ``org.apache.pdfbox.examples.pdmodel.CreatePatternsPDF`` (lines 39-130).

Creates a PDF that uses a colored and an uncolored tiling pattern.

Deviation: upstream drives the per-tile cell content via
``PDPatternContentStream``, which isn't ported in pypdfbox yet. We emit
the same operator sequence directly into the tile's backing
``COSStream`` (raw bytes — no filter). Output is byte-equivalent at the
operator level to what upstream would produce.
"""

from __future__ import annotations

import sys

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
from pypdfbox.pdmodel.graphics.pattern.pd_tiling_pattern import PDTilingPattern
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources


def _set_tile_contents(pattern: PDTilingPattern, operators: str) -> None:
    """Write the tile cell's operator stream verbatim onto the pattern's
    backing ``COSStream``. Equivalent to wrapping ``PDPatternContentStream``
    around the pattern, writing the same operators, and closing — but
    avoids the missing ``PDPatternContentStream`` port (documented above).
    """
    cos_object = pattern.get_cos_object()
    if not isinstance(cos_object, COSStream):
        raise TypeError(
            "PDTilingPattern must be backed by a COSStream to carry "
            "tile content"
        )
    cos_object.set_raw_data(operators.encode("ascii"))


class CreatePatternsPDF:
    """Mirrors ``CreatePatternsPDF`` (final class, line 39)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 45).

        Deviation: when called with no arguments, writes to
        ``patterns.pdf`` in the current working directory (matches
        upstream's hard-coded ``doc.save("patterns.pdf")``). When called
        with one argument, writes to that path — useful for tests that
        pin output to a ``tmp_path``.
        """
        argv = argv if argv is not None else []
        if len(argv) == 0:
            output_path = "patterns.pdf"
        elif len(argv) == 1:
            output_path = argv[0]
        else:
            sys.stderr.write(
                "Usage: CreatePatternsPDF [<output-pdf>]\n",
            )
            raise SystemExit(1)

        with PDDocument() as doc:
            page = PDPage()
            doc.add_page(page)
            page.set_resources(PDResources())

            with PDPageContentStream(doc, page) as pcs:
                # ---- Colored tiling pattern (PaintType=1) ----
                # The pattern colour space carries no underlying CS for
                # the colored form — the cell's content stream sets its
                # own colours.
                pattern_cs1 = PDPattern(None, resources=page.get_resources())

                tiling_pattern1 = PDTilingPattern()
                tiling_pattern1.set_b_box(PDRectangle(0, 0, 10, 10))
                tiling_pattern1.set_paint_type(PDTilingPattern.PAINT_COLORED)
                tiling_pattern1.set_tiling_type(
                    PDTilingPattern.TILING_CONSTANT_SPACING,
                )
                tiling_pattern1.set_x_step(10)
                tiling_pattern1.set_y_step(10)

                # Diagonal red line plus two short stubs in the corners
                # so adjacent tiles align cleanly.
                _set_tile_contents(
                    tiling_pattern1,
                    "1 0 0 RG\n"
                    "0 0 m\n"
                    "10 10 l\n"
                    "-1 9 m\n"
                    "1 11 l\n"
                    "9 -1 m\n"
                    "11 1 l\n"
                    "S\n",
                )

                pattern_name1 = page.get_resources().add(tiling_pattern1)

                pattern_color1 = PDColor(pattern_name1, pattern_cs1)
                pcs.set_non_stroking_color(pattern_color1)
                pcs.add_rect(50, 500, 200, 200)
                pcs.fill()

                # ---- Uncolored tiling pattern (PaintType=2) ----
                tiling_pattern2 = PDTilingPattern()
                tiling_pattern2.set_b_box(PDRectangle(0, 0, 10, 10))
                tiling_pattern2.set_paint_type(PDTilingPattern.PAINT_UNCOLORED)
                tiling_pattern2.set_tiling_type(
                    PDTilingPattern.TILING_NO_DISTORTION,
                )
                tiling_pattern2.set_x_step(10)
                tiling_pattern2.set_y_step(10)

                # Draw a plus sign (cross) per tile; the tile is colour-less,
                # so the caller's colour (set via the Pattern color space)
                # tints the strokes.
                _set_tile_contents(
                    tiling_pattern2,
                    "0 5 m\n10 5 l\n5 0 m\n5 10 l\nS\n",
                )

                pattern_name2 = page.get_resources().add(tiling_pattern2)

                # Uncolored Pattern colour space needs an underlying CS for
                # the tint components supplied at paint time.
                pattern_cs2 = PDPattern(
                    PDDeviceRGB.INSTANCE,
                    resources=page.get_resources(),
                )

                # Same uncolored pattern painted twice — first green, then
                # blue with a slight tile-origin offset so the tiles don't
                # line up exactly between the two boxes.
                pattern_color2_green = PDColor(
                    [0.0, 1.0, 0.0], pattern_name2, pattern_cs2,
                )
                pcs.set_non_stroking_color(pattern_color2_green)
                pcs.add_rect(300, 500, 100, 100)
                pcs.fill()

                pattern_color2_blue = PDColor(
                    [0.0, 0.0, 1.0], pattern_name2, pattern_cs2,
                )
                pcs.set_non_stroking_color(pattern_color2_blue)
                pcs.add_rect(455, 505, 100, 100)
                pcs.fill()

            doc.save(output_path)
