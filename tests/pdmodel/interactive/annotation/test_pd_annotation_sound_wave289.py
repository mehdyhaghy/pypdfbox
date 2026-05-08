from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_sound import (
    PDAnnotationSound,
)
from pypdfbox.pdmodel.interactive.sound.pd_sound_stream import PDSoundStream


def test_sound_presence_helpers_require_cos_stream_wave289() -> None:
    ann = PDAnnotationSound()

    assert ann.has_sound() is False

    stream = COSStream()
    ann.set_sound(stream)
    assert ann.has_sound() is True
    assert ann.get_sound() is stream

    ann.clear_sound()
    assert ann.has_sound() is False
    assert ann.get_sound() is None


def test_sound_presence_helpers_reject_malformed_sound_entry_wave289() -> None:
    ann = PDAnnotationSound()
    ann.get_cos_object().set_item(
        COSName.get_pdf_name("Sound"), COSName.get_pdf_name("NotAStream")
    )

    assert ann.get_sound() is None
    assert ann.has_sound() is False


def test_set_sound_accepts_typed_sound_stream_wave289() -> None:
    ann = PDAnnotationSound()
    sound = PDSoundStream()

    ann.set_sound(sound)

    assert ann.has_sound() is True
    assert ann.get_sound() is sound.get_cos_object()


def test_sound_icon_helpers_follow_typed_name_presence_wave289() -> None:
    ann = PDAnnotationSound()

    assert ann.get_name() == PDAnnotationSound.NAME_SPEAKER
    assert ann.has_name() is False
    assert ann.is_speaker_icon() is True
    assert ann.is_mic_icon() is False

    ann.set_name(PDAnnotationSound.NAME_MIC)
    assert ann.has_name() is True
    assert ann.is_speaker_icon() is False
    assert ann.is_mic_icon() is True

    ann.clear_name()
    assert ann.has_name() is False
    assert ann.get_name() == PDAnnotationSound.NAME_SPEAKER


def test_malformed_sound_icon_name_uses_default_without_presence_wave289() -> None:
    ann = PDAnnotationSound(COSDictionary())
    ann.get_cos_object().set_item(COSName.get_pdf_name("Name"), COSInteger.get(1))

    assert ann.get_name() == PDAnnotationSound.NAME_SPEAKER
    assert ann.has_name() is False
    assert ann.is_speaker_icon() is True
