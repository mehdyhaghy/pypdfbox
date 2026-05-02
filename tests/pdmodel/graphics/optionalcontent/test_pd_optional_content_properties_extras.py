"""Small upstream-parity additions for ``PDOptionalContentProperties``.

Covers:

- ``BaseState.get_name()`` — Java-spelled alias for :meth:`get_pdf_name`,
  returning the ``COSName`` for the state. Mirrors upstream
  ``PDOptionalContentProperties.BaseState.getName()``.
- ``is_group_enabled(None)`` — null-safety per upstream
  ``isGroupEnabled((PDOptionalContentGroup) null)``: returns the
  BaseState-derived flag without consulting /D /ON or /D /OFF.
- ``set_base_state(COSName)`` — accept the same ``COSName`` shape that
  :meth:`BaseState.value_of` already takes, for write-side symmetry.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (
    BaseState,
    PDOptionalContentProperties,
)


# ---------- BaseState.get_name() ----------


def test_base_state_get_name_returns_cos_name() -> None:
    assert BaseState.ON.get_name() == COSName.get_pdf_name("ON")
    assert BaseState.OFF.get_name() == COSName.get_pdf_name("OFF")
    assert BaseState.UNCHANGED.get_name() == COSName.get_pdf_name("Unchanged")


def test_base_state_get_name_matches_get_pdf_name() -> None:
    for member in BaseState:
        assert member.get_name() is member.get_pdf_name()


# ---------- is_group_enabled(None) ----------


def test_is_group_enabled_none_default_base_state_is_true() -> None:
    # Default base state is ON, so a null group resolves to enabled=True.
    props = PDOptionalContentProperties()
    assert props.is_group_enabled(None) is True


def test_is_group_enabled_none_with_off_base_state_is_false() -> None:
    props = PDOptionalContentProperties()
    props.set_base_state(BaseState.OFF)
    assert props.is_group_enabled(None) is False


def test_is_group_enabled_none_with_unchanged_base_state_is_true() -> None:
    # Upstream: enabled = baseState != OFF, so Unchanged -> True.
    props = PDOptionalContentProperties()
    props.set_base_state(BaseState.UNCHANGED)
    assert props.is_group_enabled(None) is True


# ---------- set_base_state(COSName) ----------


def test_set_base_state_accepts_cos_name() -> None:
    props = PDOptionalContentProperties()
    props.set_base_state(COSName.get_pdf_name("OFF"))
    assert props.get_base_state() == "OFF"
    assert props.get_base_state_enum() is BaseState.OFF


def test_set_base_state_cos_name_unchanged_round_trip() -> None:
    props = PDOptionalContentProperties()
    props.set_base_state(COSName.get_pdf_name("Unchanged"))
    assert props.get_base_state() == "Unchanged"
    assert props.get_base_state_enum() is BaseState.UNCHANGED


def test_set_base_state_cos_name_unknown_raises() -> None:
    props = PDOptionalContentProperties()
    with pytest.raises(ValueError):
        props.set_base_state(COSName.get_pdf_name("Bogus"))
