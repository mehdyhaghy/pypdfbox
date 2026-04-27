from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName

from .pd_transition_direction import PDTransitionDirection
from .pd_transition_dimension import PDTransitionDimension
from .pd_transition_motion import PDTransitionMotion
from .pd_transition_style import PDTransitionStyle

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_TRANS: COSName = COSName.get_pdf_name("Trans")
_S: COSName = COSName.get_pdf_name("S")
_D: COSName = COSName.D  # type: ignore[attr-defined]
_M: COSName = COSName.get_pdf_name("M")
_DM: COSName = COSName.get_pdf_name("Dm")
_DI: COSName = COSName.get_pdf_name("Di")
_SS: COSName = COSName.get_pdf_name("SS")
_B: COSName = COSName.B  # type: ignore[attr-defined]
_NONE: COSName = COSName.get_pdf_name("None")


class PDTransition:
    """Represents a page transition (``/Trans`` dictionary).

    Mirrors PDFBox ``PDTransition``. See paragraph 12.4.4.1 of
    PDF 32000-1:2008.
    """

    #: Motion constant: inward from the edges of the page.
    MOTION_INWARD = "I"
    #: Motion constant: outward from the center of the page.
    MOTION_OUTWARD = "O"
    #: Dimension constant: horizontal.
    DIMENSION_HORIZONTAL = "H"
    #: Dimension constant: vertical.
    DIMENSION_VERTICAL = "V"

    def __init__(
        self,
        dictionary: COSDictionary | None = None,
        style: str | None = None,
    ) -> None:
        if dictionary is None:
            self._dictionary = COSDictionary()
            self._dictionary.set_name(_TYPE, _TRANS.name)
            self._dictionary.set_name(_S, style if style is not None else PDTransitionStyle.R)
        else:
            self._dictionary = dictionary

    def get_cos_object(self) -> COSDictionary:
        return self._dictionary

    # ---------- style ----------

    def get_style(self) -> str:
        return self._dictionary.get_name(_S, PDTransitionStyle.R) or PDTransitionStyle.R

    def set_style(self, style: str) -> None:
        self._dictionary.set_name(_S, style)

    # ---------- duration (/D) ----------

    def get_duration(self) -> float:
        return self._dictionary.get_float(_D, 1)

    def set_duration(self, duration: float) -> None:
        self._dictionary.set_float(_D, duration)

    # ---------- motion (/M) ----------

    def get_motion(self) -> str:
        return self._dictionary.get_name(_M, PDTransitionMotion.I) or PDTransitionMotion.I

    def set_motion(self, motion: str) -> None:
        self._dictionary.set_name(_M, motion)

    # ---------- dimension (/Dm) ----------

    def get_dimension(self) -> str:
        return self._dictionary.get_name(_DM, PDTransitionDimension.H) or PDTransitionDimension.H

    def set_dimension(self, dim: str) -> None:
        self._dictionary.set_name(_DM, dim)

    # ---------- direction (/Di) ----------

    def get_direction(self) -> int:
        item = self._dictionary.get_dictionary_object(_DI)
        if item is None:
            return PDTransitionDirection.LEFT_TO_RIGHT
        if isinstance(item, COSName):
            if item == _NONE:
                return PDTransitionDirection.NONE
            return PDTransitionDirection.LEFT_TO_RIGHT
        if isinstance(item, COSInteger):
            return item.value
        return PDTransitionDirection.LEFT_TO_RIGHT

    def set_direction(self, direction: int) -> None:
        if direction == PDTransitionDirection.NONE:
            self._dictionary.set_item(_DI, _NONE)
        else:
            self._dictionary.set_item(_DI, COSInteger.get(direction))

    # ---------- fly scale (/SS) ----------

    def get_fly_scale(self) -> float:
        return self._dictionary.get_float(_SS, 1)

    def set_fly_scale(self, scale: float) -> None:
        self._dictionary.set_float(_SS, scale)

    # ---------- scale aliases (/SS) ----------

    def get_scale(self) -> float:
        return self._dictionary.get_float(_SS, 1)

    def set_scale(self, scale: float) -> None:
        self._dictionary.set_float(_SS, scale)

    # ---------- fly area opaque (/B) ----------

    def get_fly_area_to_show(self) -> bool:
        return self._dictionary.get_boolean(_B, False)

    def is_fly_area_to_show(self) -> bool:
        return self._dictionary.get_boolean(_B, False)

    def set_fly_area_to_show(self, b: bool) -> None:
        self._dictionary.set_boolean(_B, b)


__all__ = ["PDTransition"]
