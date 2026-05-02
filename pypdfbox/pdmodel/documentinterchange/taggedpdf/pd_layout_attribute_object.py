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
    align, baseline shift, bounding box, content size, column geometry,
    block / inline alignment, table-cell border style / padding, line
    height, text decoration, ruby alignment / position, and glyph
    orientation. The upstream change-notification plumbing
    (``potentiallyNotifyChanged``) is deferred — setters mutate the
    dictionary directly.
    """

    # Owner constant (upstream-parity).
    OWNER_LAYOUT: str = "Layout"
    # Pypdfbox-style alias kept for prior callers.
    OWNER: str = "Layout"

    # ---- Dictionary keys (upstream-parity public statics) ----
    PLACEMENT: str = "Placement"
    WRITING_MODE: str = "WritingMode"
    BACKGROUND_COLOR: str = "BackgroundColor"
    BORDER_COLOR: str = "BorderColor"
    BORDER_STYLE: str = "BorderStyle"
    BORDER_THICKNESS: str = "BorderThickness"
    PADDING: str = "Padding"
    COLOR: str = "Color"
    SPACE_BEFORE: str = "SpaceBefore"
    SPACE_AFTER: str = "SpaceAfter"
    START_INDENT: str = "StartIndent"
    END_INDENT: str = "EndIndent"
    TEXT_INDENT: str = "TextIndent"
    TEXT_ALIGN: str = "TextAlign"
    BBOX: str = "BBox"
    WIDTH: str = "Width"
    HEIGHT: str = "Height"
    BLOCK_ALIGN: str = "BlockAlign"
    INLINE_ALIGN: str = "InlineAlign"
    T_BORDER_STYLE: str = "TBorderStyle"
    T_PADDING: str = "TPadding"
    BASELINE_SHIFT: str = "BaselineShift"
    LINE_HEIGHT: str = "LineHeight"
    TEXT_DECORATION_COLOR: str = "TextDecorationColor"
    TEXT_DECORATION_THICKNESS: str = "TextDecorationThickness"
    TEXT_DECORATION_TYPE: str = "TextDecorationType"
    RUBY_ALIGN: str = "RubyAlign"
    RUBY_POSITION: str = "RubyPosition"
    GLYPH_ORIENTATION_VERTICAL: str = "GlyphOrientationVertical"
    COLUMN_COUNT: str = "ColumnCount"
    COLUMN_GAP: str = "ColumnGap"
    COLUMN_WIDTHS: str = "ColumnWidths"

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

    # LineHeight name sentinels (PDF 32000-1 §14.8.5.4 Table 343)
    LINE_HEIGHT_NORMAL: str = "Normal"
    LINE_HEIGHT_AUTO: str = "Auto"

    # TextDecorationType values
    TEXT_DECORATION_TYPE_NONE: str = "None"
    TEXT_DECORATION_TYPE_UNDERLINE: str = "Underline"
    TEXT_DECORATION_TYPE_OVERLINE: str = "Overline"
    TEXT_DECORATION_TYPE_LINE_THROUGH: str = "LineThrough"

    # RubyAlign values
    RUBY_ALIGN_START: str = "Start"
    RUBY_ALIGN_CENTER: str = "Center"
    RUBY_ALIGN_END: str = "End"
    RUBY_ALIGN_JUSTIFY: str = "Justify"
    RUBY_ALIGN_DISTRIBUTE: str = "Distribute"

    # RubyPosition values
    RUBY_POSITION_BEFORE: str = "Before"
    RUBY_POSITION_AFTER: str = "After"
    RUBY_POSITION_WARICHU: str = "Warichu"
    RUBY_POSITION_INLINE: str = "Inline"

    # GlyphOrientationVertical values (PDF 32000-1 §14.8.5.4 Table 343)
    GLYPH_ORIENTATION_VERTICAL_AUTO: str = "Auto"
    GLYPH_ORIENTATION_VERTICAL_MINUS_180_DEGREES: str = "-180"
    GLYPH_ORIENTATION_VERTICAL_MINUS_90_DEGREES: str = "-90"
    GLYPH_ORIENTATION_VERTICAL_ZERO_DEGREES: str = "0"
    GLYPH_ORIENTATION_VERTICAL_90_DEGREES: str = "90"
    GLYPH_ORIENTATION_VERTICAL_180_DEGREES: str = "180"
    GLYPH_ORIENTATION_VERTICAL_270_DEGREES: str = "270"
    GLYPH_ORIENTATION_VERTICAL_360_DEGREES: str = "360"

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

    def set_all_border_colors(self, rgb: tuple[float, ...] | None) -> None:
        """
        Set ``/BorderColor`` to a single RGB triple applied to all four
        sides. Mirrors upstream ``setAllBorderColors(PDGamma)``.
        """
        self._set_color_value("BorderColor", rgb)

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

    # ---------- Upstream-parity overload-style aliases ----------
    #
    # Upstream Java exposes both ``setAllXxx(scalar)`` and ``setXxxs(array)``
    # for the four-side / per-side layout attributes. Python collapses the
    # overloads into a single polymorphic setter (the methods above), but
    # we expose the upstream names so PDFBox-shaped code ports cleanly.

    def set_all_border_styles(self, value: str | None) -> None:
        """Set ``/BorderStyle`` to a single name applied to all four sides."""
        self.set_border_style(value)

    def set_border_styles(self, values: list[str] | None) -> None:
        """Set ``/BorderStyle`` to a four-element per-side name array."""
        if values is None:
            self._dictionary.remove_item("BorderStyle")
        else:
            self._set_array_of_name("BorderStyle", list(values))

    def set_all_border_thicknesses(self, value: float | int | None) -> None:
        """Set ``/BorderThickness`` to a single number applied to all sides."""
        self.set_border_thickness(value)

    def set_border_thicknesses(self, values: list[float] | None) -> None:
        """Set ``/BorderThickness`` to a per-side number array."""
        if values is None:
            self._dictionary.remove_item("BorderThickness")
        else:
            self._set_array_of_number("BorderThickness", [float(v) for v in values])

    def set_all_paddings(self, value: float | int | None) -> None:
        """Set ``/Padding`` to a single number applied to all four sides."""
        self.set_padding(value)

    def set_paddings(self, values: list[float] | None) -> None:
        """Set ``/Padding`` to a four-element per-side number array."""
        if values is None:
            self._dictionary.remove_item("Padding")
        else:
            self._set_array_of_number("Padding", [float(v) for v in values])

    def set_all_column_widths(self, value: float | int | None) -> None:
        """Set ``/ColumnWidths`` to a single number applied to all columns."""
        self.set_column_widths(value)

    def set_column_gaps(self, values: list[float] | None) -> None:
        """Set ``/ColumnGap`` to a per-gap number array."""
        if values is None:
            self._dictionary.remove_item("ColumnGap")
        else:
            self._set_array_of_number("ColumnGap", [float(v) for v in values])

    # ---------- /TBorderStyle (table-cell border style) ----------

    def get_t_border_style(self) -> str | list[str] | None:
        """Return either a single name or a four-element per-side list.
        Defaults to :attr:`BORDER_STYLE_NONE` when absent."""
        return self.get_name_or_array_of_name("TBorderStyle", self.BORDER_STYLE_NONE)

    def set_t_border_style(self, value: str | list[str] | None) -> None:
        """Set ``/TBorderStyle`` to a single name (all sides) or a four-element
        per-side name array."""
        if value is None:
            self._dictionary.remove_item("TBorderStyle")
        elif isinstance(value, str):
            self._set_name("TBorderStyle", value)
        else:
            self._set_array_of_name("TBorderStyle", list(value))

    def set_all_t_border_styles(self, value: str | None) -> None:
        """Upstream-parity single-name setter for ``/TBorderStyle``."""
        self.set_t_border_style(value)

    def set_t_border_styles(self, values: list[str] | None) -> None:
        """Upstream-parity per-side array setter for ``/TBorderStyle``."""
        if values is None:
            self._dictionary.remove_item("TBorderStyle")
        else:
            self._set_array_of_name("TBorderStyle", list(values))

    # ---------- /TPadding (table-cell padding) ----------

    def get_t_padding(self) -> float | list[float] | None:
        """Return either a single number or a four-element per-side list.
        Defaults to ``0.0`` when absent."""
        return self.get_number_or_array_of_number("TPadding", 0.0)

    def set_t_padding(self, value: float | int | list[float] | None) -> None:
        """Set ``/TPadding`` to a single number (uniform) or a four-element
        per-side number array."""
        if value is None:
            self._dictionary.remove_item("TPadding")
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            self._set_number("TPadding", value)
        else:
            self._set_array_of_number("TPadding", [float(v) for v in value])

    def set_all_t_paddings(self, value: float | int | None) -> None:
        """Upstream-parity single-number setter for ``/TPadding``."""
        self.set_t_padding(value)

    def set_t_paddings(self, values: list[float] | None) -> None:
        """Upstream-parity per-side array setter for ``/TPadding``."""
        if values is None:
            self._dictionary.remove_item("TPadding")
        else:
            self._set_array_of_number("TPadding", [float(v) for v in values])

    # ---------- /LineHeight ----------

    def get_line_height(self) -> float | str | None:
        """Return a number, the literal ``"Normal"``, the literal ``"Auto"``,
        or the default ``"Normal"`` when absent."""
        return self.get_number_or_name("LineHeight", self.LINE_HEIGHT_NORMAL)

    def set_line_height(self, value: float | int | str | None) -> None:
        """Set ``/LineHeight`` to a number, ``"Normal"``, ``"Auto"``, or
        remove on ``None``."""
        if value is None:
            self._dictionary.remove_item("LineHeight")
        elif isinstance(value, str):
            self._set_name("LineHeight", value)
        else:
            self._set_number("LineHeight", value)

    def set_line_height_normal(self) -> None:
        """Convenience: set ``/LineHeight`` to ``"Normal"``."""
        self._set_name("LineHeight", self.LINE_HEIGHT_NORMAL)

    def set_line_height_auto(self) -> None:
        """Convenience: set ``/LineHeight`` to ``"Auto"``."""
        self._set_name("LineHeight", self.LINE_HEIGHT_AUTO)

    # ---------- /TextDecorationColor ----------

    def get_text_decoration_color(self) -> tuple[float, ...] | None:
        return self._get_color_value("TextDecorationColor")

    def set_text_decoration_color(self, rgb: tuple[float, ...] | None) -> None:
        self._set_color_value("TextDecorationColor", rgb)

    # ---------- /TextDecorationThickness ----------

    def get_text_decoration_thickness(self) -> float:
        """Return the decoration thickness; ``UNSPECIFIED`` (-1.0) when absent."""
        return self._get_number("TextDecorationThickness", self.UNSPECIFIED)

    def set_text_decoration_thickness(self, value: float | int) -> None:
        self._set_number("TextDecorationThickness", value)

    # ---------- /TextDecorationType ----------

    def get_text_decoration_type(self) -> str | None:
        return self._get_name(
            "TextDecorationType", self.TEXT_DECORATION_TYPE_NONE
        )

    def set_text_decoration_type(self, value: str) -> None:
        self._set_name("TextDecorationType", value)

    # ---------- /RubyAlign ----------

    def get_ruby_align(self) -> str | None:
        return self._get_name("RubyAlign", self.RUBY_ALIGN_DISTRIBUTE)

    def set_ruby_align(self, value: str) -> None:
        self._set_name("RubyAlign", value)

    # ---------- /RubyPosition ----------

    def get_ruby_position(self) -> str | None:
        return self._get_name("RubyPosition", self.RUBY_POSITION_BEFORE)

    def set_ruby_position(self, value: str) -> None:
        self._set_name("RubyPosition", value)

    # ---------- /GlyphOrientationVertical ----------

    def get_glyph_orientation_vertical(self) -> str | None:
        return self._get_name(
            "GlyphOrientationVertical", self.GLYPH_ORIENTATION_VERTICAL_AUTO
        )

    def set_glyph_orientation_vertical(self, value: str) -> None:
        self._set_name("GlyphOrientationVertical", value)

    def __str__(self) -> str:
        """Mirror upstream ``PDLayoutAttributeObject.toString()`` which
        appends ``", <FieldName>=<value>"`` for every entry that is
        specified, in the dictionary-key order defined in the upstream
        class. Per upstream, list-shaped values (``BorderStyle``,
        ``BorderThickness``, ``Padding``, ``TBorderStyle``, ``TPadding``,
        ``ColumnGap``, ``ColumnWidths``) are formatted via
        :meth:`PDAttributeObject.array_to_string` when they are arrays
        and inlined as-is when they are scalars / single names."""
        sb = super().__str__()

        def append_scalar(key: str, value: object) -> str:
            return f", {key}={value}"

        def append_polymorphic(key: str, value: object) -> str:
            if isinstance(value, list):
                return f", {key}={self.array_to_string(value)}"
            return f", {key}={value}"

        if self.is_specified(self.PLACEMENT):
            sb += append_scalar("Placement", self.get_placement())
        if self.is_specified(self.WRITING_MODE):
            sb += append_scalar("WritingMode", self.get_writing_mode())
        if self.is_specified(self.BACKGROUND_COLOR):
            sb += append_scalar("BackgroundColor", self.get_background_color())
        if self.is_specified(self.BORDER_COLOR):
            sb += append_scalar("BorderColor", self.get_border_colors())
        if self.is_specified(self.BORDER_STYLE):
            sb += append_polymorphic("BorderStyle", self.get_border_style())
        if self.is_specified(self.BORDER_THICKNESS):
            sb += append_polymorphic(
                "BorderThickness", self.get_border_thickness()
            )
        if self.is_specified(self.PADDING):
            sb += append_polymorphic("Padding", self.get_padding())
        if self.is_specified(self.COLOR):
            sb += append_scalar("Color", self.get_color())
        if self.is_specified(self.SPACE_BEFORE):
            sb += append_scalar("SpaceBefore", self.get_space_before())
        if self.is_specified(self.SPACE_AFTER):
            sb += append_scalar("SpaceAfter", self.get_space_after())
        if self.is_specified(self.START_INDENT):
            sb += append_scalar("StartIndent", self.get_start_indent())
        if self.is_specified(self.END_INDENT):
            sb += append_scalar("EndIndent", self.get_end_indent())
        if self.is_specified(self.TEXT_INDENT):
            sb += append_scalar("TextIndent", self.get_text_indent())
        if self.is_specified(self.TEXT_ALIGN):
            sb += append_scalar("TextAlign", self.get_text_align())
        if self.is_specified(self.BBOX):
            sb += append_scalar("BBox", self.get_b_box())
        if self.is_specified(self.WIDTH):
            sb += append_scalar("Width", self.get_width())
        if self.is_specified(self.HEIGHT):
            sb += append_scalar("Height", self.get_height())
        if self.is_specified(self.BLOCK_ALIGN):
            sb += append_scalar("BlockAlign", self.get_block_align())
        if self.is_specified(self.INLINE_ALIGN):
            sb += append_scalar("InlineAlign", self.get_inline_align())
        if self.is_specified(self.T_BORDER_STYLE):
            sb += append_polymorphic("TBorderStyle", self.get_t_border_style())
        if self.is_specified(self.T_PADDING):
            sb += append_polymorphic("TPadding", self.get_t_padding())
        if self.is_specified(self.BASELINE_SHIFT):
            sb += append_scalar("BaselineShift", self.get_baseline_shift())
        if self.is_specified(self.LINE_HEIGHT):
            sb += append_scalar("LineHeight", self.get_line_height())
        if self.is_specified(self.TEXT_DECORATION_COLOR):
            sb += append_scalar(
                "TextDecorationColor", self.get_text_decoration_color()
            )
        if self.is_specified(self.TEXT_DECORATION_THICKNESS):
            sb += append_scalar(
                "TextDecorationThickness", self.get_text_decoration_thickness()
            )
        if self.is_specified(self.TEXT_DECORATION_TYPE):
            sb += append_scalar(
                "TextDecorationType", self.get_text_decoration_type()
            )
        if self.is_specified(self.RUBY_ALIGN):
            sb += append_scalar("RubyAlign", self.get_ruby_align())
        if self.is_specified(self.RUBY_POSITION):
            sb += append_scalar("RubyPosition", self.get_ruby_position())
        if self.is_specified(self.GLYPH_ORIENTATION_VERTICAL):
            sb += append_scalar(
                "GlyphOrientationVertical", self.get_glyph_orientation_vertical()
            )
        if self.is_specified(self.COLUMN_COUNT):
            sb += append_scalar("ColumnCount", self.get_column_count())
        if self.is_specified(self.COLUMN_GAP):
            sb += append_polymorphic("ColumnGap", self.get_column_gap())
        if self.is_specified(self.COLUMN_WIDTHS):
            sb += append_polymorphic("ColumnWidths", self.get_column_widths())
        return sb

    def __repr__(self) -> str:
        return (
            f"PDLayoutAttributeObject(O={self.get_owner()}, "
            f"Placement={self.get_placement()}, "
            f"WritingMode={self.get_writing_mode()})"
        )


__all__ = ["PDLayoutAttributeObject"]
