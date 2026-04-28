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
        """Return ``/Volume`` (default ``1.0``). PDF 32000-1 §12.6.4.13
        Table 207 constrains ``/Volume`` to ``[-1.0, 1.0]``; values outside
        that range are read as ``1.0`` (the default), mirroring upstream
        ``PDActionSound.getVolume`` clamp behavior."""
        volume = self._action.get_float(_VOLUME, 1.0)
        if volume < -1.0 or volume > 1.0:
            return 1.0
        return volume

    def set_volume(self, volume: float) -> None:
        """Set ``/Volume``. Raises :class:`ValueError` when ``volume`` is
        outside ``[-1.0, 1.0]``. Mirrors upstream
        ``PDActionSound.setVolume`` (``IllegalArgumentException`` →
        :class:`ValueError`)."""
        if volume < -1.0 or volume > 1.0:
            raise ValueError("volume outside of the range -1.0 to 1.0")
        self._action.set_float(_VOLUME, volume)

    # ---------- /Synchronous ----------

    def get_synchronous(self) -> bool:
        """Return ``/Synchronous`` (default ``False``). Upstream
        ``PDActionSound.getSynchronous`` parity name."""
        return self._action.get_boolean(_SYNCHRONOUS, False)

    def is_synchronous(self) -> bool:
        """pypdfbox-style alias of :meth:`get_synchronous`."""
        return self.get_synchronous()

    def set_synchronous(self, synchronous: bool) -> None:
        self._action.set_boolean(_SYNCHRONOUS, synchronous)

    # ---------- /Repeat ----------

    def get_repeat(self) -> bool:
        """Return ``/Repeat`` (default ``False``). Upstream
        ``PDActionSound.getRepeat`` parity name."""
        return self._action.get_boolean(_REPEAT, False)

    def is_repeat(self) -> bool:
        """pypdfbox-style alias of :meth:`get_repeat`."""
        return self.get_repeat()

    def set_repeat(self, repeat: bool) -> None:
        self._action.set_boolean(_REPEAT, repeat)

    # ---------- /Mix ----------

    def get_mix(self) -> bool:
        """Return ``/Mix`` (default ``False``). Upstream
        ``PDActionSound.getMix`` parity name."""
        return self._action.get_boolean(_MIX, False)

    def is_mix(self) -> bool:
        """pypdfbox-style alias of :meth:`get_mix`."""
        return self.get_mix()

    def set_mix(self, mix: bool) -> None:
        self._action.set_boolean(_MIX, mix)


__all__ = ["PDActionSound"]
