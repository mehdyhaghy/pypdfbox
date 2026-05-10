from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.interactive.action.pd_action_sound import PDActionSound
from pypdfbox.pdmodel.interactive.sound.pd_sound_stream import PDSoundStream

_SOUND: COSName = COSName.get_pdf_name("Sound")


def test_default_values_when_wrapping_empty_cos_stream() -> None:
    """Wrapping a bare ``COSStream`` (no /B, /E, /C entries) reports the
    spec-defined defaults: ``B=8``, ``E="Raw"``, ``C=1``. ``/CO`` and
    ``/CP`` are absent."""
    sound = PDSoundStream(COSStream())
    assert sound.get_bits_per_sample() == 8
    assert sound.get_encoding_format() == "Raw"
    assert sound.get_number_of_channels() == 1
    assert sound.get_compression_format() is None
    assert sound.get_compression_params() is None


def test_no_arg_constructor_stamps_spec_defaults() -> None:
    """``PDSoundStream()`` with no arg materialises the defaults into the
    underlying COSStream so the dictionary serialises with ``/B``, ``/E``,
    ``/C`` set."""
    sound = PDSoundStream()
    cos = sound.get_cos_object()
    assert cos.get_int(COSName.get_pdf_name("B")) == 8
    assert cos.get_name(COSName.get_pdf_name("E")) == "Raw"
    assert cos.get_int(COSName.get_pdf_name("C")) == 1


def test_round_trips_every_accessor() -> None:
    sound = PDSoundStream()
    sound.set_samples_per_second(44100.0)
    sound.set_number_of_channels(2)
    sound.set_bits_per_sample(16)
    sound.set_encoding_format("Signed")
    sound.set_compression_format("muLaw")
    params = COSDictionary()
    params.set_int(COSName.get_pdf_name("Quality"), 5)
    sound.set_compression_params(params)

    assert sound.get_samples_per_second() == 44100.0
    assert sound.get_number_of_channels() == 2
    assert sound.get_bits_per_sample() == 16
    assert sound.get_encoding_format() == "Signed"
    assert sound.get_compression_format() == "muLaw"
    assert sound.get_compression_params() is params

    # Setting compression entries to None removes them.
    sound.set_compression_format(None)
    sound.set_compression_params(None)
    assert sound.get_compression_format() is None
    assert sound.get_compression_params() is None


def test_action_sound_get_sound_returns_typed_wrapper() -> None:
    """``PDActionSound.get_sound()`` returns a :class:`PDSoundStream`
    wrapping the indirect ``/Sound`` COSStream entry."""
    action = PDActionSound()
    body = COSStream()
    body.set_int(COSName.get_pdf_name("R"), 22050)
    action.set_sound(body)

    resolved = action.get_sound()
    assert isinstance(resolved, PDSoundStream)
    assert resolved.get_cos_object() is body
    # Read-through into the wrapper accessor.
    assert resolved.get_samples_per_second() == 22050.0


def test_action_sound_set_sound_none_removes_entry() -> None:
    action = PDActionSound()
    action.set_sound(COSStream())
    assert action.get_cos_object().get_dictionary_object(_SOUND) is not None

    action.set_sound(None)
    assert action.get_cos_object().get_dictionary_object(_SOUND) is None
    assert action.get_sound() is None


def test_action_sound_set_sound_accepts_pd_sound_stream() -> None:
    """Passing a typed :class:`PDSoundStream` stores its underlying
    ``COSStream`` rather than wrapping the wrapper."""
    action = PDActionSound()
    sound = PDSoundStream()
    sound.set_samples_per_second(8000.0)
    action.set_sound(sound)

    stored = action.get_cos_object().get_dictionary_object(_SOUND)
    assert stored is sound.get_cos_object()


def test_constructor_accepts_pd_stream_and_steals_cos_stream() -> None:
    """``PDSoundStream(PDStream)`` reuses the underlying ``COSStream`` so
    edits flow through to the original."""
    base = PDStream()
    sound = PDSoundStream(base)
    assert sound.get_cos_object() is base.get_cos_object()
    sound.set_bits_per_sample(24)
    assert base.get_cos_object().get_int(COSName.get_pdf_name("B")) == 24
