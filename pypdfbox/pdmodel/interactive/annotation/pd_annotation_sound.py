from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream

from .pd_annotation_markup import PDAnnotationMarkup

_SOUND: COSName = COSName.get_pdf_name("Sound")
_NAME: COSName = COSName.get_pdf_name("Name")


class PDAnnotationSound(PDAnnotationMarkup):
    """
    Sound annotation — ``/Subtype /Sound``. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSound``.

    A sound annotation is analogous to a text annotation except that it
    plays back a sound from an embedded sound stream rather than displaying
    a text note (PDF 32000-1:2008 §12.5.6.16). Required entries:

    * ``/Sound`` — sound stream (``COSStream``); see
      :class:`pypdfbox.pdmodel.interactive.sound.pd_sound_stream.PDSoundStream`.
    * ``/Name`` — icon used to render the annotation. Spec default
      ``Speaker``; ``Mic`` is the only other named value, viewers may
      support custom names.

    Extends :class:`PDAnnotationMarkup` so review-workflow metadata
    (``/CreationDate``, ``/Subj``, ``/IRT``, ``/CA``, …) come for free.
    """

    SUB_TYPE: str = "Sound"

    # Icon name constants — spec default is ``Speaker``.
    NAME_SPEAKER: str = "Speaker"
    NAME_MIC: str = "Mic"

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /Sound (sound stream, required) ----------

    def get_sound(self) -> COSStream | None:
        """Return the raw ``/Sound`` stream or ``None`` when absent.

        A typed :class:`PDSoundStream` wrapper is available — call sites
        that want it can do ``PDSoundStream(ann.get_sound())``."""
        value = self._dict.get_dictionary_object(_SOUND)
        if isinstance(value, COSStream):
            return value
        return None

    def set_sound(self, sound: COSStream | None) -> None:
        """Set the ``/Sound`` stream. Accepts a raw ``COSStream``,
        anything exposing ``get_cos_object()`` (e.g. ``PDSoundStream``),
        or ``None`` to clear."""
        if sound is None:
            self._dict.remove_item(_SOUND)
            return
        if isinstance(sound, COSStream):
            self._dict.set_item(_SOUND, sound)
            return
        if hasattr(sound, "get_cos_object"):
            cos = sound.get_cos_object()
            if not isinstance(cos, COSStream):
                raise TypeError(
                    "set_sound expects a COSStream-backed sound wrapper"
                )
            self._dict.set_item(_SOUND, cos)
            return
        raise TypeError(
            f"set_sound expects None, COSStream, or PDSoundStream; got "
            f"{type(sound).__name__}"
        )

    # ---------- /Name (icon) ----------

    def get_name(self) -> str:
        """Icon name. Default per spec is ``Speaker``."""
        value = self._dict.get_name(_NAME)
        return value if value is not None else self.NAME_SPEAKER

    def set_name(self, name: str | None) -> None:
        if name is None:
            self._dict.remove_item(_NAME)
            return
        self._dict.set_name(_NAME, name)


__all__ = ["PDAnnotationSound"]
