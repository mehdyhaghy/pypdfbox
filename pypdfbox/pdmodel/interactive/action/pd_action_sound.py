from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName

from .pd_action import PDAction

_SOUND: COSName = COSName.get_pdf_name("Sound")
_VOLUME: COSName = COSName.get_pdf_name("Volume")
_SYNCHRONOUS: COSName = COSName.get_pdf_name("Synchronous")
_REPEAT: COSName = COSName.get_pdf_name("Repeat")
_MIX: COSName = COSName.get_pdf_name("Mix")


class PDActionSound(PDAction):
    """Sound action. Mirrors PDFBox ``PDActionSound`` lite surface.

    The ``/Sound`` entry is exposed as a raw ``COSBase`` for now; a typed
    ``PDSoundStream`` wrapper is deferred."""

    SUB_TYPE = "Sound"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_sound(self) -> COSBase | None:
        return self._action.get_dictionary_object(_SOUND)

    def set_sound(self, sound: COSBase | None) -> None:
        if sound is None:
            self._action.remove_item(_SOUND)
            return
        self._action.set_item(_SOUND, sound)

    def get_volume(self) -> float:
        return self._action.get_float(_VOLUME, 1.0)

    def set_volume(self, volume: float) -> None:
        self._action.set_float(_VOLUME, volume)

    def is_synchronous(self) -> bool:
        return self._action.get_boolean(_SYNCHRONOUS, False)

    def set_synchronous(self, synchronous: bool) -> None:
        self._action.set_boolean(_SYNCHRONOUS, synchronous)

    def is_repeat(self) -> bool:
        return self._action.get_boolean(_REPEAT, False)

    def set_repeat(self, repeat: bool) -> None:
        self._action.set_boolean(_REPEAT, repeat)

    def is_mix(self) -> bool:
        return self._action.get_boolean(_MIX, False)

    def set_mix(self, mix: bool) -> None:
        self._action.set_boolean(_MIX, mix)


__all__ = ["PDActionSound"]
