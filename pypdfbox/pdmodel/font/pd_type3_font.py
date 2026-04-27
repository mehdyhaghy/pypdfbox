from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)

from .pd_simple_font import PDSimpleFont

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle  # noqa: F401
    from pypdfbox.pdmodel.pd_resources import PDResources

_CHAR_PROCS: COSName = COSName.get_pdf_name("CharProcs")
_FIRST_CHAR: COSName = COSName.get_pdf_name("FirstChar")
_FONT_BBOX: COSName = COSName.get_pdf_name("FontBBox")
_FONT_MATRIX: COSName = COSName.get_pdf_name("FontMatrix")
_LAST_CHAR: COSName = COSName.get_pdf_name("LastChar")
_RESOURCES: COSName = COSName.get_pdf_name("Resources")
_WIDTHS: COSName = COSName.get_pdf_name("Widths")

# PDF 32000-1 §9.2.4: default Type 3 /FontMatrix maps the glyph coordinate
# system (typically 1000-unit em) into text space (1-unit em).
_DEFAULT_FONT_MATRIX: tuple[float, ...] = (0.001, 0.0, 0.0, 0.001, 0.0, 0.0)


class PDType3Font(PDSimpleFont):
    """PDF Type 3 font — glyph shapes are defined by inline content streams.

    Mirrors PDFBox ``PDType3Font``. Wires the dictionary accessors from PDF
    32000-1 §9.6.5 Table 113. Typed ``PDType3CharProc`` and the
    ``Matrix`` / glyph-paint pipeline are deferred until the contentstream
    renderer cluster — ``get_font_matrix`` returns the raw 6-float list
    rather than a typed ``Matrix`` object until then.
    """

    SUB_TYPE = "Type3"

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)

    # ---------- /CharProcs (raw — typed PDType3CharProc deferred) ----------

    def get_char_procs(self) -> COSDictionary | None:
        """Return the ``/CharProcs`` glyph-name -> content-stream mapping."""
        entry = self._dict.get_dictionary_object(_CHAR_PROCS)
        return entry if isinstance(entry, COSDictionary) else None

    def set_char_procs(self, value: COSDictionary | None) -> None:
        """Set or clear the ``/CharProcs`` dictionary."""
        if value is None:
            self._dict.remove_item(_CHAR_PROCS)
            return
        self._dict.set_item(_CHAR_PROCS, value)

    def get_char_proc(self, name: str) -> COSStream | None:
        """Look up a single glyph's content stream by glyph name.

        Returns ``None`` when ``/CharProcs`` is missing or the glyph name is
        not present (or its entry is not a stream). Unlike upstream's
        ``getCharProc(int code)`` this takes the glyph *name* directly so it
        works without resolving the font's ``/Encoding`` first — the encoded
        lookup will land alongside the typed ``PDType3CharProc`` port.
        """
        char_procs = self.get_char_procs()
        if char_procs is None:
            return None
        entry = char_procs.get_dictionary_object(COSName.get_pdf_name(name))
        return entry if isinstance(entry, COSStream) else None

    # ---------- /Resources (typed via PDResources) ----------

    def get_resources(self) -> PDResources | None:
        """Return the ``/Resources`` dictionary wrapped as ``PDResources``."""
        from pypdfbox.pdmodel.pd_resources import PDResources

        entry = self._dict.get_dictionary_object(_RESOURCES)
        if isinstance(entry, COSDictionary):
            return PDResources(entry)
        return None

    def set_resources(self, value: PDResources | None) -> None:
        """Set or clear the ``/Resources`` dictionary."""
        if value is None:
            self._dict.remove_item(_RESOURCES)
            return
        self._dict.set_item(_RESOURCES, value.get_cos_object())

    # ---------- /FontMatrix ----------

    def get_font_matrix(self) -> list[float]:
        """Return the 6-element ``/FontMatrix`` transform.

        Defaults to ``[0.001, 0, 0, 0.001, 0, 0]`` per PDF 32000-1 §9.2.4
        when the entry is missing or malformed (not a 6-entry numeric
        array).
        """
        entry = self._dict.get_dictionary_object(_FONT_MATRIX)
        if isinstance(entry, COSArray) and entry.size() == 6:
            values: list[float] = []
            for i in range(6):
                item = entry.get_object(i)
                if not isinstance(item, (COSInteger, COSFloat)):
                    return list(_DEFAULT_FONT_MATRIX)
                values.append(float(item.value))
            return values
        return list(_DEFAULT_FONT_MATRIX)

    def set_font_matrix(self, matrix: list[float]) -> None:
        """Replace the ``/FontMatrix`` with a 6-element transform."""
        if len(matrix) != 6:
            raise ValueError(
                f"/FontMatrix requires exactly 6 elements, got {len(matrix)}"
            )
        arr = COSArray([COSFloat(float(v)) for v in matrix])
        self._dict.set_item(_FONT_MATRIX, arr)

    # ---------- /FontBBox ----------

    def get_font_bbox(self) -> PDRectangle | None:
        """Return the ``/FontBBox`` rectangle, or ``None`` when absent."""
        from pypdfbox.pdmodel.pd_rectangle import PDRectangle

        entry = self._dict.get_dictionary_object(_FONT_BBOX)
        if isinstance(entry, COSArray) and entry.size() >= 4:
            return PDRectangle.from_cos_array(entry)
        return None

    def set_font_bbox(self, rect: PDRectangle | None) -> None:
        """Set or clear the ``/FontBBox`` rectangle."""
        if rect is None:
            self._dict.remove_item(_FONT_BBOX)
            return
        self._dict.set_item(_FONT_BBOX, rect.to_cos_array())

    # ---------- /FontBBox legacy (raw COSArray accessors) ----------

    def get_font_b_box(self) -> COSArray | None:
        """Raw ``/FontBBox`` array accessor — kept for the lite-surface
        round-trip tests; new code should use :meth:`get_font_bbox`."""
        entry = self._dict.get_dictionary_object(_FONT_BBOX)
        return entry if isinstance(entry, COSArray) else None

    def set_font_b_box(self, bbox: COSArray | None) -> None:
        """Raw ``/FontBBox`` array setter — kept for the lite-surface
        round-trip tests; new code should use :meth:`set_font_bbox`."""
        if bbox is None:
            self._dict.remove_item(_FONT_BBOX)
            return
        self._dict.set_item(_FONT_BBOX, bbox)

    # ---------- /FirstChar /LastChar /Widths ----------
    #
    # Inherited ``get_first_char`` / ``get_last_char`` / ``get_widths`` come
    # from :class:`PDSimpleFont`. The setters below are wired here for
    # convenience: PDFBox exposes these on ``PDSimpleFont`` itself, but
    # we only need them on Type3 today, so keeping them local avoids
    # cross-class churn.

    def set_first_char(self, value: int) -> None:
        self._dict.set_int(_FIRST_CHAR, int(value))

    def set_last_char(self, value: int) -> None:
        self._dict.set_int(_LAST_CHAR, int(value))

    def set_widths(self, values: list[float]) -> None:
        """Replace the ``/Widths`` array with the given glyph widths."""
        arr = COSArray([COSFloat(float(v)) for v in values])
        self._dict.set_item(_WIDTHS, arr)


__all__ = ["PDType3Font"]
