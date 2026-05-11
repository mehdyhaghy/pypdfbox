from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName

from .fdf_page_info import FDFPageInfo
from .fdf_template import FDFTemplate

_TEMPLATES: COSName = COSName.get_pdf_name("Templates")
_INFO: COSName = COSName.get_pdf_name("Info")


class FDFPage:
    """A page entry inside an FDF document.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFPage`` (Java
    lines 33-121).
    """

    def __init__(self, page: COSDictionary | None = None) -> None:
        self._page: COSDictionary = page if page is not None else COSDictionary()

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        """Return the wrapped ``COSDictionary``. Mirrors upstream
        ``getCOSObject()`` (Java line 62)."""
        return self._page

    # ---------- /Templates ----------

    def get_templates(self) -> list[FDFTemplate] | None:
        """Return the templates serving as named pages.

        Mirrors upstream ``getTemplates()`` (Java line 71).
        """
        array = self._page.get_dictionary_object(_TEMPLATES)
        if not isinstance(array, COSArray):
            return None
        templates: list[FDFTemplate] = []
        for i in range(array.size()):
            entry = array.get_object(i)
            if isinstance(entry, COSDictionary):
                templates.append(FDFTemplate(entry))
        return templates

    def set_templates(self, templates: list[FDFTemplate] | None) -> None:
        """Set the templates (``/Templates``).

        Mirrors upstream ``setTemplates(List<FDFTemplate>)`` (Java line 91).
        """
        if templates is None:
            self._page.remove_item(_TEMPLATES)
            return
        array = COSArray()
        for template in templates:
            array.add(template.get_cos_object())
        self._page.set_item(_TEMPLATES, array)

    # ---------- /Info ----------

    def get_page_info(self) -> FDFPageInfo | None:
        """Return the page-info dictionary (``/Info``) or ``None``.

        Mirrors upstream ``getPageInfo()`` (Java line 101).
        """
        dict_ = self._page.get_dictionary_object(_INFO)
        if isinstance(dict_, COSDictionary):
            return FDFPageInfo(dict_)
        return None

    def set_page_info(self, info: FDFPageInfo | None) -> None:
        """Set the page-info dictionary (``/Info``).

        Mirrors upstream ``setPageInfo(FDFPageInfo)`` (Java line 117).
        """
        if info is None:
            self._page.remove_item(_INFO)
            return
        self._page.set_item(_INFO, info.get_cos_object())


__all__ = ["FDFPage"]
