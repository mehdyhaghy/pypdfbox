from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

_P: COSName = COSName.get_pdf_name("P")


class PDSeedValueMDP:
    """``/MDP`` sub-dictionary of a seed value (``/Type /SV``) entry.

    Mirrors PDFBox ``PDSeedValueMDP`` (PDF 32000-1 §12.7.4.5, Table 235).
    Defines whether an author signature or a certification signature shall
    be used. The single field is ``/P`` whose integer value (0..3) is
    interpreted per ISO 32000-1 §12.8.2.2.2:

    * 0 — author signature
    * 1 — certification signature, no changes permitted
    * 2 — certification signature, form fill-in / signing permitted
    * 3 — certification signature, plus annotation/form/signing permitted
    """

    def __init__(self, dict_: COSDictionary | None = None) -> None:
        if dict_ is None:
            self._dict = COSDictionary()
        else:
            self._dict = dict_
        self._dict.set_direct(True)

    def get_cos_object(self) -> COSDictionary:
        """Return the wrapped ``COSDictionary``."""
        return self._dict

    # ---------- /P ----------

    def get_p(self) -> int:
        """Return the ``/P`` permission integer (0..3); ``-1`` if absent
        (mirrors ``COSDictionary.get_int`` default behavior)."""
        return self._dict.get_int(_P)

    def set_p(self, p: int) -> None:
        """Set the ``/P`` permission integer.

        Raises :class:`ValueError` if ``p`` is not in ``[0, 3]``.
        Mirrors upstream ``IllegalArgumentException``.
        """
        if p < 0 or p > 3:
            raise ValueError("Only values between 0 and 3 are allowed.")
        self._dict.set_int(_P, p)


__all__ = ["PDSeedValueMDP"]
