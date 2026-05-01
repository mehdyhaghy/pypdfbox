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

    # ---------- /S (style) ----------

    def set_style(self, s: str) -> None:
        """Set the border effect style; see the ``STYLE_*`` constants."""
        self._dict.set_name(_S, s)

    def get_style(self) -> str:
        """Return the border effect style; ``STYLE_SOLID`` if absent."""
        value = self._dict.get_name(_S)
        return value if value is not None else self.STYLE_SOLID


__all__ = ["PDBorderEffectDictionary"]
