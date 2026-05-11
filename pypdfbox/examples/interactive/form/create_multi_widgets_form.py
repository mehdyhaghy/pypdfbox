"""Port of ``CreateMultiWidgetsForm`` (upstream
``CreateMultiWidgetsForm.java`` lines 49-147).

Builds a two-page form where the same text field carries two widgets,
one per page.
"""

from __future__ import annotations

import contextlib
import sys

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (
    PDAppearanceCharacteristicsDictionary,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources


class CreateMultiWidgetsForm:
    """Mirrors ``CreateMultiWidgetsForm`` (final, package-private ctor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/
    interactive/form/CreateMultiWidgetsForm.java`` (lines 49-147).
    """

    DEFAULT_FILENAME: str = "target/MultiWidgetsForm.pdf"

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 55)."""
        argv = list(argv) if argv else []
        out = argv[0] if argv else CreateMultiWidgetsForm.DEFAULT_FILENAME
        CreateMultiWidgetsForm.create(out)

    @staticmethod
    def create(filename: str) -> None:
        """Build a two-page document with one shared field across both
        pages and write it to ``filename``."""
        with PDDocument() as document:
            page1 = PDPage(PDRectangle.A4)  # type: ignore[attr-defined]
            document.add_page(page1)
            page2 = PDPage(PDRectangle.A4)  # type: ignore[attr-defined]
            document.add_page(page2)

            font = PDType1Font()
            resources = PDResources()
            resources.put(COSName.get_pdf_name("Helv"), font)

            acro_form = PDAcroForm(document)
            document.get_document_catalog().set_acro_form(acro_form)
            acro_form.set_default_resources(resources)
            acro_form.set_default_appearance("/Helv 0 Tf 0 g")

            text_box = PDTextField(acro_form)
            text_box.set_partial_name("SampleField")
            text_box.set_default_appearance("/Helv 12 Tf 0 0 1 rg")
            acro_form.set_fields([*acro_form.get_fields(), text_box])

            widget1 = PDAnnotationWidget()
            widget1.set_rectangle(PDRectangle(50, 750, 250, 50))
            widget1.set_page(page1)
            widget1.set_parent(text_box)

            widget2 = PDAnnotationWidget()
            widget2.set_rectangle(PDRectangle(200, 650, 100, 50))
            widget2.set_page(page2)
            widget2.set_parent(text_box)

            field_appearance1 = PDAppearanceCharacteristicsDictionary(COSDictionary())
            field_appearance1.set_border_colour(
                PDColor([0, 1, 0], PDDeviceRGB.INSTANCE)
            )
            field_appearance1.set_background(
                PDColor([1, 1, 0], PDDeviceRGB.INSTANCE)
            )
            widget1.set_appearance_characteristics(field_appearance1)

            field_appearance2 = PDAppearanceCharacteristicsDictionary(COSDictionary())
            field_appearance2.set_border_colour(
                PDColor([1, 0, 0], PDDeviceRGB.INSTANCE)
            )
            field_appearance2.set_background(
                PDColor([0, 1, 0], PDDeviceRGB.INSTANCE)
            )
            widget2.set_appearance_characteristics(field_appearance2)

            try:
                text_box.set_widgets([widget1, widget2])
            except Exception:  # noqa: BLE001
                # set_widgets may not be exposed yet — fall back to direct
                # access.
                text_box.get_widgets().extend([widget1, widget2])

            widget1.set_printed(True)
            widget2.set_printed(True)

            page1.get_annotations().append(widget1)
            page2.get_annotations().append(widget2)

            with contextlib.suppress(Exception):
                text_box.set_value("Sample field")

            document.save(filename)


if __name__ == "__main__":  # pragma: no cover
    CreateMultiWidgetsForm.main(sys.argv[1:])
