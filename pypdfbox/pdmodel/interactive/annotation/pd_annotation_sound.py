from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSDictionary, COSName, COSStream

from .pd_annotation_markup import PDAnnotationMarkup

if TYPE_CHECKING:
    from pypdfbox.pdmodel.interactive.sound.pd_sound_stream import PDSoundStream
    from pypdfbox.pdmodel.pd_document import PDDocument

    from .handlers.pd_appearance_handler import PDAppearanceHandler

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
        self._custom_appearance_handler: PDAppearanceHandler | None = None
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- appearance construction ----------

    def set_custom_appearance_handler(
        self, appearance_handler: PDAppearanceHandler | None
    ) -> None:
        """Set the custom appearance handler used by
        :meth:`construct_appearances`.

        Mirrors upstream ``setCustomAppearanceHandler``. ``None`` clears the
        custom handler and restores the default construction path.
        """
        self._custom_appearance_handler = appearance_handler

    def construct_appearances(self, document: PDDocument | None = None) -> None:
        """Generate sound annotation appearances.

        A custom handler, when configured, is invoked exactly as upstream does.
        The built-in ``PDSoundAppearanceHandler`` is not ported yet, so the
        default path remains a no-op like the base annotation implementation.
        """
        if self._custom_appearance_handler is not None:
            self._custom_appearance_handler.generate_appearance_streams()
            return None
        return super().construct_appearances(document)

    # ---------- /Sound (sound stream, required) ----------

    def get_sound(self) -> COSStream | None:
        """Return the raw ``/Sound`` stream or ``None`` when absent.

        A typed :class:`PDSoundStream` wrapper is available — call sites
        that want it can do ``PDSoundStream(ann.get_sound())``."""
        value = self._dict.get_dictionary_object(_SOUND)
        if isinstance(value, COSStream):
            return value
        return None

    def set_sound(self, sound: COSStream | PDSoundStream | None) -> None:
        """Set the ``/Sound`` stream. Accepts a raw ``COSStream``,
        anything exposing ``get_cos_object()`` (e.g. ``PDSoundStream``),
        or ``None`` to clear."""
        if sound is None:
            self._dict.remove_item(_SOUND)
            return
        if isinstance(sound, COSStream):
            self._dict.set_item(_SOUND, sound)
            return
        if not hasattr(sound, "get_cos_object"):
            raise TypeError(
                f"set_sound expects None, COSStream, or PDSoundStream; got "
                f"{type(sound).__name__}"
            )
        cos = sound.get_cos_object()
        if not isinstance(cos, COSStream):
            raise TypeError("set_sound expects a COSStream-backed sound wrapper")
        self._dict.set_item(_SOUND, cos)

    def has_sound(self) -> bool:
        """Return ``True`` when ``/Sound`` resolves to a sound stream."""
        return isinstance(self._dict.get_dictionary_object(_SOUND), COSStream)

    def clear_sound(self) -> None:
        """Remove the ``/Sound`` entry."""
        self._dict.remove_item(_SOUND)

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

    def has_name(self) -> bool:
        """Return ``True`` when ``/Name`` is explicitly set as a name."""
        return self._dict.get_name(_NAME) is not None

    def clear_name(self) -> None:
        """Remove the explicit icon name, reverting to the ``Speaker`` default."""
        self._dict.remove_item(_NAME)

    def is_speaker_icon(self) -> bool:
        """Return ``True`` when the resolved icon name is ``Speaker``."""
        return self.get_name() == self.NAME_SPEAKER

    def is_mic_icon(self) -> bool:
        """Return ``True`` when the resolved icon name is ``Mic``."""
        return self.get_name() == self.NAME_MIC


__all__ = ["PDAnnotationSound"]
