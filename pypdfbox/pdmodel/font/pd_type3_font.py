from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName

from .pd_simple_font import PDSimpleFont

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_resources import PDResources

_CHAR_PROCS: COSName = COSName.get_pdf_name("CharProcs")
_FONT_BBOX: COSName = COSName.get_pdf_name("FontBBox")
_FONT_MATRIX: COSName = COSName.get_pdf_name("FontMatrix")
_RESOURCES: COSName = COSName.get_pdf_name("Resources")


class PDType3Font(PDSimpleFont):
    """PDF Type 3 font — glyph shapes are defined by inline content streams.

    Mirrors PDFBox ``PDType3Font``. Lite surface — only the dictionary
    accessors needed by the writer / round-trip tests are wired. Typed
    ``PDType3CharProc`` and the ``PDRectangle`` / ``Matrix`` / glyph-paint
    pipeline are deferred until the contentstream renderer cluster.
    """

    SUB_TYPE = "Type3"

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)

    # ---------- /CharProcs (raw — typed PDCharProc deferred) ----------

    def get_char_procs(self) -> COSDictionary | None:
        entry = self._dict.get_dictionary_object(_CHAR_PROCS)
        return entry if isinstance(entry, COSDictionary) else None

    def set_char_procs(self, char_procs: COSDictionary | None) -> None:
        if char_procs is None:
            self._dict.remove_item(_CHAR_PROCS)
            return
        self._dict.set_item(_CHAR_PROCS, char_procs)

    # ---------- /FontBBox ----------

    def get_font_b_box(self) -> COSArray | None:
        entry = self._dict.get_dictionary_object(_FONT_BBOX)
        return entry if isinstance(entry, COSArray) else None

    def set_font_b_box(self, bbox: COSArray | None) -> None:
        if bbox is None:
            self._dict.remove_item(_FONT_BBOX)
            return
        self._dict.set_item(_FONT_BBOX, bbox)

    # ---------- /FontMatrix ----------

    def get_font_matrix(self) -> COSArray | None:
        entry = self._dict.get_dictionary_object(_FONT_MATRIX)
        return entry if isinstance(entry, COSArray) else None

    def set_font_matrix(self, matrix: COSArray | None) -> None:
        if matrix is None:
            self._dict.remove_item(_FONT_MATRIX)
            return
        self._dict.set_item(_FONT_MATRIX, matrix)

    # ---------- /Resources (typed via PDResources) ----------

    def get_resources(self) -> PDResources | None:
        from pypdfbox.pdmodel.pd_resources import PDResources

        entry = self._dict.get_dictionary_object(_RESOURCES)
        if isinstance(entry, COSDictionary):
            return PDResources(entry)
        return None

    def set_resources(self, resources: PDResources | None) -> None:
        if resources is None:
            self._dict.remove_item(_RESOURCES)
            return
        self._dict.set_item(_RESOURCES, resources.get_cos_object())


__all__ = ["PDType3Font"]
