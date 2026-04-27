from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.interactive.sound.pd_sound_stream import PDSoundStream

from .pd_action import PDAction

_SOUND: COSName = COSName.get_pdf_name("Sound")
_VOLUME: COSName = COSName.get_pdf_name("Volume")
_SYNCHRONOUS: COSName = COSName.get_pdf_name("Synchronous")
_REPEAT: COSName = COSName.get_pdf_name("Repeat")
_MIX: COSName = COSName.get_pdf_name("Mix")


class PDActionSound(PDAction):
    """Sound action. Mirrors PDFBox ``PDActionSound``.

    The ``/Sound`` entry is exposed both as the raw ``COSBase``
    (:meth:`get_sound`/:meth:`set_sound` legacy back-compat surface, kept
    accepting raw COS) and as a typed :class:`PDSoundStream` via
    :meth:`get_sound`."""

    SUB_TYPE = "Sound"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_sound(self) -> PDSoundStream | None:
        """Return ``/Sound`` as a typed :class:`PDSoundStream`, or
        ``None`` when the entry is absent or not a stream."""
        entry = self._action.get_dictionary_object(_SOUND)
        if entry is None:
            return None
        if isinstance(entry, COSStream):
            return PDSoundStream(entry)
        return None

    def set_sound(self, sound: PDSoundStream | COSBase | None) -> None:
        """Replace ``/Sound``. Accepts ``None`` (removes the entry), a
        :class:`PDSoundStream` (stores its underlying COSStream), or a
        raw ``COSBase`` (stored as-is for back-compat)."""
        if sound is None:
            self._action.remove_item(_SOUND)
            return
        if isinstance(sound, PDSoundStream):
            self._action.set_item(_SOUND, sound.get_cos_object())
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
