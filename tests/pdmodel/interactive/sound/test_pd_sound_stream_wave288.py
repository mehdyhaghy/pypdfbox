from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSNull, COSStream, COSString
from pypdfbox.pdmodel.interactive.sound.pd_sound_stream import PDSoundStream

_B = COSName.get_pdf_name("B")
_C = COSName.get_pdf_name("C")
_CO = COSName.get_pdf_name("CO")
_CP = COSName.get_pdf_name("CP")
_E = COSName.get_pdf_name("E")
_R = COSName.get_pdf_name("R")
_TYPE = COSName.get_pdf_name("Type")


def test_default_sound_entries_report_typed_presence() -> None:
    sound = PDSoundStream()

    assert sound.has_bits_per_sample() is True
    assert sound.has_number_of_channels() is True
    assert sound.has_encoding_format() is True
    assert sound.has_samples_per_second() is False
    assert sound.has_compression_format() is False
    assert sound.has_compression_params() is False
    assert sound.has_type() is False


def test_typed_presence_helpers_ignore_malformed_sound_entries() -> None:
    raw = COSStream()
    raw.set_item(_R, COSName.get_pdf_name("bad"))
    raw.set_item(_C, COSString("2"))
    raw.set_item(_B, COSArray())
    raw.set_item(_E, COSString("Signed"))
    raw.set_item(_CO, COSString("FlateDecode"))
    raw.set_item(_CP, COSNull.NULL)
    raw.set_item(_TYPE, COSString("Sound"))

    sound = PDSoundStream(raw)

    assert sound.get_samples_per_second() == 0.0
    assert sound.get_number_of_channels() == 1
    assert sound.get_bits_per_sample() == 8
    assert sound.get_encoding_format() == "Raw"
    assert sound.get_compression_format() is None
    assert sound.get_compression_params() is None
    assert sound.get_type() is None

    assert sound.has_samples_per_second() is False
    assert sound.has_number_of_channels() is False
    assert sound.has_bits_per_sample() is False
    assert sound.has_encoding_format() is False
    assert sound.has_compression_format() is False
    assert sound.has_compression_params() is False
    assert sound.has_type() is False


def test_clear_helpers_remove_sound_entries() -> None:
    sound = PDSoundStream()
    sound.set_samples_per_second(44100.0)
    sound.set_compression_format("FlateDecode")
    sound.set_compression_params(COSDictionary())
    sound.set_type(PDSoundStream.TYPE_SOUND)

    sound.clear_samples_per_second()
    sound.clear_encoding_format()
    sound.clear_compression_format()
    sound.clear_compression_params()
    sound.clear_type()

    cos = sound.get_cos_object()
    assert not cos.contains_key(_R)
    assert not cos.contains_key(_E)
    assert not cos.contains_key(_CO)
    assert not cos.contains_key(_CP)
    assert not cos.contains_key(_TYPE)
    assert sound.get_samples_per_second() == 0.0
    assert sound.get_encoding_format() == "Raw"
