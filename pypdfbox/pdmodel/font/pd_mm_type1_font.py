from __future__ import annotations

from pypdfbox.cos import COSDictionary

from .pd_type1_font import PDType1Font


class PDMMType1Font(PDType1Font):
    """Multiple-Master Type 1 font. Mirrors PDFBox ``PDMMType1Font``.

    Marker subclass — the upstream class adds no methods beyond
    ``PDType1Font`` and exists only to distinguish ``/Subtype /MMType1``
    from regular ``/Subtype /Type1`` for downstream selection logic.
    """

    SUB_TYPE = "MMType1"

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)


__all__ = ["PDMMType1Font"]
