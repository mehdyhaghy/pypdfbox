"""Wave 269 — pdmodel/interactive/action/PDActionSound parity gaps.

Covers the predicate / clear-helper surface (``has_sound``,
``clear_sound``, ``is_empty``, ``is_valid``) added to mirror the
established convention used by :class:`PDActionTransition`,
:class:`PDActionEmbeddedGoTo`, and friends.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.interactive.action.pd_action_sound import PDActionSound
from pypdfbox.pdmodel.interactive.sound.pd_sound_stream import PDSoundStream

_SOUND: COSName = COSName.get_pdf_name("Sound")
_S: COSName = COSName.get_pdf_name("S")


def test_has_sound_default_false_wave269() -> None:
    """A freshly-constructed action has no ``/Sound`` entry."""
    action = PDActionSound()
    assert action.has_sound() is False


def test_has_sound_true_after_set_wave269() -> None:
    action = PDActionSound()
    sound = PDSoundStream()
    action.set_sound(sound)
    assert action.has_sound() is True


def test_has_sound_false_for_non_stream_entry_wave269() -> None:
    """``/Sound`` must be a stream — a non-stream entry is rejected.

    PDF 32000-1 Table 207 specifies ``/Sound`` as a sound stream.
    Mirrors upstream ``getCOSStream`` semantics.
    """
    action = PDActionSound()
    # Plant a non-stream value directly.
    action.get_cos_object().set_item(_SOUND, COSDictionary())
    assert action.has_sound() is False


def test_clear_sound_removes_entry_wave269() -> None:
    action = PDActionSound()
    sound = PDSoundStream()
    action.set_sound(sound)
    assert action.has_sound() is True

    action.clear_sound()
    assert action.has_sound() is False
    assert action.get_sound() is None
    assert action.get_cos_object().get_dictionary_object(_SOUND) is None


def test_clear_sound_when_absent_is_noop_wave269() -> None:
    action = PDActionSound()
    action.clear_sound()  # should not raise
    assert action.has_sound() is False


def test_is_empty_when_no_sound_wave269() -> None:
    action = PDActionSound()
    assert action.is_empty() is True


def test_is_empty_false_after_set_sound_wave269() -> None:
    action = PDActionSound()
    action.set_sound(PDSoundStream())
    assert action.is_empty() is False


def test_is_empty_keyed_on_sound_only_wave269() -> None:
    """Volume / Synchronous / Repeat / Mix don't lift emptiness — only
    the presence of a ``/Sound`` stream does."""
    action = PDActionSound()
    action.set_volume(0.5)
    action.set_synchronous(True)
    action.set_repeat(True)
    action.set_mix(True)
    assert action.is_empty() is True


def test_is_valid_default_constructor_wave269() -> None:
    action = PDActionSound()
    assert action.is_valid() is True
    assert action.get_sub_type() == "Sound"


def test_is_valid_false_for_wrong_subtype_wave269() -> None:
    """Wrap a hand-built dict whose ``/S`` is something else."""
    cos = COSDictionary()
    cos.set_name(_S, "Wrong")
    action = PDActionSound(cos)
    assert action.is_valid() is False


def test_set_sound_then_clear_round_trip_wave269() -> None:
    action = PDActionSound()
    stream = COSStream()
    action.set_sound(stream)
    assert action.has_sound() is True
    assert action.is_empty() is False
    assert action.is_valid() is True

    action.clear_sound()
    assert action.has_sound() is False
    assert action.is_empty() is True
    assert action.is_valid() is True
