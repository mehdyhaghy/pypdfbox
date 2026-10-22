"""Visible-signature template builder helpers.

Ports of the upstream ``org.apache.pdfbox.pdmodel.interactive.digitalsignature.visible``
package. These classes coordinate the construction of the form-XObject
visual signature embedded into a signed PDF; the heavy rendering work
(drawing fonts, baking images) is delegated to the surrounding
:mod:`pypdfbox.pdmodel.graphics` and :mod:`pypdfbox.pdmodel.font`
modules.
"""

from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .pd_visible_sig_builder import PDVisibleSigBuilder
    from .pd_visible_sig_properties import PDVisibleSigProperties
    from .pd_visible_sign_designer import PDVisibleSignDesigner
    from .pdf_template_builder import PDFTemplateBuilder
    from .pdf_template_creator import PDFTemplateCreator
    from .pdf_template_structure import PDFTemplateStructure

__getattr__, __dir__ = _attach(
    __name__,
    {
        "PDVisibleSigBuilder": ".pd_visible_sig_builder",
        "PDVisibleSigProperties": ".pd_visible_sig_properties",
        "PDVisibleSignDesigner": ".pd_visible_sign_designer",
        "PDFTemplateBuilder": ".pdf_template_builder",
        "PDFTemplateCreator": ".pdf_template_creator",
        "PDFTemplateStructure": ".pdf_template_structure",
    },
)

__all__ = [
    "PDFTemplateBuilder",
    "PDFTemplateCreator",
    "PDFTemplateStructure",
    "PDVisibleSigBuilder",
    "PDVisibleSigProperties",
    "PDVisibleSignDesigner",
]
