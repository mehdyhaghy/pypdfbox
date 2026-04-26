from __future__ import annotations

from pypdfbox.cos import COSDictionary

from .pd_four_colours import PDFourColours
from .pd_standard_attribute_object import PDStandardAttributeObject


class PDLayoutAttributeObject(PDStandardAttributeObject):
    """
    A layout attribute object (``/O /Layout``). Mirrors PDFBox
    ``PDLayoutAttributeObject``.

    Lite scope: the most common typed accessors per PDF 32000-1:2008
    §14.8.5.4 are exposed. Border / padding / column / decoration / ruby
    accessors and the change-notification plumbing are deferred.
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

    def __repr__(self) -> str:
        return (
            f"PDLayoutAttributeObject(O={self.get_owner()}, "
            f"Placement={self.get_placement()}, "
            f"WritingMode={self.get_writing_mode()})"
        )


__all__ = ["PDLayoutAttributeObject"]
