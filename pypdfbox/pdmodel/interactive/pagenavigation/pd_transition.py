from __future__ import annotations

from pypdfbox.cos import (
    COSBase,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
)

from .pd_transition_dimension import PDTransitionDimension
from .pd_transition_direction import PDTransitionDirection
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
        # Upstream PDTransition.getStyle() uses COSDictionary.getNameAsString,
        # so a string-valued /S returns its decoded text, not just a /Name.
        return (
            self._dictionary.get_name_as_string(_S, PDTransitionStyle.R)
            or PDTransitionStyle.R
        )

    def set_style(self, style: str) -> None:
        self._dictionary.set_name(_S, style)

    def has_style(self) -> bool:
        """Return ``True`` when ``/S`` contains a parsable transition style name."""
        return self._dictionary.get_name(_S) is not None

    def clear_style(self) -> None:
        """Remove the transition style (``/S``), restoring the default on read."""
        self._dictionary.remove_item(_S)

    # ---------- duration (/D) ----------

    def get_duration(self) -> float:
        return self._dictionary.get_float(_D, 1)

    def set_duration(self, duration: float) -> None:
        self._dictionary.set_float(_D, duration)

    def has_duration(self) -> bool:
        """Return ``True`` when ``/D`` contains a numeric duration."""
        item = self._dictionary.get_dictionary_object(_D)
        return isinstance(item, (COSFloat, COSInteger))

    def clear_duration(self) -> None:
        """Remove the duration (``/D``), restoring the default on read."""
        self._dictionary.remove_item(_D)

    # ---------- motion (/M) ----------

    def get_motion(self) -> str:
        # Upstream PDTransition.getMotion() uses getNameAsString (string-valued
        # /M returns its decoded text).
        return (
            self._dictionary.get_name_as_string(_M, PDTransitionMotion.I)
            or PDTransitionMotion.I
        )

    def set_motion(self, motion: str) -> None:
        self._dictionary.set_name(_M, motion)

    def has_motion(self) -> bool:
        """Return ``True`` when ``/M`` contains a parsable motion name."""
        return self._dictionary.get_name(_M) is not None

    def clear_motion(self) -> None:
        """Remove the motion (``/M``), restoring the default on read."""
        self._dictionary.remove_item(_M)

    # ---------- dimension (/Dm) ----------

    def get_dimension(self) -> str:
        # Upstream PDTransition.getDimension() uses getNameAsString
        # (string-valued /Dm returns its decoded text).
        return (
            self._dictionary.get_name_as_string(_DM, PDTransitionDimension.H)
            or PDTransitionDimension.H
        )

    def set_dimension(self, dim: str) -> None:
        self._dictionary.set_name(_DM, dim)

    def has_dimension(self) -> bool:
        """Return ``True`` when ``/Dm`` contains a parsable dimension name."""
        return self._dictionary.get_name(_DM) is not None

    def clear_dimension(self) -> None:
        """Remove the dimension (``/Dm``), restoring the default on read."""
        self._dictionary.remove_item(_DM)

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

    def has_direction(self) -> bool:
        """Return ``True`` when ``/Di`` contains a parsable direction value."""
        item = self._dictionary.get_dictionary_object(_DI)
        if isinstance(item, COSInteger):
            return True
        return isinstance(item, COSName) and item == _NONE

    def clear_direction(self) -> None:
        """Remove the direction (``/Di``), restoring the default on read."""
        self._dictionary.remove_item(_DI)

    def get_direction_cos(self) -> COSBase:
        """Return the raw ``/Di`` value as a :class:`COSBase`.

        Mirrors upstream ``PDTransition.getDirection()``, which returns the
        underlying ``COSBase`` (either a ``COSInteger`` or ``COSName.NONE``)
        rather than a Python ``int``. When ``/Di`` is absent the upstream
        contract is to return ``COSInteger.ZERO``.
        """
        item = self._dictionary.get_dictionary_object(_DI)
        if item is None:
            return COSInteger.get(0)
        return item

    # ---------- fly scale (/SS) ----------

    def get_fly_scale(self) -> float:
        return self._dictionary.get_float(_SS, 1)

    def set_fly_scale(self, scale: float) -> None:
        self._dictionary.set_float(_SS, scale)

    def has_fly_scale(self) -> bool:
        """Return ``True`` when ``/SS`` contains a numeric fly scale."""
        item = self._dictionary.get_dictionary_object(_SS)
        return isinstance(item, (COSFloat, COSInteger))

    def clear_fly_scale(self) -> None:
        """Remove the fly scale (``/SS``), restoring the default on read."""
        self._dictionary.remove_item(_SS)

    # ---------- scale aliases (/SS) ----------

    def get_scale(self) -> float:
        return self._dictionary.get_float(_SS, 1)

    def set_scale(self, scale: float) -> None:
        self._dictionary.set_float(_SS, scale)

    def has_scale(self) -> bool:
        """Alias of :meth:`has_fly_scale` matching the ``get_scale`` name."""
        return self.has_fly_scale()

    def clear_scale(self) -> None:
        """Alias of :meth:`clear_fly_scale` matching the ``get_scale`` name."""
        self.clear_fly_scale()

    # ---------- fly area opaque (/B) ----------

    def get_fly_area_to_show(self) -> bool:
        return self._dictionary.get_boolean(_B, False)

    def is_fly_area_to_show(self) -> bool:
        return self._dictionary.get_boolean(_B, False)

    def set_fly_area_to_show(self, b: bool) -> None:
        self._dictionary.set_boolean(_B, b)

    def has_fly_area_to_show(self) -> bool:
        """Return ``True`` when ``/B`` contains a boolean fly-area flag."""
        return isinstance(self._dictionary.get_dictionary_object(_B), COSBoolean)

    def clear_fly_area_to_show(self) -> None:
        """Remove the fly-area flag (``/B``), restoring the default on read."""
        self._dictionary.remove_item(_B)

    # ---------- fly area opaque upstream-name aliases ----------
    #
    # Upstream PDFBox names these ``isFlyAreaOpaque`` / ``setFlyAreaOpaque``.
    # The ``..._to_show`` accessors above predate this round-out; we provide
    # the snake_case equivalents of the upstream names so PDFBox developers
    # can reach for what they expect.

    def is_fly_area_opaque(self) -> bool:
        """Alias of :meth:`is_fly_area_to_show` matching upstream
        ``isFlyAreaOpaque``."""
        return self._dictionary.get_boolean(_B, False)

    def set_fly_area_opaque(self, opaque: bool) -> None:
        """Alias of :meth:`set_fly_area_to_show` matching upstream
        ``setFlyAreaOpaque``."""
        self._dictionary.set_boolean(_B, opaque)

    def has_fly_area_opaque(self) -> bool:
        """Alias of :meth:`has_fly_area_to_show` matching upstream naming."""
        return self.has_fly_area_to_show()

    def clear_fly_area_opaque(self) -> None:
        """Alias of :meth:`clear_fly_area_to_show` matching upstream naming."""
        self.clear_fly_area_to_show()


__all__ = ["PDTransition"]
