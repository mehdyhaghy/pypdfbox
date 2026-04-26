from __future__ import annotations

from pypdfbox.cos import COSDictionary

from .pd_type1_font import PDType1Font


class PDType1CFont(PDType1Font):
    """Type 1 font whose glyph program is a CFF (Compact Font Format) stream.

    Mirrors PDFBox ``PDType1CFont``. The font dictionary itself still
    declares ``/Subtype /Type1`` — Type1C-ness is signalled by a
    ``/FontFile3`` stream on the ``/FontDescriptor`` whose own
    ``/Subtype`` is ``Type1C``. Therefore this wrapper is *not* selected
    by ``PDFontFactory`` from the font dict's ``/Subtype`` alone; it is
    reachable today only via direct construction. Auto-dispatch from
    FontDescriptor inspection is deferred.
    """

    SUB_TYPE = "Type1"

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)


__all__ = ["PDType1CFont"]
