from __future__ import annotations

from pypdfbox.cos import COSArray, COSString


class FDFOptionElement:
    """An element of an FDF field's ``/Opt`` array.

    Mirrors ``org.apache.pdfbox.pdmodel.fdf.FDFOptionElement`` (Java
    lines 31-115). Wraps a two-entry ``COSArray`` where the first entry is
    the option string and the second is the default-appearance string.
    """

    def __init__(self, option: COSArray | None = None) -> None:
        if option is None:
            self._option = COSArray()
            self._option.add(COSString(""))
            self._option.add(COSString(""))
        else:
            self._option = option

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSArray:
        """Return the wrapped ``COSArray``. Mirrors upstream
        ``getCOSObject()`` (Java line 61)."""
        return self._option

    def get_cos_array(self) -> COSArray:
        """Return the wrapped ``COSArray``. Mirrors upstream
        ``getCOSArray()`` (Java line 71)."""
        return self._option

    # ---------- option string ----------

    def get_option(self) -> str:
        """Return the option string (index 0).

        Mirrors upstream ``getOption()`` (Java line 81).
        """
        value = self._option.get_object(0)
        if isinstance(value, COSString):
            return value.get_string()
        return ""

    def set_option(self, opt: str) -> None:
        """Set the option string at index 0.

        Mirrors upstream ``setOption(String)`` (Java line 91).
        """
        self._option.set(0, COSString(opt))

    # ---------- default appearance string ----------

    def get_default_appearance_string(self) -> str:
        """Return the default-appearance string (index 1).

        Mirrors upstream ``getDefaultAppearanceString()`` (Java line 101).
        """
        value = self._option.get_object(1)
        if isinstance(value, COSString):
            return value.get_string()
        return ""

    def set_default_appearance_string(self, da: str) -> None:
        """Set the default-appearance string at index 1.

        Mirrors upstream ``setDefaultAppearanceString(String)`` (Java
        line 111).
        """
        self._option.set(1, COSString(da))


__all__ = ["FDFOptionElement"]
