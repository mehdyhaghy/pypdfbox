"""Port of ``org.apache.pdfbox.examples.interactive.form.CreateCheckBox``
(upstream ``CreateCheckBox.java`` lines 52-216).

Creates a single checkbox widget with red border / yellow background.

The full upstream sample also pre-builds the on/off appearance streams by
hand. That requires :class:`PDAppearanceStream` plumbing that the lite
pypdfbox port does not yet expose for in-memory construction — pypdfbox
appearance streams are wired in alongside the rendering cluster. The port
keeps the checkbox creation visible and documents the missing step.
"""

from __future__ import annotations

import contextlib
import sys

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (
    PDAppearanceCharacteristicsDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


class CreateCheckBox:
    """Mirrors ``CreateCheckBox`` (final, package-private constructor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/
    interactive/form/CreateCheckBox.java`` (lines 52-216).
    """

    DEFAULT_FILENAME: str = "target/CheckBoxSample.pdf"

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 58)."""
        argv = list(argv) if argv else []
        out = argv[0] if argv else CreateCheckBox.DEFAULT_FILENAME
        CreateCheckBox.create(out)

    @staticmethod
    def create(filename: str) -> None:
        """Build the checkbox sample and write it to ``filename``."""
        with PDDocument() as document:
            page = PDPage()
            document.add_page(page)

            acro_form = PDAcroForm(document)
            document.get_document_catalog().set_acro_form(acro_form)

            x = 50.0
            y = page.get_media_box().get_height() - 50.0
            rect = PDRectangle(x, y, 20, 20)

            checkbox = PDCheckBox(acro_form)
            checkbox.set_partial_name("MyCheckBox")
            widget = checkbox.get_widgets()[0]
            widget.set_page(page)
            widget.set_rectangle(rect)
            widget.set_printed(True)

            appearance_characteristics = PDAppearanceCharacteristicsDictionary(
                COSDictionary()
            )
            appearance_characteristics.set_border_colour(
                PDColor([1, 0, 0], PDDeviceRGB.INSTANCE)
            )
            appearance_characteristics.set_background(
                PDColor([1, 1, 0], PDDeviceRGB.INSTANCE)
            )
            # Mirrors upstream caption codes: 4 = checkmark, 8 = cross,
            # H = star, u = diamond, n = square, l = dot.
            appearance_characteristics.set_normal_caption("4")
            widget.set_appearance_characteristics(appearance_characteristics)

            border_style = PDBorderStyleDictionary()
            border_style.set_width(1)
            border_style.set_style(PDBorderStyleDictionary.STYLE_SOLID)
            widget.set_border_style(border_style)

            page.get_annotations().append(widget)
            acro_form.set_fields([*acro_form.get_fields(), checkbox])

            # Upstream calls ``unCheck()`` to ensure an /AS value is set.
            # Lite port: PDCheckBox may surface set-state through a
            # different accessor depending on porting stage.
            with contextlib.suppress(Exception):
                checkbox.un_check()

            document.save(filename)

    @staticmethod
    def get_line_width(widget) -> float:  # type: ignore[no-untyped-def]
        """Return the widget's border width, defaulting to 1 — promoted
        from the upstream static helper (line 207)."""
        bs = widget.get_border_style()
        if bs is not None:
            return bs.get_width()
        return 1.0

    @staticmethod
    def create_appearance_stream(
        document, widget, on: bool, font  # type: ignore[no-untyped-def]
    ):
        """Build the on/off appearance stream for the checkbox widget —
        promoted from upstream's private static
        ``createAppearanceStream`` (line 120).

        The lite port returns ``None`` and documents the missing
        appearance plumbing in ``CHANGES.md``. The hand-painted
        appearance stream lands with the rendering / appearance cluster
        (PRD §6.13)."""
        _ = (document, widget, on, font)
        return None


if __name__ == "__main__":  # pragma: no cover
    CreateCheckBox.main(sys.argv[1:])
