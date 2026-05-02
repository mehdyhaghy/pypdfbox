from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

_START: COSName = COSName.get_pdf_name("Start")
_DURATION: COSName = COSName.get_pdf_name("Duration")
_RATE: COSName = COSName.get_pdf_name("Rate")
_VOLUME: COSName = COSName.get_pdf_name("Volume")
_SHOW_CONTROLS: COSName = COSName.get_pdf_name("ShowControls")
_MODE: COSName = COSName.get_pdf_name("Mode")


class PDMovieActivation:
    """Movie activation dictionary wrapper for annotation ``/A`` entries."""

    # ---------- /Mode value constants (ISO 32000-1 Table 273) ----------

    MODE_ONCE: str = "Once"
    MODE_OPEN: str = "Open"
    MODE_REPEAT: str = "Repeat"
    MODE_PALINDROME: str = "Palindrome"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    def get_start(self) -> COSBase | None:
        return self._dict.get_dictionary_object(_START)

    def set_start(self, start: COSBase | None) -> None:
        if start is None:
            self._dict.remove_item(_START)
            return
        self._dict.set_item(_START, start)

    def get_duration(self) -> COSBase | None:
        return self._dict.get_dictionary_object(_DURATION)

    def set_duration(self, duration: COSBase | None) -> None:
        if duration is None:
            self._dict.remove_item(_DURATION)
            return
        self._dict.set_item(_DURATION, duration)

    def get_rate(self) -> float:
        return self._dict.get_float(_RATE, 1.0)

    def set_rate(self, rate: float | None) -> None:
        if rate is None:
            self._dict.remove_item(_RATE)
            return
        self._dict.set_float(_RATE, rate)

    def get_volume(self) -> float:
        return self._dict.get_float(_VOLUME, 1.0)

    def set_volume(self, volume: float | None) -> None:
        if volume is None:
            self._dict.remove_item(_VOLUME)
            return
        self._dict.set_float(_VOLUME, volume)

    def show_controls(self) -> bool:
        return self._dict.get_boolean(_SHOW_CONTROLS, False)

    def set_show_controls(self, show_controls: bool | None) -> None:
        if show_controls is None:
            self._dict.remove_item(_SHOW_CONTROLS)
            return
        self._dict.set_boolean(_SHOW_CONTROLS, show_controls)

    def get_mode(self) -> str | None:
        return self._dict.get_name(_MODE)

    def set_mode(self, mode: str | None) -> None:
        if mode is None:
            self._dict.remove_item(_MODE)
            return
        self._dict.set_name(_MODE, mode)


__all__ = ["PDMovieActivation"]
