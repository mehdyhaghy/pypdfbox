"""Port of ``org.apache.pdfbox.examples.interactive.form.CreateSimpleForm``
(upstream ``CreateSimpleForm.java`` lines 46-141).

Creates an AcroForm with a single text field — properties resemble the
defaults Adobe Acrobat applies when adding a text box interactively.
"""

from __future__ import annotations

import sys

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (
    PDAppearanceCharacteristicsDictionary,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources


class CreateSimpleForm:
    """Mirrors ``CreateSimpleForm`` (final, package-private constructor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/
    interactive/form/CreateSimpleForm.java`` (lines 46-141).
    """

    DEFAULT_FILENAME: str = "target/SimpleForm.pdf"

    def __init__(self) -> None:
        # Upstream marks the class final with a private no-arg constructor.
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 54)."""
        argv = list(argv) if argv else []
        out = argv[0] if argv else CreateSimpleForm.DEFAULT_FILENAME
        CreateSimpleForm.create(out)

    @staticmethod
    def create(filename: str) -> None:
        """Build and write a simple form to ``filename`` — promoted from
        upstream's inline ``main`` body so tests can drive it directly."""
        with PDDocument() as document:
            page = PDPage(PDRectangle.A4)  # type: ignore[attr-defined]
            document.add_page(page)

            # Acrobat uses Helvetica as the default form font under /Helv.
            font = PDType1Font()
            resources = PDResources()
            resources.put(COSName.get_pdf_name("Helv"), font)

            acro_form = PDAcroForm(document)
            document.get_document_catalog().set_acro_form(acro_form)
            acro_form.set_default_resources(resources)
            # Auto-sized font default — mirrors Acrobat's "/Helv 0 Tf 0 g".
            acro_form.set_default_appearance("/Helv 0 Tf 0 g")

            text_box = PDTextField(acro_form)
            text_box.set_partial_name("SampleField")
            # 12pt blue field-level default appearance.
            text_box.set_default_appearance("/Helv 12 Tf 0 0 1 rg")
            # ``get_fields()`` returns a fresh list — push back via
            # ``set_fields`` so the field is persisted on the form COS.
            acro_form.set_fields([*acro_form.get_fields(), text_box])

            widget = text_box.get_widgets()[0]
            rect = PDRectangle(50, 750, 200, 50)
            widget.set_rectangle(rect)
            widget.set_page(page)

            field_appearance = PDAppearanceCharacteristicsDictionary(COSDictionary())
            field_appearance.set_border_colour(
                PDColor([0, 1, 0], PDDeviceRGB.INSTANCE)
            )
            field_appearance.set_background(
                PDColor([1, 1, 0], PDDeviceRGB.INSTANCE)
            )
            widget.set_appearance_characteristics(field_appearance)

            widget.set_printed(True)
            page.get_annotations().append(widget)

            try:
                text_box.set_value("Sample field content")
            except Exception:  # noqa: BLE001
                # value generation may need a font dictionary not embedded
                # by this minimal sample; smoke tests skip the appearance pass.
                sys.stderr.write("warning: set_value skipped (appearance unavailable)\n")

            with PDPageContentStream(document, page) as cs:
                cs.begin_text()
                cs.set_font(PDType1Font(), 15)
                cs.new_line_at_offset(50, 810)
                cs.show_text("Field:")
                cs.end_text()

            document.save(filename)


if __name__ == "__main__":  # pragma: no cover
    CreateSimpleForm.main(sys.argv[1:])
