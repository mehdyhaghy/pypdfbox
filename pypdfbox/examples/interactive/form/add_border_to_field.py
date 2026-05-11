"""Port of ``org.apache.pdfbox.examples.interactive.form.AddBorderToField``
(upstream ``AddBorderToField.java`` lines 41-74).

Loads a PDF created by :class:`CreateSimpleForm` and adds a red border
to the ``SampleField`` widget.
"""

from __future__ import annotations

import sys

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (
    PDAppearanceCharacteristicsDictionary,
)
from pypdfbox.pdmodel.pd_document import PDDocument


class AddBorderToField:
    """Mirrors ``AddBorderToField`` (final, package-private constructor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/
    interactive/form/AddBorderToField.java`` (lines 41-74).
    """

    RESULT_FILENAME: str = "target/AddBorderToField.pdf"

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 49).

        Expects ``argv[0]`` (input form PDF) and ``argv[1]`` (output PDF).
        Falls back to the upstream defaults when called with no args."""
        from pypdfbox.examples.interactive.form.create_simple_form import (
            CreateSimpleForm,
        )

        argv = list(argv) if argv else []
        src = argv[0] if argv else CreateSimpleForm.DEFAULT_FILENAME
        dst = argv[1] if len(argv) > 1 else AddBorderToField.RESULT_FILENAME
        AddBorderToField.add_border(src, dst, "SampleField")

    @staticmethod
    def add_border(src: str, dst: str, field_name: str) -> None:
        """Open ``src``, paint a red border on ``field_name``, save to
        ``dst``. Promoted from the upstream inline ``main`` body."""
        with PDDocument.load(src) as document:
            acro_form = document.get_document_catalog().get_acro_form()
            if acro_form is None:
                raise OSError("document has no AcroForm")
            field = acro_form.get_field(field_name)
            if field is None:
                raise OSError(f"field {field_name!r} not found")
            widget = field.get_widgets()[0]

            field_appearance = PDAppearanceCharacteristicsDictionary(COSDictionary())
            red = PDColor([1, 0, 0], PDDeviceRGB.INSTANCE)
            field_appearance.set_border_colour(red)
            widget.set_appearance_characteristics(field_appearance)

            document.save(dst)


if __name__ == "__main__":  # pragma: no cover
    AddBorderToField.main(sys.argv[1:])
