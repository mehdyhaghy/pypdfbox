from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_sound import PDActionSound

_VOLUME: COSName = COSName.get_pdf_name("Volume")


def test_get_volume_clamps_above_range_returns_default() -> None:
    """Upstream parity: ``getVolume`` returns ``1.0`` when the stored value
    is outside ``[-1.0, 1.0]``. We bypass :meth:`set_volume` (which
    validates) to plant an out-of-range value directly."""
    action = PDActionSound()
    action.get_cos_object().set_float(_VOLUME, 1.5)
    assert action.get_volume() == 1.0


def test_get_volume_clamps_below_range_returns_default() -> None:
    action = PDActionSound()
    action.get_cos_object().set_float(_VOLUME, -2.0)
    assert action.get_volume() == 1.0


def test_get_volume_in_range_returned_as_is() -> None:
    action = PDActionSound()
    action.set_volume(0.25)
    assert action.get_volume() == pytest.approx(0.25)


def test_get_volume_at_boundaries_returned_as_is() -> None:
    """The upper / lower boundaries are inclusive."""
    action = PDActionSound()
    action.set_volume(1.0)
    assert action.get_volume() == 1.0
    action.set_volume(-1.0)
    assert action.get_volume() == -1.0


def test_set_volume_above_range_raises() -> None:
    action = PDActionSound()
    with pytest.raises(ValueError):
        action.set_volume(1.0001)


def test_set_volume_below_range_raises() -> None:
    action = PDActionSound()
    with pytest.raises(ValueError):
        action.set_volume(-1.0001)


def test_get_synchronous_upstream_alias() -> None:
    """Upstream-parity ``get_synchronous`` returns the same value as the
    pypdfbox-style ``is_synchronous``."""
    action = PDActionSound()
    assert action.get_synchronous() is False
    assert action.is_synchronous() is False

    action.set_synchronous(True)
    assert action.get_synchronous() is True
    assert action.is_synchronous() is True


def test_get_repeat_upstream_alias() -> None:
    action = PDActionSound()
    assert action.get_repeat() is False
    action.set_repeat(True)
    assert action.get_repeat() is True
    assert action.is_repeat() is True


def test_get_mix_upstream_alias() -> None:
    action = PDActionSound()
    assert action.get_mix() is False
    action.set_mix(True)
    assert action.get_mix() is True
    assert action.is_mix() is True


def test_default_volume_when_entry_absent() -> None:
    action = PDActionSound()
    assert action.get_volume() == 1.0


def test_round_trip_via_cos_dictionary() -> None:
    """Serializing a populated action to ``COSDictionary`` and rehydrating
    preserves all primitive entries."""
    action = PDActionSound()
    action.set_volume(-0.5)
    action.set_synchronous(True)
    action.set_repeat(True)
    action.set_mix(True)

    rehydrated = PDActionSound(action.get_cos_object())
    assert rehydrated.get_volume() == pytest.approx(-0.5)
    assert rehydrated.get_synchronous() is True
    assert rehydrated.get_repeat() is True
    assert rehydrated.get_mix() is True


def test_explicit_cos_construction_preserves_existing_values() -> None:
    cos = COSDictionary()
    cos.set_name(COSName.get_pdf_name("S"), "Sound")
    cos.set_float(_VOLUME, 0.8)

    action = PDActionSound(cos)
    assert action.get_volume() == pytest.approx(0.8)
