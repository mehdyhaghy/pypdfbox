"""Port of ``DetermineTextFitsField`` (upstream
``DetermineTextFitsField.java`` lines 39-101).

Loads a form, reads the field's default appearance, then asks the
backing font how wide a given test string would render.
"""

from __future__ import annotations

import sys

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.pd_document import PDDocument


class DetermineTextFitsField:
    """Mirrors ``DetermineTextFitsField`` (final, package-private ctor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/
    interactive/form/DetermineTextFitsField.java`` (lines 39-101).
    """

    DEFAULT_FILENAME: str = "target/SimpleForm.pdf"

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 45)."""
        argv = list(argv) if argv else []
        src = argv[0] if argv else DetermineTextFitsField.DEFAULT_FILENAME
        field_name = argv[1] if len(argv) > 1 else "SampleField"
        DetermineTextFitsField.check_field(src, field_name)

    @staticmethod
    def check_field(src: str, field_name: str) -> tuple[float, float, float]:
        """Return ``(field_width, short_width, long_width)`` for
        ``field_name`` — promoted from the upstream inline ``main`` body."""
        with PDDocument.load(src) as document:
            acro_form = document.get_document_catalog().get_acro_form()
            if acro_form is None:
                raise OSError("document has no AcroForm")
            field = acro_form.get_field(field_name)
            if field is None:
                raise OSError(f"field {field_name!r} not found")
            widget = field.get_widgets()[0]

            width_of_field = widget.get_rectangle().get_width()

            # Field's default appearance string e.g. "/Helv 12 Tf 0 g".
            default_appearance = field.get_default_appearance()
            parts = default_appearance.split(" ")
            font_name = COSName.get_pdf_name(parts[0][1:])
            font_size = float(parts[1])

            font = None
            try:
                normal_appearance = widget.get_normal_appearance_stream()
                resources = (
                    normal_appearance.get_resources()
                    if normal_appearance is not None
                    else None
                )
                if resources is not None:
                    font = resources.get_font(font_name)
            except Exception:  # noqa: BLE001
                font = None
            if font is None:
                font = acro_form.get_default_resources().get_font(font_name)

            will_fit = "short string"
            will_not_fit = (
                "this is a very long string which will not fit the width of the widget"
            )

            try:
                will_fit_width = font.get_string_width(will_fit) * font_size / 1000.0
                will_not_fit_width = (
                    font.get_string_width(will_not_fit) * font_size / 1000.0
                )
            except Exception:  # noqa: BLE001
                # Some fonts (especially without embedded program) cannot
                # measure arbitrary strings — return NaNs in that case so
                # callers can detect the missing width.
                will_fit_width = float("nan")
                will_not_fit_width = float("nan")

            return width_of_field, will_fit_width, will_not_fit_width


if __name__ == "__main__":  # pragma: no cover
    DetermineTextFitsField.main(sys.argv[1:])
