from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream

from .pd_icon_fit import PDIconFit

if TYPE_CHECKING:
    from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
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


def _read_color(dictionary: COSDictionary, key: COSName) -> PDColor | None:
    """Read a ``/BC`` or ``/BG`` colour entry as a typed :class:`PDColor`.

    Mirrors the private ``getColor(COSName)`` helper in upstream
    ``PDAppearanceCharacteristicsDictionary``: dispatch on the array
    arity to ``DeviceGray`` (1), ``DeviceRGB`` (3) or ``DeviceCMYK``
    (4); ``None`` for any other length and when the entry is absent.
    """
    value = dictionary.get_dictionary_object(key)
    if not isinstance(value, COSArray):
        return None
    # Local imports avoid a top-level cycle through the colour module.
    from pypdfbox.pdmodel.graphics.color.pd_color import PDColor  # noqa: PLC0415
    from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import (  # noqa: PLC0415
        PDDeviceCMYK,
    )
    from pypdfbox.pdmodel.graphics.color.pd_device_gray import (  # noqa: PLC0415
        PDDeviceGray,
    )
    from pypdfbox.pdmodel.graphics.color.pd_device_rgb import (  # noqa: PLC0415
        PDDeviceRGB,
    )

    size = value.size()
    if size == 1:
        cs = PDDeviceGray.INSTANCE
    elif size == 3:
        cs = PDDeviceRGB.INSTANCE
    elif size == 4:
        cs = PDDeviceCMYK.INSTANCE
    else:
        return None
    return PDColor(value, cs)


def _color_to_cos_array(value: object) -> COSArray:
    """Coerce a ``PDColor`` or raw ``COSArray`` to a ``COSArray``.

    Upstream's ``setBorderColour(PDColor)`` writes ``c.toCOSArray()``;
    pypdfbox accepts either a typed :class:`PDColor` (calls
    ``to_cos_array()``) or a raw :class:`COSArray` for low-level
    callers and during round-trips through ``get_border_colour_array()``.
    """
    if isinstance(value, COSArray):
        return value
    to_cos_array = getattr(value, "to_cos_array", None)
    if callable(to_cos_array):
        out = to_cos_array()
        if isinstance(out, COSArray):
            return out
    raise TypeError(
        f"colour must be a PDColor or COSArray; got {type(value).__name__}"
    )


class PDAppearanceCharacteristicsDictionary:
    """
    Appearance characteristics dictionary (``/MK``) for widget annotations.
    Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceCharacteristicsDictionary``
    (PDF 32000-1:2008 §12.5.6.19, Table 189).

    ``/BC`` / ``/BG`` are typed as :class:`PDColor` (upstream parity);
    a raw-``COSArray`` escape hatch is exposed via
    :meth:`get_border_colour_array` / :meth:`get_background_array` for
    low-level callers. ``/I`` / ``/RI`` / ``/IX`` keep the existing
    raw-``COSStream`` getters and add a ``_form`` typed companion.
    """

    # ---------- /TP (text/caption position) constants ----------
    #
    # PDF 32000-1 §12.5.6.19 Table 189: caption-icon relationship.

    TEXT_POSITION_CAPTION_ONLY: ClassVar[int] = 0
    TEXT_POSITION_NO_CAPTION: ClassVar[int] = 1
    TEXT_POSITION_CAPTION_BELOW: ClassVar[int] = 2
    TEXT_POSITION_CAPTION_ABOVE: ClassVar[int] = 3
    TEXT_POSITION_CAPTION_RIGHT: ClassVar[int] = 4
    TEXT_POSITION_CAPTION_LEFT: ClassVar[int] = 5
    TEXT_POSITION_CAPTION_OVERLAID: ClassVar[int] = 6

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

    # ---------- /BC (border colour, typed PDColor) ----------

    def get_border_colour(self) -> PDColor | None:
        """Typed ``/BC`` border colour. ``None`` when absent or when the
        component count is not 1/3/4 (DeviceGray/RGB/CMYK)."""
        return _read_color(self._dict, _BC)

    def get_border_colour_array(self) -> COSArray | None:
        """Raw ``/BC`` ``COSArray`` (low-level escape hatch)."""
        value = self._dict.get_dictionary_object(_BC)
        if isinstance(value, COSArray):
            return value
        return None

    def set_border_colour(self, c: PDColor | COSArray | None) -> None:
        if c is None:
            self._dict.remove_item(_BC)
            return
        self._dict.set_item(_BC, _color_to_cos_array(c))

    # ---------- /BG (background colour, typed PDColor) ----------

    def get_background(self) -> PDColor | None:
        """Typed ``/BG`` background colour. ``None`` when absent or when
        the component count is not 1/3/4 (DeviceGray/RGB/CMYK)."""
        return _read_color(self._dict, _BG)

    def get_background_array(self) -> COSArray | None:
        """Raw ``/BG`` ``COSArray`` (low-level escape hatch)."""
        value = self._dict.get_dictionary_object(_BG)
        if isinstance(value, COSArray):
            return value
        return None

    def set_background(self, c: PDColor | COSArray | None) -> None:
        if c is None:
            self._dict.remove_item(_BG)
            return
        self._dict.set_item(_BG, _color_to_cos_array(c))

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
        """Caption-vs-icon position code, default 0 (caption only).

        Values per PDF 32000-1:2008 Table 189:

        - 0 caption only (default)
        - 1 no caption, icon only
        - 2 caption below the icon
        - 3 caption above the icon
        - 4 caption to the right of the icon
        - 5 caption to the left of the icon
        - 6 caption overlaid directly on the icon
        """
        return self._dict.get_int(_TP, 0)

    def set_text_position(self, tp: int) -> None:
        self._dict.set_int(_TP, tp)


__all__ = ["PDAppearanceCharacteristicsDictionary"]
