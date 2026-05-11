"""Port of ``CreateEmptySignatureForm`` (upstream 1-90)."""

from __future__ import annotations

from pathlib import Path


class CreateEmptySignatureForm:
    """Build a one-page PDF with an empty signature field."""

    def __init__(self) -> None:  # pragma: no cover - mirrors private ctor
        raise RuntimeError("CreateEmptySignatureForm is a static helper class")

    @staticmethod
    def main(args: list[str]) -> None:
        """CLI entry point (upstream line 45)."""
        if not args:
            raise SystemExit("usage: create_empty_signature_form <output.pdf>")
        CreateEmptySignatureForm.create(args[0])

    @staticmethod
    def create(output_path: Path | str) -> None:
        """Write a PDF with an empty signature field to ``output_path``."""
        from pypdfbox.cos.cos_name import COSName
        from pypdfbox.pdmodel.common.pd_rectangle import PDRectangle
        from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
        from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
        from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
        from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField
        from pypdfbox.pdmodel.pd_document import PDDocument
        from pypdfbox.pdmodel.pd_page import PDPage
        from pypdfbox.pdmodel.pd_resources import PDResources

        with PDDocument() as document:
            page = PDPage(PDRectangle.A4)
            document.add_page(page)

            font = PDType1Font(Standard14Fonts.FontName.HELVETICA)
            resources = PDResources()
            resources.put(COSName.HELV, font)

            acro_form = PDAcroForm(document)
            document.get_document_catalog().set_acro_form(acro_form)
            acro_form.set_default_resources(resources)
            acro_form.set_default_appearance("/Helv 0 Tf 0 g")

            signature_field = PDSignatureField(acro_form)
            widget = signature_field.get_widgets()[0]
            rect = PDRectangle(50, 650, 200, 50)
            widget.set_rectangle(rect)
            widget.set_page(page)
            widget.set_printed(True)

            page.get_annotations().append(widget)
            acro_form.get_fields().append(signature_field)

            document.save(str(output_path))
