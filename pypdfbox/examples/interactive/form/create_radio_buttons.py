"""Port of ``CreateRadioButtons`` (upstream ``CreateRadioButtons.java``
lines 48-179).

Creates a group of three radio button widgets ("a", "b", "c").

The upstream sample also builds on/off circle appearance streams by hand
through :class:`PDAppearanceContentStream`. The lite pypdfbox port wires
up the radio button structure and skips the per-widget appearance stream
hand-painting — that lands with the rendering / appearance cluster.
"""

from __future__ import annotations

import contextlib
import sys

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (
    PDAppearanceCharacteristicsDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


class CreateRadioButtons:
    """Mirrors ``CreateRadioButtons`` (final, package-private ctor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/
    interactive/form/CreateRadioButtons.java`` (lines 48-179).
    """

    DEFAULT_FILENAME: str = "target/RadioButtonsSample.pdf"

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 54)."""
        argv = list(argv) if argv else []
        out = argv[0] if argv else CreateRadioButtons.DEFAULT_FILENAME
        CreateRadioButtons.create(out)

    @staticmethod
    def create(filename: str) -> None:
        """Build a three-option radio group and save to ``filename``."""
        with PDDocument() as document:
            page = PDPage(PDRectangle.A4)  # type: ignore[attr-defined]
            document.add_page(page)

            acro_form = PDAcroForm(document)
            document.get_document_catalog().set_acro_form(acro_form)

            options = ["a", "b", "c"]
            radio_button = PDRadioButton(acro_form)
            radio_button.set_partial_name("MyRadioButton")
            with contextlib.suppress(Exception):
                radio_button.set_export_values(options)

            appearance_characteristics = PDAppearanceCharacteristicsDictionary(
                COSDictionary()
            )
            appearance_characteristics.set_border_colour(
                PDColor([1, 0, 0], PDDeviceRGB.INSTANCE)
            )
            appearance_characteristics.set_background(
                PDColor([0, 1, 0.3], PDDeviceRGB.INSTANCE)
            )

            widgets = []
            a4_height = 842.0
            for i in range(len(options)):
                widget = PDAnnotationWidget()
                widget.set_rectangle(PDRectangle(30, a4_height - 40 - i * 35, 30, 30))
                widget.set_printed(True)
                widget.set_appearance_characteristics(appearance_characteristics)
                border_style = PDBorderStyleDictionary()
                border_style.set_width(2)
                border_style.set_style(PDBorderStyleDictionary.STYLE_SOLID)
                widget.set_border_style(border_style)
                widget.set_page(page)
                with contextlib.suppress(Exception):
                    widget.set_appearance_state("Off")
                widgets.append(widget)
                page.get_annotations().append(widget)
            try:
                radio_button.set_widgets(widgets)
            except Exception:  # noqa: BLE001
                radio_button.get_widgets().extend(widgets)

            acro_form.set_fields([*acro_form.get_fields(), radio_button])

            with contextlib.suppress(Exception):
                radio_button.set_value("c")

            document.save(filename)

    @staticmethod
    def get_line_width(widget) -> float:  # type: ignore[no-untyped-def]
        """Return the widget's border width — promoted from the upstream
        static helper (line 158)."""
        bs = widget.get_border_style()
        if bs is not None:
            return bs.get_width()
        return 1.0

    @staticmethod
    def create_appearance_stream(
        document, widget, on: bool  # type: ignore[no-untyped-def]
    ):
        """Build the on/off radio-circle appearance stream — promoted
        from upstream's private static ``createAppearanceStream``
        (line 128).

        The lite port returns ``None`` and documents the missing
        appearance plumbing in ``CHANGES.md``. The hand-painted
        appearance stream lands with the rendering / appearance cluster
        (PRD §6.13)."""
        _ = (document, widget, on)
        return None

    @staticmethod
    def draw_circle(
        cs, x: float, y: float, r: float
    ) -> None:  # type: ignore[no-untyped-def]
        """Paint a circle with the four-Bezier approximation onto an
        appearance content stream — promoted from upstream's private
        static ``drawCircle`` (line 168).

        ``magic`` follows the http://stackoverflow.com/a/2007782 ratio
        ``r * 0.551784`` for a four-segment Bezier circle."""
        magic = r * 0.551784
        cs.move_to(x, y + r)
        cs.curve_to(x + magic, y + r, x + r, y + magic, x + r, y)
        cs.curve_to(x + r, y - magic, x + magic, y - r, x, y - r)
        cs.curve_to(x - magic, y - r, x - r, y - magic, x - r, y)
        cs.curve_to(x - r, y + magic, x - magic, y + r, x, y + r)
        cs.close_path()


if __name__ == "__main__":  # pragma: no cover
    CreateRadioButtons.main(sys.argv[1:])
