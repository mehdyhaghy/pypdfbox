from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern

_C: COSName = COSName.get_pdf_name("C")
_W: COSName = COSName.get_pdf_name("W")
_S: COSName = COSName.get_pdf_name("S")
_D: COSName = COSName.get_pdf_name("D")


class PDBoxStyle:
    """Box Style — visual characteristics for displaying box areas
    (PDF 32000-1:2008 §14.10.4 / Table 366). Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.documentinterchange.prepress.PDBoxStyle``.

    The dictionary keys covered are:

    * ``/C`` — guideline colour (3-component RGB array, default ``[0 0 0]``)
    * ``/W`` — guideline width in default user-space units (default ``1``)
    * ``/S`` — guideline style name (``"S"`` solid, ``"D"`` dashed; default
      :attr:`GUIDELINE_STYLE_SOLID`)
    * ``/D`` — line dash pattern (1- or 2-element number array; default
      ``[3]``)
    """

    # Style names per upstream PDFBox.
    GUIDELINE_STYLE_SOLID: str = "S"
    GUIDELINE_STYLE_DASHED: str = "D"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dictionary: COSDictionary = (
            dictionary if dictionary is not None else COSDictionary()
        )

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    def get_cos_dictionary(self) -> COSDictionary:
        """Pypdfbox-style alias for :meth:`get_cos_object`."""
        return self._dictionary

    # ---------- /C — guideline colour ----------

    def get_guideline_color(self) -> PDColor:
        """Return the guideline colour. Never ``None``: when ``/C`` is
        absent, the default ``[0 0 0]`` is materialised into the
        underlying dictionary, matching upstream behaviour.
        """
        color_values = self._dictionary.get_cos_array(_C)
        if color_values is None:
            color_values = COSArray()
            color_values.add(COSInteger.ZERO)
            color_values.add(COSInteger.ZERO)
            color_values.add(COSInteger.ZERO)
            self._dictionary.set_item(_C, color_values)
        return PDColor(color_values, PDDeviceRGB.INSTANCE)

    def set_guideline_color(self, color: PDColor | None) -> None:
        """Set the guideline colour. ``None`` removes the entry.

        Upstream's ``setGuideLineColor`` (sic, with internal capital ``L``)
        is also exposed for parity.
        """
        if color is None:
            self._dictionary.remove_item(_C)
        else:
            self._dictionary.set_item(_C, color.to_cos_array())

    def set_guide_line_color(self, color: PDColor | None) -> None:
        """Upstream-parity alias for :meth:`set_guideline_color`."""
        self.set_guideline_color(color)

    # ---------- /W — guideline width ----------

    def get_guideline_width(self) -> float:
        """Return ``/W`` in default user-space units. Default is ``1.0``."""
        return self._dictionary.get_float(_W, 1.0)

    def set_guideline_width(self, width: float) -> None:
        self._dictionary.set_float(_W, float(width))

    # ---------- /S — guideline style ----------

    def get_guideline_style(self) -> str:
        """Return the guideline style name. Default is
        :attr:`GUIDELINE_STYLE_SOLID`.
        """
        value = self._dictionary.get_name(_S, self.GUIDELINE_STYLE_SOLID)
        # ``get_name`` returns ``str | None``; the default is non-None so
        # this branch is for type-narrowing only.
        return value if value is not None else self.GUIDELINE_STYLE_SOLID

    def set_guideline_style(self, style: str | None) -> None:
        if style is None:
            self._dictionary.remove_item(_S)
        else:
            self._dictionary.set_name(_S, style)

    # ---------- /D — line dash pattern ----------

    def get_line_dash_pattern(self) -> PDLineDashPattern:
        """Return the dash pattern. Never ``None``: when ``/D`` is
        absent, the default ``[3]`` is materialised into the underlying
        dictionary, matching upstream behaviour. The upstream
        implementation does not record a dash phase in the dictionary
        (PDF 32000 Table 366 only specifies the dash array), so the
        returned pattern always has phase 0.
        """
        d = self._dictionary.get_cos_array(_D)
        if d is None:
            d = COSArray()
            d.add(COSInteger.THREE)
            self._dictionary.set_item(_D, d)
        line_array = COSArray()
        line_array.add(d)
        line_array.add(COSInteger.ZERO)
        return PDLineDashPattern.from_cos_array(line_array)

    def set_line_dash_pattern(self, dash_array: COSArray | None) -> None:
        """Set ``/D`` directly to ``dash_array`` (a numeric ``COSArray``),
        or remove the entry when ``None``. Mirrors upstream
        ``setLineDashPattern(COSArray)``.
        """
        if dash_array is None:
            self._dictionary.remove_item(_D)
        else:
            self._dictionary.set_item(_D, dash_array)


__all__ = ["PDBoxStyle"]
