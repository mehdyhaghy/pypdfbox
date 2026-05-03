"""Wave 260 — round-out :class:`PDOptionalContentProperties` with the
small predicate / count helpers that bring its surface in line with
sister classes (e.g. :class:`PDOptionalContentMembershipDictionary`).

- :meth:`get_group_count` + :meth:`__len__` + :meth:`has_groups` —
  size and presence predicates over /OCGs that skip malformed
  (non-dictionary) entries to track :meth:`get_groups` rather than the
  raw array size.
- :meth:`is_base_state` — predicate counterpart to :meth:`set_base_state`,
  accepts strings (case-insensitive), :class:`BaseState` enum values, and
  :class:`COSName` instances; rejects unknown spellings with
  ``ValueError``.
- :meth:`is_intent` — predicate that delegates to the default
  configuration's intent test (honouring the spec ``"View"`` default when
  /Intent is absent).
- :meth:`has_configuration` — predicate for named entries in
  ``/OCProperties /Configs`` (parallels :meth:`has_group`).

These additions are pypdfbox enrichment — Apache PDFBox 3.0 leaves
callers to walk the underlying COSDictionary themselves.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_configuration import (  # noqa: E501
    PDOptionalContentConfiguration,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_properties import (  # noqa: E501
    BaseState,
    PDOptionalContentProperties,
)

_OCGS = COSName.get_pdf_name("OCGs")
_NAME = COSName.get_pdf_name("Name")
_D = COSName.D  # type: ignore[attr-defined]
_CONFIGS = COSName.get_pdf_name("Configs")


# ---------- get_group_count / __len__ / has_groups ------------------------


def test_get_group_count_zero_on_fresh_properties() -> None:
    props = PDOptionalContentProperties()
    assert props.get_group_count() == 0
    assert len(props) == 0
    assert props.has_groups() is False


def test_get_group_count_tracks_add_group() -> None:
    props = PDOptionalContentProperties()
    props.add_group(PDOptionalContentGroup("A"))
    assert props.get_group_count() == 1
    assert len(props) == 1
    assert props.has_groups() is True
    props.add_group(PDOptionalContentGroup("B"))
    props.add_group(PDOptionalContentGroup("C"))
    assert len(props) == 3


def test_get_group_count_decreases_after_remove() -> None:
    props = PDOptionalContentProperties()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    props.add_group(a)
    props.add_group(b)
    assert len(props) == 2
    assert props.remove_group(a) is True
    assert len(props) == 1
    assert props.remove_group(b) is True
    assert len(props) == 0
    assert props.has_groups() is False


def test_get_group_count_skips_non_dictionary_entries() -> None:
    """Non-dictionary garbage in /OCGs must not inflate the count —
    parallels :meth:`get_groups` which silently skips such entries."""
    props = PDOptionalContentProperties()
    props.add_group(PDOptionalContentGroup("Real"))
    raw = props.get_cos_object().get_dictionary_object(_OCGS)
    assert isinstance(raw, COSArray)
    raw.add(COSName.get_pdf_name("BogusName"))  # not a dict
    raw.add(COSName.get_pdf_name("AlsoBogus"))
    # Only the one real OCG counts.
    assert props.get_group_count() == 1
    assert props.has_groups() is True


def test_has_groups_false_when_only_non_dictionary_entries() -> None:
    props = PDOptionalContentProperties()
    raw = props.get_cos_object().get_dictionary_object(_OCGS)
    assert isinstance(raw, COSArray)
    raw.add(COSName.get_pdf_name("Bogus"))
    assert props.has_groups() is False
    assert props.get_group_count() == 0


def test_len_dunder_matches_get_group_count() -> None:
    """``len(props)`` is exactly :meth:`get_group_count` — invariant the
    docstring contract relies on."""
    props = PDOptionalContentProperties()
    for name in ("A", "B", "C", "D"):
        props.add_group(PDOptionalContentGroup(name))
    assert len(props) == props.get_group_count() == 4


# ---------- is_base_state -------------------------------------------------


def test_is_base_state_default_is_on() -> None:
    """Spec default for /BaseState is ``"ON"``."""
    props = PDOptionalContentProperties()
    assert props.is_base_state("ON") is True
    assert props.is_base_state("OFF") is False
    assert props.is_base_state("Unchanged") is False


def test_is_base_state_after_set_off() -> None:
    props = PDOptionalContentProperties()
    props.set_base_state("OFF")
    assert props.is_base_state("OFF") is True
    assert props.is_base_state("ON") is False


def test_is_base_state_accepts_enum_member() -> None:
    props = PDOptionalContentProperties()
    props.set_base_state(BaseState.UNCHANGED)
    assert props.is_base_state(BaseState.UNCHANGED) is True
    assert props.is_base_state(BaseState.ON) is False
    assert props.is_base_state(BaseState.OFF) is False


def test_is_base_state_accepts_cos_name() -> None:
    props = PDOptionalContentProperties()
    props.set_base_state("ON")
    assert props.is_base_state(COSName.get_pdf_name("ON")) is True
    assert props.is_base_state(COSName.get_pdf_name("OFF")) is False


def test_is_base_state_string_is_case_insensitive() -> None:
    props = PDOptionalContentProperties()
    props.set_base_state("OFF")
    assert props.is_base_state("off") is True
    assert props.is_base_state("oFf") is True
    assert props.is_base_state("On") is False


def test_is_base_state_unchanged_canonical_spelling() -> None:
    """Spec-defined value is ``"Unchanged"`` (mixed case); upper-case
    form must still resolve."""
    props = PDOptionalContentProperties()
    props.set_base_state(BaseState.UNCHANGED)
    assert props.is_base_state("Unchanged") is True
    assert props.is_base_state("UNCHANGED") is True


def test_is_base_state_unknown_string_raises() -> None:
    props = PDOptionalContentProperties()
    with pytest.raises(ValueError):
        props.is_base_state("Bogus")


# ---------- is_intent (delegated) -----------------------------------------


def test_is_intent_default_view_when_absent() -> None:
    """Per PDF 32000-1 §8.11.4.3 Table 101 the spec default for /Intent
    is ``"View"`` — :meth:`is_intent` must honour that default for an
    unset /Intent."""
    props = PDOptionalContentProperties()
    assert props.is_intent("View") is True
    assert props.is_intent("Design") is False


def test_is_intent_round_trips_set() -> None:
    props = PDOptionalContentProperties()
    props.set_intent("Design")
    assert props.is_intent("Design") is True
    # The string-set form replaces the default — "View" no longer
    # matches because /Intent now contains a single name "Design".
    assert props.is_intent("View") is False


def test_is_intent_array_form() -> None:
    props = PDOptionalContentProperties()
    props.set_intent(["View", "Design"])
    assert props.is_intent("View") is True
    assert props.is_intent("Design") is True
    assert props.is_intent("Other") is False


# ---------- has_configuration ---------------------------------------------


def test_has_configuration_returns_false_when_configs_missing() -> None:
    props = PDOptionalContentProperties()
    assert props.has_configuration("Anything") is False


def test_has_configuration_after_add() -> None:
    props = PDOptionalContentProperties()
    cfg = PDOptionalContentConfiguration()
    cfg.set_name("Print")
    props.add_configuration(cfg)
    assert props.has_configuration("Print") is True
    assert props.has_configuration("Display") is False


def test_has_configuration_distinguishes_multiple_entries() -> None:
    props = PDOptionalContentProperties()
    for cfg_name in ("Print", "Web", "Archive"):
        cfg = PDOptionalContentConfiguration()
        cfg.set_name(cfg_name)
        props.add_configuration(cfg)
    assert props.has_configuration("Web") is True
    assert props.has_configuration("Archive") is True
    assert props.has_configuration("Missing") is False


def test_has_configuration_returns_false_for_unnamed_entry() -> None:
    """An entry with no /Name doesn't satisfy any name lookup."""
    props = PDOptionalContentProperties()
    cfg = PDOptionalContentConfiguration()  # no /Name set
    props.add_configuration(cfg)
    assert props.has_configuration("") is False
    assert props.has_configuration("anything") is False


