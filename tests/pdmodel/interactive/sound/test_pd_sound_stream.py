from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.interactive.sound.pd_sound_stream import PDSoundStream

# ---------- construction ----------


def test_default_ctor_stamps_spec_defaults():
    sound = PDSoundStream()
    cos = sound.get_cos_object()
    assert isinstance(cos, COSStream)
    assert cos.get_int(COSName.get_pdf_name("B")) == 8
    assert cos.get_int(COSName.get_pdf_name("C")) == 1
    assert cos.get_name(COSName.get_pdf_name("E")) == "Raw"


def test_ctor_wraps_existing_cos_stream_without_defaults():
    raw = COSStream()
    raw.set_int(COSName.get_pdf_name("R"), 22050)
    sound = PDSoundStream(raw)
    # No defaults stamped onto an existing stream.
    assert sound.get_cos_object() is raw
    assert not raw.contains_key(COSName.get_pdf_name("B"))
    assert not raw.contains_key(COSName.get_pdf_name("C"))
    assert not raw.contains_key(COSName.get_pdf_name("E"))


def test_ctor_steals_underlying_stream_from_pd_stream():
    base = PDStream()
    base.get_cos_object().set_int(COSName.get_pdf_name("R"), 8000)
    sound = PDSoundStream(base)
    assert sound.get_cos_object() is base.get_cos_object()


def test_ctor_rejects_unknown_type():
    with pytest.raises(TypeError):
        PDSoundStream(42)  # type: ignore[arg-type]


# ---------- /R sampling rate ----------


def test_samples_per_second_round_trip_int_value():
    sound = PDSoundStream()
    assert sound.get_samples_per_second() == 0.0
    sound.set_samples_per_second(44100)
    assert sound.get_samples_per_second() == pytest.approx(44100.0)


def test_samples_per_second_accepts_float():
    sound = PDSoundStream()
    sound.set_samples_per_second(22050.5)
    assert sound.get_samples_per_second() == pytest.approx(22050.5)


# ---------- /C number of channels ----------


def test_channels_default_is_one():
    assert PDSoundStream().get_number_of_channels() == 1


def test_channels_round_trip():
    sound = PDSoundStream()
    sound.set_number_of_channels(2)
    assert sound.get_number_of_channels() == 2


# ---------- /B bits per sample ----------


def test_bits_per_sample_default_is_eight():
    assert PDSoundStream().get_bits_per_sample() == 8


def test_bits_per_sample_round_trip():
    sound = PDSoundStream()
    sound.set_bits_per_sample(16)
    assert sound.get_bits_per_sample() == 16


# ---------- /E encoding format ----------


def test_encoding_format_default_is_raw():
    assert PDSoundStream().get_encoding_format() == "Raw"


@pytest.mark.parametrize("name", ["Raw", "Signed", "muLaw", "ALaw", "Custom"])
def test_encoding_format_round_trip(name: str):
    sound = PDSoundStream()
    sound.set_encoding_format(name)
    assert sound.get_encoding_format() == name


def test_encoding_format_falls_back_to_raw_when_missing():
    # Wrap a bare stream so /E is genuinely absent.
    sound = PDSoundStream(COSStream())
    assert sound.get_encoding_format() == "Raw"


# ---------- /CO compression format ----------


def test_compression_format_absent_by_default():
    assert PDSoundStream().get_compression_format() is None


def test_compression_format_round_trip():
    sound = PDSoundStream()
    sound.set_compression_format("FLATE")
    assert sound.get_compression_format() == "FLATE"


def test_compression_format_clear_with_none():
    sound = PDSoundStream()
    sound.set_compression_format("FLATE")
    sound.set_compression_format(None)
    assert sound.get_compression_format() is None
    assert not sound.get_cos_object().contains_key(COSName.get_pdf_name("CO"))


# ---------- /CP compression parameters ----------


def test_compression_params_absent_by_default():
    assert PDSoundStream().get_compression_params() is None


def test_compression_params_round_trip_dict():
    sound = PDSoundStream()
    params = COSDictionary()
    params.set_int(COSName.get_pdf_name("Predictor"), 12)
    sound.set_compression_params(params)
    assert sound.get_compression_params() is params


def test_compression_params_round_trip_array():
    sound = PDSoundStream()
    arr = COSArray()
    arr.add(COSInteger.get(1))
    arr.add(COSInteger.get(2))
    sound.set_compression_params(arr)
    assert sound.get_compression_params() is arr


def test_compression_params_clear_with_none():
    sound = PDSoundStream()
    sound.set_compression_params(COSDictionary())
    sound.set_compression_params(None)
    assert sound.get_compression_params() is None
    assert not sound.get_cos_object().contains_key(COSName.get_pdf_name("CP"))


# ---------- raw sample data ----------


def test_get_raw_sample_data_empty_stream_returns_empty_bytes():
    sound = PDSoundStream()
    payload = sound.get_raw_sample_data().read()
    assert payload == b""


def test_get_raw_sample_data_returns_unfiltered_payload():
    cos = COSStream()
    cos.set_raw_data(b"\x01\x02\x03\x04")
    sound = PDSoundStream(cos)
    payload = sound.get_raw_sample_data().read()
    assert payload == b"\x01\x02\x03\x04"


# ---------- /E encoding constants ----------


def test_encoding_constants_match_iso_32000_table_174():
    assert PDSoundStream.ENCODING_RAW == "Raw"
    assert PDSoundStream.ENCODING_SIGNED == "Signed"
    assert PDSoundStream.ENCODING_MULAW == "muLaw"
    assert PDSoundStream.ENCODING_ALAW == "ALaw"


def test_encoding_constants_round_trip_through_setter():
    sound = PDSoundStream()
    sound.set_encoding_format(PDSoundStream.ENCODING_MULAW)
    assert sound.get_encoding_format() == "muLaw"
    sound.set_encoding_format(PDSoundStream.ENCODING_SIGNED)
    assert sound.get_encoding_format() == "Signed"


# ---------- /Type optional ----------


def test_type_constant_is_sound():
    assert PDSoundStream.TYPE_SOUND == "Sound"


def test_get_type_absent_by_default():
    assert PDSoundStream().get_type() is None


def test_type_round_trip_and_clear():
    sound = PDSoundStream()
    sound.set_type(PDSoundStream.TYPE_SOUND)
    assert sound.get_type() == "Sound"
    assert (
        sound.get_cos_object().get_name(COSName.get_pdf_name("Type")) == "Sound"
    )
    sound.set_type(None)
    assert sound.get_type() is None
    assert not sound.get_cos_object().contains_key(
        COSName.get_pdf_name("Type")
    )


# ---------- COS surface ----------


def test_get_cos_object_is_cos_stream():
    sound = PDSoundStream()
    assert isinstance(sound.get_cos_object(), COSStream)
