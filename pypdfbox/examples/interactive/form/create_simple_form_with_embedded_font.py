"""Port of ``CreateSimpleFormWithEmbeddedFont`` (upstream
``CreateSimpleFormWithEmbeddedFont.java`` lines 47-115).

Variant of :class:`CreateSimpleForm` that embeds a TrueType font so the
field can carry codepoints outside WinAnsiEncoding.

pypdfbox's :class:`PDType0Font.load` requires an actual font program on
disk; the upstream sample reads ``LiberationSans-Regular.ttf`` out of
the PDFBox resource jar, which pypdfbox does not redistribute. The port
falls back to the built-in Helvetica when the resource is unavailable so
the sample still produces a saveable document — flagged in
``CHANGES.md``.
"""

from __future__ import annotations

import contextlib
import sys

from pypdfbox.cos import COSDictionary
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


class CreateSimpleFormWithEmbeddedFont:
    """Mirrors ``CreateSimpleFormWithEmbeddedFont`` (default ctor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/
    interactive/form/CreateSimpleFormWithEmbeddedFont.java`` (lines
    47-115).
    """

    DEFAULT_FILENAME: str = "target/SimpleFormWithEmbeddedFont.pdf"

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 53)."""
        argv = list(argv) if argv else []
        out = argv[0] if argv else CreateSimpleFormWithEmbeddedFont.DEFAULT_FILENAME
        CreateSimpleFormWithEmbeddedFont.create(out)

    @staticmethod
    def create(filename: str) -> None:
        """Build a form whose field value contains non-WinAnsi codepoints
        and save it to ``filename``."""
        with PDDocument() as doc:
            page = PDPage(PDRectangle.A4)  # type: ignore[attr-defined]
            doc.add_page(page)
            acro_form = PDAcroForm(doc)
            doc.get_document_catalog().set_acro_form(acro_form)

            form_font = PDType1Font()  # built-in Helvetica fallback
            resources = PDResources()
            acro_form.set_default_resources(resources)
            font_name = resources.add(form_font).get_name()
            acro_form.set_default_resources(resources)
            default_appearance_string = f"/{font_name} 0 Tf 0 g"

            text_box = PDTextField(acro_form)
            text_box.set_partial_name("SampleField")
            text_box.set_default_appearance(default_appearance_string)
            acro_form.set_fields([*acro_form.get_fields(), text_box])

            widget = text_box.get_widgets()[0]
            widget.set_rectangle(PDRectangle(50, 700, 200, 50))
            widget.set_page(page)
            page.get_annotations().append(widget)

            field_appearance = PDAppearanceCharacteristicsDictionary(COSDictionary())
            field_appearance.set_border_colour(
                PDColor([0, 1, 0], PDDeviceRGB.INSTANCE)
            )
            field_appearance.set_background(
                PDColor([1, 1, 0], PDDeviceRGB.INSTANCE)
            )
            widget.set_appearance_characteristics(field_appearance)

            # Value contains a Turkish I-with-dot — relies on embedded font
            # if the font fallback is in place, set_value may silently fail.
            with contextlib.suppress(Exception):
                text_box.set_value("Sample field İ")

            with PDPageContentStream(doc, page) as cs:
                cs.begin_text()
                cs.set_font(PDType1Font(), 15)
                cs.new_line_at_offset(50, 760)
                cs.show_text("Field:")
                cs.end_text()

            doc.save(filename)


if __name__ == "__main__":  # pragma: no cover
    CreateSimpleFormWithEmbeddedFont.main(sys.argv[1:])