def test_has_configuration_skips_non_dict_entries() -> None:
    """Malformed /Configs (non-dict slot) must not crash the lookup."""
    props = PDOptionalContentProperties()
    cfg = PDOptionalContentConfiguration()
    cfg.set_name("Real")
    props.add_configuration(cfg)
    configs = props.get_cos_object().get_dictionary_object(_CONFIGS)
    assert isinstance(configs, COSArray)
    configs.add(COSName.get_pdf_name("Bogus"))  # not a dict
    assert props.has_configuration("Real") is True
    assert props.has_configuration("Bogus") is False


# ---------- cross-cutting -------------------------------------------------


def test_round_trip_add_remove_and_has() -> None:
    """Cross-check: counts and the predicate stay coherent across adds
    and removes."""
    props = PDOptionalContentProperties()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    assert not props.has_groups()
    props.add_group(a)
    props.add_group(b)
    assert len(props) == 2
    assert props.has_groups() is True
    props.remove_group(a)
    assert len(props) == 1
    assert props.has_groups() is True
    props.remove_group(b)
    assert len(props) == 0
    assert props.has_groups() is False


def test_is_base_state_consistent_with_get_base_state_enum() -> None:
    """``is_base_state(get_base_state_enum())`` must always be ``True``."""
    props = PDOptionalContentProperties()
    for state in (BaseState.ON, BaseState.OFF, BaseState.UNCHANGED):
        props.set_base_state(state)
        assert props.is_base_state(props.get_base_state_enum()) is True
