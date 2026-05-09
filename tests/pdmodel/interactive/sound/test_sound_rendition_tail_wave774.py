from __future__ import annotations

import pytest

from pypdfbox.cos import COSName, COSObject
from pypdfbox.pdmodel.interactive.measurement.pd_rendition import PDRendition
from pypdfbox.pdmodel.interactive.sound.pd_sound_stream import PDSoundStream

_B = COSName.get_pdf_name("B")
_C = COSName.get_pdf_name("C")


def test_sound_stream_channel_and_bit_depth_clearers_restore_defaults() -> None:
    sound = PDSoundStream()
    sound.set_number_of_channels(2)
    sound.set_bits_per_sample(16)
    assert sound.has_number_of_channels() is True
    assert sound.has_bits_per_sample() is True

    sound.clear_number_of_channels()
    sound.clear_bits_per_sample()

    cos = sound.get_cos_object()
    assert not cos.contains_key(_C)
    assert not cos.contains_key(_B)
    assert sound.has_number_of_channels() is False
    assert sound.has_bits_per_sample() is False
    assert sound.get_number_of_channels() == 1
    assert sound.get_bits_per_sample() == 8


def test_rendition_create_returns_none_for_cyclic_indirect_object() -> None:
    indirect = COSObject(1)
    indirect.set_object(indirect)

    assert PDRendition.create(indirect) is None


def test_rendition_create_rejects_non_dictionary_cos_base() -> None:
    with pytest.raises(TypeError, match="COSDictionary"):
        PDRendition.create(COSName.get_pdf_name("NotADictionary"))
