from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_BORDER: COSName = COSName.get_pdf_name("Border")
_W: COSName = COSName.get_pdf_name("W")
_S: COSName = COSName.get_pdf_name("S")
_D: COSName = COSName.get_pdf_name("D")


class PDBorderStyleDictionary:
    """
    Border style dictionary (``/BS`` entry of an annotation dictionary).
    Mirrors ``org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderStyleDictionary``
    (PDF 32000-1:2008 §12.5.4 / Table 166).

    Lite port: ``/D`` is exposed as a raw :class:`COSArray` because the
    typed ``PDLineDashPattern`` wrapper from ``pypdfbox.pdmodel.graphics``
    is not yet ported.
    """

    STYLE_SOLID: ClassVar[str] = "S"
    STYLE_DASHED: ClassVar[str] = "D"
    STYLE_BEVELED: ClassVar[str] = "B"
    STYLE_INSET: ClassVar[str] = "I"
    STYLE_UNDERLINE: ClassVar[str] = "U"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dict = COSDictionary()
            self._dict.set_item(_TYPE, _BORDER)
        else:
            self._dict = dictionary

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /W (border width) ----------

    def set_width(self, w: float) -> None:
        """Set border width in points; 0 = no border.

        PDFBOX-3929 workaround: integer-valued floats are written as
        integers because Adobe Reader DC ignores float widths on widget
        fields.
        """
        if float(w) == int(w):
            self._dict.set_int(_W, int(w))
        else:
            self._dict.set_float(_W, float(w))

    def get_width(self) -> float:
        """Border width in points; 0 if ``/W`` is a name (Adobe quirk)."""
        value = self._dict.get_dictionary_object(_W)
        if isinstance(value, COSName):
            # replicate Adobe behavior although it contradicts the spec
            return 0.0
        return self._dict.get_float(_W, 1.0)

    # ---------- /S (border style) ----------

    def set_style(self, s: str | None) -> None:
        """Set the border style name; ``None`` clears the optional ``/S`` entry."""
        self._dict.set_name(_S, s)

    def get_style(self) -> str:
        value = self._dict.get_name(_S)
        return value if value is not None else self.STYLE_SOLID

    # ---------- /S predicate helpers ----------

    def is_solid(self) -> bool:
        """True when ``/S`` is solid (the default)."""
        return self.get_style() == self.STYLE_SOLID

    def is_dashed(self) -> bool:
        """True when ``/S`` is dashed (uses ``/D`` dash array)."""
        return self.get_style() == self.STYLE_DASHED

    def is_beveled(self) -> bool:
        """True when ``/S`` is beveled."""
        return self.get_style() == self.STYLE_BEVELED

    def is_inset(self) -> bool:
        """True when ``/S`` is inset."""
        return self.get_style() == self.STYLE_INSET

    def is_underline(self) -> bool:
        """True when ``/S`` is underline."""
        return self.get_style() == self.STYLE_UNDERLINE

    # ---------- /D (dash style) ----------

    def set_dash_style(
        self,
        dash_pattern: PDLineDashPattern | COSArray | Sequence[float] | None,
    ) -> None:
        """Set ``/D`` from a typed pattern, raw COSArray, or numeric sequence.

        ``None`` clears the entry. Sequence input (list / tuple of floats) is
        coerced into a fresh ``COSArray``.
        """
        if dash_pattern is None:
            self._dict.remove_item(_D)
            return
        if isinstance(dash_pattern, COSArray):
            self._dict.set_item(_D, dash_pattern)
            return
        if isinstance(dash_pattern, PDLineDashPattern):
            # `/D` here is the inner dash array only (not the [array, phase] form).
            inner = COSArray()
            inner.set_float_array(dash_pattern.get_dash_array())
            self._dict.set_item(_D, inner)
            return
        if isinstance(dash_pattern, Sequence) and not isinstance(
            dash_pattern, (str, bytes, bytearray)
        ):
            inner = COSArray()
            inner.set_float_array([float(v) for v in dash_pattern])
            self._dict.set_item(_D, inner)
            return
        raise TypeError(
            "set_dash_style expects PDLineDashPattern, COSArray, sequence "
            f"of floats, or None; got {type(dash_pattern).__name__}"
        )

    def get_dash_style(self) -> PDLineDashPattern | None:
        """Return the ``/D`` dash pattern, or ``None`` if absent."""
        value = self._dict.get_dictionary_object(_D)
        if isinstance(value, COSArray):
            return PDLineDashPattern(value, 0)
        return None

    def get_dash_style_or_default(self) -> PDLineDashPattern:
        """Return the ``/D`` dash pattern; install a default ``[3]`` array
        when absent and return the typed wrapper.

        Mirrors upstream ``PDBorderStyleDictionary.getDashStyle()`` which
        seeds the default ``[3]`` dash array on the underlying dictionary
        when the entry is missing. ``get_dash_style`` (without the
        ``_or_default`` suffix) keeps the existing pypdfbox semantics of
        returning ``None`` for absent entries.
        """
        value = self._dict.get_dictionary_object(_D)
        if isinstance(value, COSArray):
            return PDLineDashPattern(value, 0)
        default = COSArray()
        default.add(COSInteger.get(3))
        self._dict.set_item(_D, default)
        return PDLineDashPattern(default, 0)


__all__ = ["PDBorderStyleDictionary"]
