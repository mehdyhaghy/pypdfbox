from __future__ import annotations

from typing import ClassVar

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

_SW: COSName = COSName.get_pdf_name("SW")
_S: COSName = COSName.get_pdf_name("S")
_A: COSName = COSName.get_pdf_name("A")
_FB: COSName = COSName.get_pdf_name("FB")


class PDIconFit:
    """
    Icon-fit dictionary (``/IF`` entry of an appearance-characteristics
    dictionary) describing how a button widget's icon is scaled and
    positioned within its annotation rectangle.

    Mirrors ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceCharacteristicsDictionary``
    (sub-dictionary type — see PDF 32000-1:2008 §12.5.6.19, Table 247).

    Entries:

    - ``/SW`` — *scale when* — ``A``=Always (default), ``B``=icon Bigger
      than annotation, ``S``=icon Smaller than annotation, ``N``=Never.
    - ``/S``  — *scale type* — ``A``=Anamorphic (non-proportional),
      ``P``=Proportional (default).
    - ``/A``  — *fractional space* — 2-element array ``[x y]`` of floats
      in 0..1 specifying icon position; default ``[0.5, 0.5]`` (centered).
    - ``/FB`` — *fit to bounds* — boolean; if true the icon is scaled to
      fit inside the annotation border rather than the annotation
      rectangle. Default ``false``.
    """

    # /SW values
    SCALE_OPTION_ALWAYS: str = "A"
    SCALE_OPTION_ICON_IS_BIGGER: str = "B"
    SCALE_OPTION_ICON_IS_SMALLER: str = "S"
    SCALE_OPTION_NEVER: str = "N"

    # /S values
    SCALE_TYPE_ANAMORPHIC: str = "A"
    SCALE_TYPE_PROPORTIONAL: str = "P"

    #: Tuple of every ``/SW`` scale-option code recognised by the spec, in
    #: declaration order. Useful for validation and iteration without
    #: maintaining a parallel external list.
    SCALE_OPTION_VALUES: ClassVar[tuple[str, ...]] = (
        SCALE_OPTION_ALWAYS,
        SCALE_OPTION_ICON_IS_BIGGER,
        SCALE_OPTION_ICON_IS_SMALLER,
        SCALE_OPTION_NEVER,
    )

    #: Tuple of every ``/S`` scale-type code recognised by the spec, in
    #: declaration order.
    SCALE_TYPE_VALUES: ClassVar[tuple[str, ...]] = (
        SCALE_TYPE_ANAMORPHIC,
        SCALE_TYPE_PROPORTIONAL,
    )

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /SW (scale option / "scale when") ----------

    def get_scale_option(self) -> str:
        """``/SW`` — when to scale the icon. Default ``"A"`` (Always)."""
        value = self._dict.get_name(_SW)
        return value if value is not None else self.SCALE_OPTION_ALWAYS

    def set_scale_option(self, scale_option: str | None) -> None:
        """Set ``/SW``. Pass ``None`` to remove the entry — the spec
        default is ``Always``."""
        self._dict.set_name(_SW, scale_option)

    def has_scale_option(self) -> bool:
        """True when ``/SW`` is explicitly present on the dictionary.

        :meth:`get_scale_option` masks an absent ``/SW`` by returning
        ``SCALE_OPTION_ALWAYS`` (the spec default); this predicate
        distinguishes "explicitly Always" from "missing entry".
        """
        return self._dict.contains_key(_SW)

    # ---------- /SW predicate helpers ----------

    def is_scale_always(self) -> bool:
        """True when ``/SW`` is ``"A"`` (the default; always scale)."""
        return self.get_scale_option() == self.SCALE_OPTION_ALWAYS

    def is_scale_when_bigger(self) -> bool:
        """True when ``/SW`` is ``"B"`` (scale only when icon is bigger
        than the annotation)."""
        return self.get_scale_option() == self.SCALE_OPTION_ICON_IS_BIGGER

    def is_scale_when_smaller(self) -> bool:
        """True when ``/SW`` is ``"S"`` (scale only when icon is smaller
        than the annotation)."""
        return self.get_scale_option() == self.SCALE_OPTION_ICON_IS_SMALLER

    def is_scale_never(self) -> bool:
        """True when ``/SW`` is ``"N"`` (never scale)."""
        return self.get_scale_option() == self.SCALE_OPTION_NEVER

    # ---------- /S (scale type) ----------

    def get_scale_type(self) -> str:
        """``/S`` — Anamorphic (``"A"``) or Proportional (``"P"``).
        Default ``"P"``."""
        value = self._dict.get_name(_S)
        return value if value is not None else self.SCALE_TYPE_PROPORTIONAL

    def set_scale_type(self, scale_type: str | None) -> None:
        """Set ``/S``. Pass ``None`` to remove the entry — the spec
        default is ``Proportional``."""
        self._dict.set_name(_S, scale_type)

    def has_scale_type(self) -> bool:
        """True when ``/S`` is explicitly present on the dictionary.

        :meth:`get_scale_type` masks an absent ``/S`` by returning
        ``SCALE_TYPE_PROPORTIONAL`` (the spec default); this predicate
        distinguishes "explicitly Proportional" from "missing entry".
        """
        return self._dict.contains_key(_S)

    # ---------- /S predicate helpers ----------

    def is_anamorphic(self) -> bool:
        """True when ``/S`` is ``"A"`` (non-proportional scaling)."""
        return self.get_scale_type() == self.SCALE_TYPE_ANAMORPHIC

    def is_proportional(self) -> bool:
        """True when ``/S`` is ``"P"`` (the default; proportional
        scaling)."""
        return self.get_scale_type() == self.SCALE_TYPE_PROPORTIONAL

    # ---------- /A (fractional space) ----------

    def _fractional_space(self) -> tuple[float, float]:
        value = self._dict.get_dictionary_object(_A)
        if isinstance(value, COSArray) and value.size() >= 2:
            xs = value.to_float_array()
            return float(xs[0]), float(xs[1])
        return 0.5, 0.5

    def get_fractional_space(self) -> tuple[float, float]:
        """``/A`` — fractional icon position as ``(x, y)``. Default
        ``(0.5, 0.5)`` (centered). Convenience accessor that returns
        both fractional offsets in a single call."""
        return self._fractional_space()

    def get_fractional_space_x(self) -> float:
        """``/A[0]`` — horizontal icon position. Default ``0.5``."""
        return self._fractional_space()[0]

    def get_fractional_space_y(self) -> float:
        """``/A[1]`` — vertical icon position. Default ``0.5``."""
        return self._fractional_space()[1]

    def set_fractional_space(self, x: float, y: float) -> None:
        """Set ``/A`` to ``[x y]``."""
        arr = COSArray([COSFloat(float(x)), COSFloat(float(y))])
        self._dict.set_item(_A, arr)

    def has_fractional_space(self) -> bool:
        """True when ``/A`` is explicitly present on the dictionary.

        :meth:`get_fractional_space` masks an absent ``/A`` by returning
        the spec default ``(0.5, 0.5)``; this predicate distinguishes
        "explicit centered position" from "missing entry".
        """
        return self._dict.contains_key(_A)

    # ---------- /FB (fit to bounds) ----------

    def is_fit_to_bounds(self) -> bool:
        """``/FB`` — when true, scale to fit inside the annotation border
        rather than the annotation rectangle. Default ``False``."""
        return self._dict.get_boolean(_FB, False)

    def set_fit_to_bounds(self, value: bool) -> None:
        self._dict.set_boolean(_FB, bool(value))

    def has_fit_to_bounds(self) -> bool:
        """True when ``/FB`` is explicitly present on the dictionary.

        :meth:`is_fit_to_bounds` masks an absent ``/FB`` by returning
        ``False`` (the spec default); this predicate distinguishes
        "explicitly false" from "missing entry".
        """
        return self._dict.contains_key(_FB)

    # The PRD's task brief calls this ``get_dont_stretch``; in PDF 32000-1
    # the closest semantic is the *inverse* of /FB combined with a
    # Never-scale option. We expose it as a thin alias over /FB for
    # cluster compatibility.
    def get_dont_stretch(self) -> bool:
        """Alias: returns ``True`` when scaling is suppressed
        (``/SW == "N"``). The PDF spec has no dedicated ``DontStretch``
        entry — this helper exists for the task brief's API surface."""
        return self.get_scale_option() == self.SCALE_OPTION_NEVER

    # ---------- dunder ----------

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        x, y = self._fractional_space()
        return (
            f"PDIconFit(scale_option={self.get_scale_option()!r}, "
            f"scale_type={self.get_scale_type()!r}, "
            f"fractional_space=({x}, {y}), "
            f"fit_to_bounds={self.is_fit_to_bounds()})"
        )


__all__ = ["PDIconFit"]
