from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName

if TYPE_CHECKING:
    from .pd_font_descriptor import PDFontDescriptor

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_FONT: COSName = COSName.get_pdf_name("Font")
_BASE_FONT: COSName = COSName.get_pdf_name("BaseFont")
_FONT_DESCRIPTOR: COSName = COSName.get_pdf_name("FontDescriptor")


class PDFont:
    """Abstract base font wrapper. Mirrors PDFBox ``PDFont``.

    A ``PDFont`` wraps a ``COSDictionary`` whose ``/Type`` is ``/Font``.
    Concrete subclasses set the appropriate ``/Subtype``.
    """

    SUB_TYPE: str | None = None

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        self._dict = font_dict if font_dict is not None else COSDictionary()
        if self._dict.get_dictionary_object(_TYPE) is None:
            self._dict.set_item(_TYPE, _FONT)
        if font_dict is None and self.SUB_TYPE is not None:
            self._dict.set_name(_SUBTYPE, self.SUB_TYPE)

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- font identity ----------

    def get_name(self) -> str | None:
        """``/BaseFont`` — the PostScript / lookup name of the font."""
        return self._dict.get_name(_BASE_FONT)

    def get_subtype(self) -> str | None:
        """``/Subtype`` — e.g. ``Type1``, ``TrueType``, ``Type0``."""
        return self._dict.get_name(_SUBTYPE)

    # ---------- font descriptor ----------

    def get_font_descriptor(self) -> PDFontDescriptor | None:
        from .pd_font_descriptor import PDFontDescriptor

        fd = self._dict.get_dictionary_object(_FONT_DESCRIPTOR)
        if isinstance(fd, COSDictionary):
            return PDFontDescriptor(fd)
        return None

    def set_font_descriptor(self, font_descriptor: PDFontDescriptor | None) -> None:
        if font_descriptor is None:
            self._dict.remove_item(_FONT_DESCRIPTOR)
            return
        self._dict.set_item(_FONT_DESCRIPTOR, font_descriptor.get_cos_object())


__all__ = ["PDFont"]
