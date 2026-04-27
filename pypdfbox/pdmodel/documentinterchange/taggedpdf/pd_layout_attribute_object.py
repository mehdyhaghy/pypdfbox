from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger

from .pd_four_colours import PDFourColours
from .pd_standard_attribute_object import PDStandardAttributeObject


class PDLayoutAttributeObject(PDStandardAttributeObject):
    """
    A layout attribute object (``/O /Layout``). Mirrors PDFBox
    ``PDLayoutAttributeObject``.

    Covers the typed accessors per PDF 32000-1:2008 §14.8.5.4: placement,
    writing mode, foreground / background colors, four-side border colors,
    border style / thickness, padding, vertical spacing, indents, text
    align, baseline shift, bounding box, content size, column geometry, and
    block / inline alignment. The decoration / ruby accessors and the
    upstream change-notification plumbing are still deferred.
    """

    OWNER: str = "Layout"

    # Placement values
    PLACEMENT_BLOCK: str = "Block"
    PLACEMENT_INLINE: str = "Inline"
    PLACEMENT_BEFORE: str = "Before"
    PLACEMENT_START: str = "Start"
    PLACEMENT_END: str = "End"

    # WritingMode values
    WRITING_MODE_LRTB: str = "LrTb"
    WRITING_MODE_RLTB: str = "RlTb"
    WRITING_MODE_TBRL: str = "TbRl"

    # BorderStyle values (PDF 32000-1 §14.8.5.4 Table 343)
    BORDER_STYLE_NONE: str = "None"
    BORDER_STYLE_HIDDEN: str = "Hidden"
    BORDER_STYLE_DOTTED: str = "Dotted"
    BORDER_STYLE_DASHED: str = "Dashed"
    BORDER_STYLE_SOLID: str = "Solid"
    BORDER_STYLE_DOUBLE: str = "Double"
    BORDER_STYLE_GROOVE: str = "Groove"
    BORDER_STYLE_RIDGE: str = "Ridge"
    BORDER_STYLE_INSET: str = "Inset"
    BORDER_STYLE_OUTSET: str = "Outset"

    # Width / Height "auto" sentinel (a /Name in the COS surface)
    WIDTH_AUTO: str = "Auto"
    HEIGHT_AUTO: str = "Auto"

    # BlockAlign values
    BLOCK_ALIGN_BEFORE: str = "Before"
    BLOCK_ALIGN_MIDDLE: str = "Middle"
    BLOCK_ALIGN_AFTER: str = "After"
    BLOCK_ALIGN_JUSTIFY: str = "Justify"

    # InlineAlign values
    INLINE_ALIGN_START: str = "Start"
    INLINE_ALIGN_CENTER: str = "Center"
    INLINE_ALIGN_END: str = "End"

    # TextAlign values
    TEXT_ALIGN_START: str = "Start"
    TEXT_ALIGN_CENTER: str = "Center"
    TEXT_ALIGN_END: str = "End"
    TEXT_ALIGN_JUSTIFY: str = "Justify"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)
        if dictionary is None:
            self.set_owner(self.OWNER)

    # ---------- /Placement ----------

    def get_placement(self) -> str | None:
        return self._get_name("Placement", self.PLACEMENT_INLINE)

    def set_placement(self, placement: str) -> None:
        self._set_name("Placement", placement)

    # ---------- /WritingMode ----------

    def get_writing_mode(self) -> str | None:
        return self._get_name("WritingMode", self.WRITING_MODE_LRTB)

    def set_writing_mode(self, writing_mode: str) -> None:
        self._set_name("WritingMode", writing_mode)

    # ---------- /BackgroundColor ----------

    def get_background_color(self) -> tuple[float, ...] | None:
        return self._get_color_value("BackgroundColor")

    def set_background_color(self, rgb: tuple[float, ...] | None) -> None:
        self._set_color_value("BackgroundColor", rgb)

    # ---------- /Color ----------

    def get_color(self) -> tuple[float, ...] | None:
        return self._get_color_value("Color")

    def set_color(self, rgb: tuple[float, ...] | None) -> None:
        self._set_color_value("Color", rgb)

    # ---------- /BorderColor ----------

    def get_border_color(self) -> PDFourColours | None:
        return self._get_four_colours("BorderColor")

    def set_border_color(self, four: PDFourColours | None) -> None:
        self._set_four_colours("BorderColor", four)

    # ---------- /BorderColor — upstream-parity polymorphic getter ----------

    def get_border_colors(self) -> tuple[float, ...] | PDFourColours | None:
        """
        Return either a single RGB tuple (3 components) or a
        :class:`PDFourColours` (4 inner arrays), matching upstream
        ``getBorderColors``. ``None`` if absent.
        """
        return self.get_color_or_four_colors("BorderColor")

    def set_border_colors(self, four: PDFourColours | None) -> None:
        """Upstream-parity alias for :meth:`set_border_color`."""
        self._set_four_colours("BorderColor", four)

    # ---------- /BorderStyle ----------

    def get_border_style(self) -> str | list[str] | None:
        """
        Return a single style name or a four-element list of style names.
        Defaults to :attr:`BORDER_STYLE_NONE` when absent (PDF 32000-1
        §14.8.5.4 Table 343).
        """
        return self.get_name_or_array_of_name("BorderStyle", self.BORDER_STYLE_NONE)

    def set_border_style(self, value: str | list[str] | None) -> None:
        """
        Set ``/BorderStyle`` either to a single name (applies to all four
        sides) or to a four-element name array (per-side).
        """
        if value is None:
            self._dictionary.remove_item("BorderStyle")
        elif isinstance(value, str):
            self._set_name("BorderStyle", value)
        else:
            self._set_array_of_name("BorderStyle", list(value))

    # ---------- /BorderThickness ----------

    def get_border_thickness(self) -> float | list[float] | None:
        """
        Return either a single number or a four-element list of numbers
        (per-side thickness). ``None`` if absent.
        """
        return self.get_number_or_array_of_number("BorderThickness", self.UNSPECIFIED)

    def set_border_thickness(self, value: float | int | list[float] | None) -> None:
        """
        Set ``/BorderThickness`` either to a single number (all four sides)
        or to a four-element number array (per-side).
        """
        if value is None:
            self._dictionary.remove_item("BorderThickness")
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            self._set_number("BorderThickness", value)
        else:
            self._set_array_of_number("BorderThickness", [float(v) for v in value])

    # ---------- /Padding ----------

    def get_padding(self) -> float | list[float] | None:
        """
        Return either a single number or a four-element list of numbers.
        Defaults to ``0.0`` when absent.
        """
        return self.get_number_or_array_of_number("Padding", 0.0)

    def set_padding(self, value: float | int | list[float] | None) -> None:
        """
        Set ``/Padding`` either to a single number (all four sides) or to a
        four-element number array (per-side).
        """
        if value is None:
            self._dictionary.remove_item("Padding")
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            self._set_number("Padding", value)
        else:
            self._set_array_of_number("Padding", [float(v) for v in value])

    # ---------- /SpaceBefore ----------

    def get_space_before(self) -> float:
        return self._get_number("SpaceBefore", 0.0)

    def set_space_before(self, value: float | int) -> None:
        self._set_number("SpaceBefore", value)

    # ---------- /SpaceAfter ----------

    def get_space_after(self) -> float:
        return self._get_number("SpaceAfter", 0.0)

    def set_space_after(self, value: float | int) -> None:
        self._set_number("SpaceAfter", value)

    # ---------- /StartIndent ----------

    def get_start_indent(self) -> float:
        return self._get_number("StartIndent", 0.0)

    def set_start_indent(self, value: float | int) -> None:
        self._set_number("StartIndent", value)

    # ---------- /EndIndent ----------

    def get_end_indent(self) -> float:
        return self._get_number("EndIndent", 0.0)

    def set_end_indent(self, value: float | int) -> None:
        self._set_number("EndIndent", value)

    # ---------- /TextIndent ----------

    def get_text_indent(self) -> float:
        return self._get_number("TextIndent", 0.0)

    def set_text_indent(self, value: float | int) -> None:
        self._set_number("TextIndent", value)

    # ---------- /TextAlign ----------

    def get_text_align(self) -> str | None:
        return self._get_name("TextAlign", self.TEXT_ALIGN_START)

    def set_text_align(self, text_align: str) -> None:
        self._set_name("TextAlign", text_align)

    # ---------- /BaselineShift ----------

    def get_baseline_shift(self) -> float:
        return self._get_number("BaselineShift", 0.0)

    def set_baseline_shift(self, value: float | int) -> None:
        self._set_number("BaselineShift", value)

    # ---------- /BBox ----------

    def get_b_box(self) -> tuple[float, float, float, float] | None:
        """
        Return the bounding box as ``(llx, lly, urx, ury)`` or ``None`` if
        absent / malformed. Upstream returns a ``PDRectangle``; the tuple
        form is the established pypdfbox convention for fixed-arity number
        arrays in the layout-attribute surface.
        """
        v = self._dictionary.get_dictionary_object("BBox")
        if not isinstance(v, COSArray) or v.size() != 4:
            return None
        coords: list[float] = []
        for index in range(4):
            item = v.get_object(index)
            if not isinstance(item, (COSInteger, COSFloat)):
                return None
            coords.append(float(item.value))
        return (coords[0], coords[1], coords[2], coords[3])

    def set_b_box(
        self, bbox: tuple[float, float, float, float] | None
    ) -> None:
        """Set ``/BBox`` to a 4-element rectangle, or remove if ``None``."""
        if bbox is None:
            self._dictionary.remove_item("BBox")
            return
        if len(bbox) != 4:
            raise ValueError(
                f"BBox must be a 4-element (llx, lly, urx, ury) tuple, got {len(bbox)}"
            )
        array = COSArray()
        for component in bbox:
            array.add(COSFloat(float(component)))
        self._dictionary.set_item("BBox", array)

    # ---------- /Width ----------

    def get_width(self) -> float | str | None:
        """Return a number, the literal ``"Auto"``, or the default ``"Auto"``."""
        return self.get_number_or_name("Width", self.WIDTH_AUTO)

    def set_width(self, value: float | int | str | None) -> None:
        """Set ``/Width`` to a number, ``"Auto"``, or remove on ``None``."""
        if value is None:
            self._dictionary.remove_item("Width")
        elif isinstance(value, str):
            self._set_name("Width", value)
        else:
            self._set_number("Width", value)

    def set_width_auto(self) -> None:
        """Convenience: set ``/Width`` to the literal name ``"Auto"``."""
        self._set_name("Width", self.WIDTH_AUTO)

    # ---------- /Height ----------

    def get_height(self) -> float | str | None:
        """Return a number, the literal ``"Auto"``, or the default ``"Auto"``."""
        return self.get_number_or_name("Height", self.HEIGHT_AUTO)

    def set_height(self, value: float | int | str | None) -> None:
        """Set ``/Height`` to a number, ``"Auto"``, or remove on ``None``."""
        if value is None:
            self._dictionary.remove_item("Height")
        elif isinstance(value, str):
            self._set_name("Height", value)
        else:
            self._set_number("Height", value)

    def set_height_auto(self) -> None:
        """Convenience: set ``/Height`` to the literal name ``"Auto"``."""
        self._set_name("Height", self.HEIGHT_AUTO)

    # ---------- /BlockAlign ----------

    def get_block_align(self) -> str | None:
        return self._get_name("BlockAlign", self.BLOCK_ALIGN_BEFORE)

    def set_block_align(self, block_align: str) -> None:
        self._set_name("BlockAlign", block_align)

    # ---------- /InlineAlign ----------

    def get_inline_align(self) -> str | None:
        return self._get_name("InlineAlign", self.INLINE_ALIGN_START)

    def set_inline_align(self, inline_align: str) -> None:
        self._set_name("InlineAlign", inline_align)

    # ---------- /ColumnCount ----------

    def get_column_count(self) -> int:
        """Return the column count (default ``1``)."""
        return self._get_integer("ColumnCount", 1)

    def set_column_count(self, count: int) -> None:
        self._set_integer("ColumnCount", count)

    # ---------- /ColumnGap ----------

    def get_column_gap(self) -> float | list[float] | None:
        """Return either a single number or a four-element list of numbers."""
        return self.get_number_or_array_of_number("ColumnGap", self.UNSPECIFIED)

    def set_column_gap(self, value: float | int | list[float] | None) -> None:
        """Single number (uniform) or four-element array (per-side)."""
        if value is None:
            self._dictionary.remove_item("ColumnGap")
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            self._set_number("ColumnGap", value)
        else:
            self._set_array_of_number("ColumnGap", [float(v) for v in value])

    # ---------- /ColumnWidths ----------

    def get_column_widths(self) -> float | list[float] | None:
        """Return either a single number or a list of per-column widths."""
        return self.get_number_or_array_of_number("ColumnWidths", self.UNSPECIFIED)

    def set_column_widths(self, value: float | int | list[float] | None) -> None:
        """Single number (uniform) or per-column number array."""
        if value is None:
            self._dictionary.remove_item("ColumnWidths")
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            self._set_number("ColumnWidths", value)
        else:
            self._set_array_of_number("ColumnWidths", [float(v) for v in value])

    def __repr__(self) -> str:
        return (
            f"PDLayoutAttributeObject(O={self.get_owner()}, "
            f"Placement={self.get_placement()}, "
            f"WritingMode={self.get_writing_mode()})"
        )


__all__ = ["PDLayoutAttributeObject"]
