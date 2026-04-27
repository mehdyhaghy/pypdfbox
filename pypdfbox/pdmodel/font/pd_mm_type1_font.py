from __future__ import annotations

from pypdfbox.cos import COSDictionary

from .pd_type1_font import PDType1Font


class PDMMType1Font(PDType1Font):
    """Multiple-Master Type 1 font. Mirrors PDFBox ``PDMMType1Font``.

    A *Multiple Master* (MM) Type 1 font (PDF 32000-1:2008 §9.6.2.3) is a
    Type 1 font carrying a *design vector* — a tuple of axis values
    (weight, width, optical size, ...) that select an instance of the
    font's master design space. The instance name is encoded in the
    ``/BaseFont`` entry by replacing the spaces in the PostScript instance
    name with underscores, e.g. ``MyriadMM_366_BD_700_TT_400_``.

    Per upstream, this class is a **marker subclass** — it adds no
    methods beyond :class:`PDType1Font` and exists only to distinguish
    ``/Subtype /MMType1`` from regular ``/Subtype /Type1`` so that
    factory dispatch (:class:`PDFontFactory`) and downstream selection
    logic can branch on the runtime type. All glyph-width, encoding,
    embedded-program, and metric handling is inherited unchanged from
    :class:`PDType1Font`.
    """

    SUB_TYPE = "MMType1"

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        # Delegates fully to the Type 1 parent — no MM-specific dict
        # initialisation is required (the design vector lives encoded in
        # /BaseFont, which the parent already accepts verbatim).
        super().__init__(font_dict)


__all__ = ["PDMMType1Font"]
