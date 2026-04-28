from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream

from .pd_icon_fit import PDIconFit

if TYPE_CHECKING:
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject

_R: COSName = COSName.get_pdf_name("R")
_BC: COSName = COSName.get_pdf_name("BC")
_BG: COSName = COSName.get_pdf_name("BG")
_CA: COSName = COSName.get_pdf_name("CA")
_RC: COSName = COSName.get_pdf_name("RC")
_AC: COSName = COSName.get_pdf_name("AC")
_I: COSName = COSName.get_pdf_name("I")
_RI: COSName = COSName.get_pdf_name("RI")
_IX: COSName = COSName.get_pdf_name("IX")
_IF: COSName = COSName.get_pdf_name("IF")
_TP: COSName = COSName.get_pdf_name("TP")


def _to_form(stream: COSStream) -> PDFormXObject:
    # Local import to avoid a top-level cycle through the graphics module.
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import (  # noqa: PLC0415
        PDFormXObject,
    )

    return PDFormXObject(stream)


def _icon_to_cos(value: object) -> COSStream:
    """Accept a raw ``COSStream`` or a ``PDFormXObject`` and return the
    underlying stream."""
    if isinstance(value, COSStream):
        return value
    # Duck-type: treat anything with ``get_cos_object()`` returning a
    # COSStream as a PDFormXObject without importing it eagerly.
    cos = getattr(value, "get_cos_object", None)
    if callable(cos):
        out = cos()
        if isinstance(out, COSStream):
            return out
    raise TypeError(
        f"icon must be a COSStream or PDFormXObject; got {type(value).__name__}"
    )


class PDAppearanceCharacteristicsDictionary:
    """
    Appearance characteristics dictionary (``/MK``) for widget annotations.
    Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceCharacteristicsDictionary``
    (PDF 32000-1:2008 §12.5.6.19, Table 189).

    ``/BC`` / ``/BG`` are exposed as raw ``COSArray`` (a typed ``PDColor``
    wrapper lands with the colour-space cluster). ``/I`` / ``/RI`` /
    ``/IX`` are typed as ``PDFormXObject`` for parity with upstream;
    setters also accept a raw ``COSStream`` for low-level callers.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /R (rotation) ----------

    def get_rotation(self) -> int:
        """Multiple of 90, default 0."""
        return self._dict.get_int(_R, 0)

    def set_rotation(self, rotation: int) -> None:
        self._dict.set_int(_R, rotation)

    # ---------- /BC (border colour, raw COSArray) ----------

    def get_border_colour(self) -> COSArray | None:
        value = self._dict.get_dictionary_object(_BC)
        if isinstance(value, COSArray):
            return value
        return None

    def set_border_colour(self, c: COSArray | None) -> None:
        if c is None:
            self._dict.remove_item(_BC)
            return
        self._dict.set_item(_BC, c)

    # ---------- /BG (background colour, raw COSArray) ----------

    def get_background(self) -> COSArray | None:
        value = self._dict.get_dictionary_object(_BG)
        if isinstance(value, COSArray):
            return value
        return None

    def set_background(self, c: COSArray | None) -> None:
        if c is None:
            self._dict.remove_item(_BG)
            return
        self._dict.set_item(_BG, c)

    # ---------- /CA (normal caption) ----------

    def get_normal_caption(self) -> str | None:
        return self._dict.get_string(_CA)

    def set_normal_caption(self, caption: str | None) -> None:
        self._dict.set_string(_CA, caption)

    # ---------- /RC (rollover caption) ----------

    def get_rollover_caption(self) -> str | None:
        return self._dict.get_string(_RC)

    def set_rollover_caption(self, caption: str | None) -> None:
        self._dict.set_string(_RC, caption)

    # ---------- /AC (alternate caption) ----------

    def get_alternate_caption(self) -> str | None:
        return self._dict.get_string(_AC)

    def set_alternate_caption(self, caption: str | None) -> None:
        self._dict.set_string(_AC, caption)

    # ---------- /I (normal icon) ----------
    #
    # Getter returns the raw ``COSStream`` (lite), matching the existing
    # widget-cluster API. Use ``get_normal_icon_form()`` for the typed
    # ``PDFormXObject`` wrapper.

    def get_normal_icon(self) -> COSStream | None:
        value = self._dict.get_dictionary_object(_I)
        if isinstance(value, COSStream):
            return value
        return None

    def get_normal_icon_form(self) -> PDFormXObject | None:
        """Typed ``/I`` form-XObject icon, ``None`` when absent."""
        value = self._dict.get_dictionary_object(_I)
        if isinstance(value, COSStream):
            return _to_form(value)
        return None

    def set_normal_icon(self, icon: PDFormXObject | COSStream | None) -> None:
        if icon is None:
            self._dict.remove_item(_I)
            return
        self._dict.set_item(_I, _icon_to_cos(icon))

    # ---------- /RI (rollover icon) ----------

    def get_rollover_icon(self) -> COSStream | None:
        value = self._dict.get_dictionary_object(_RI)
        if isinstance(value, COSStream):
            return value
        return None

    def get_rollover_icon_form(self) -> PDFormXObject | None:
        value = self._dict.get_dictionary_object(_RI)
        if isinstance(value, COSStream):
            return _to_form(value)
        return None

    def set_rollover_icon(self, icon: PDFormXObject | COSStream | None) -> None:
        if icon is None:
            self._dict.remove_item(_RI)
            return
        self._dict.set_item(_RI, _icon_to_cos(icon))

    # ---------- /IX (alternate icon) ----------

    def get_alternate_icon(self) -> COSStream | None:
        value = self._dict.get_dictionary_object(_IX)
        if isinstance(value, COSStream):
            return value
        return None

    def get_alternate_icon_form(self) -> PDFormXObject | None:
        value = self._dict.get_dictionary_object(_IX)
        if isinstance(value, COSStream):
            return _to_form(value)
        return None

    def set_alternate_icon(self, icon: PDFormXObject | COSStream | None) -> None:
        if icon is None:
            self._dict.remove_item(_IX)
            return
        self._dict.set_item(_IX, _icon_to_cos(icon))

    # ---------- /IF (icon fit) ----------

    def get_icon_fit(self) -> PDIconFit | None:
        """Typed ``/IF`` icon-fit sub-dictionary; ``None`` when absent."""
        value = self._dict.get_dictionary_object(_IF)
        if isinstance(value, COSDictionary):
            return PDIconFit(value)
        return None

    def set_icon_fit(self, icon_fit: PDIconFit | COSDictionary | None) -> None:
        if icon_fit is None:
            self._dict.remove_item(_IF)
            return
        if isinstance(icon_fit, COSDictionary):
            self._dict.set_item(_IF, icon_fit)
            return
        self._dict.set_item(_IF, icon_fit.get_cos_object())

    # ---------- /TP (text position) ----------

    def get_text_position(self) -> int:
        """Caption-vs-icon position code, default 0 (caption only)."""
        return self._dict.get_int(_TP, 0)

    def set_text_position(self, tp: int) -> None:
        self._dict.set_int(_TP, tp)


__all__ = ["PDAppearanceCharacteristicsDictionary"]
