from __future__ import annotations

from typing import ClassVar

from pypdfbox.cos import COSDictionary, COSName

_I: COSName = COSName.get_pdf_name("I")
_S: COSName = COSName.get_pdf_name("S")


class PDBorderEffectDictionary:
    """
    Border effect dictionary (``/BE`` entry of an annotation dictionary).
    Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderEffectDictionary``
    (PDF 32000-1:2008 §12.5.4 / Table 167).

    Two entries are defined:

    - ``/S`` (name) — the effect style. ``S`` (solid, no effect) or ``C``
      (cloudy). Defaults to ``S``.
    - ``/I`` (number) — intensity of the effect, suggested values 0 to 2.
      Defaults to 0.
    """

    STYLE_SOLID: ClassVar[str] = "S"
    STYLE_CLOUDY: ClassVar[str] = "C"

    #: Tuple of every ``/S`` style code recognised by the spec, in
    #: declaration order. Useful for validation and iteration without
    #: having to keep an external list in sync.
    STYLE_VALUES: ClassVar[tuple[str, ...]] = (STYLE_SOLID, STYLE_CLOUDY)

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /I (intensity) ----------

    def set_intensity(self, i: float) -> None:
        """Set the intensity of the applied effect (suggested 0 to 2)."""
        self._dict.set_float(_I, float(i))

    def get_intensity(self) -> float:
        """Return the intensity of the applied effect; 0 if absent."""
        return self._dict.get_float(_I, 0.0)

    def has_intensity(self) -> bool:
        """True when ``/I`` is explicitly present as a numeric value.

        :meth:`get_intensity` masks an absent ``/I`` by returning ``0.0``;
        this predicate distinguishes "explicitly 0" from "missing entry".
        """
        return self._dict.has_float(_I)

    def clear_intensity(self) -> None:
        """Remove the optional ``/I`` intensity entry."""
        self._dict.remove_item(_I)

    # ---------- /S (style) ----------

    def set_style(self, s: str | None) -> None:
        """Set the border effect style; ``None`` clears the optional ``/S`` entry."""
        self._dict.set_name(_S, s)

    def get_style(self) -> str:
        """Return the border effect style; ``STYLE_SOLID`` if absent.

        Upstream ``getStyle`` reads ``/S`` via ``getNameAsString("S", "S")``,
        so a ``COSString`` value is decoded too.
        """
        return self._dict.get_name_as_string(_S, self.STYLE_SOLID)

    def has_style(self) -> bool:
        """True when ``/S`` is explicitly present as a name.

        :meth:`get_style` masks an absent ``/S`` by returning
        ``STYLE_SOLID`` (the spec default); this predicate distinguishes
        "explicitly solid" from "missing entry".
        """
        return self._dict.has_name(_S)

    def clear_style(self) -> None:
        """Remove the optional ``/S`` style entry."""
        self._dict.remove_item(_S)

    # ---------- /S predicate helpers ----------
    #
    # Parallel to the ``is_*`` predicates on ``PDBorderStyleDictionary``
    # (Wave 202): style equality without requiring callers to import the
    # ``STYLE_*`` constants.

    def is_solid(self) -> bool:
        """True when ``/S`` is solid (the default, no effect)."""
        return self.get_style() == self.STYLE_SOLID

    def is_cloudy(self) -> bool:
        """True when ``/S`` is cloudy."""
        return self.get_style() == self.STYLE_CLOUDY

    # ---------- dunder ----------

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"PDBorderEffectDictionary(style={self.get_style()!r}, "
            f"intensity={self.get_intensity()})"
        )


__all__ = ["PDBorderEffectDictionary"]
