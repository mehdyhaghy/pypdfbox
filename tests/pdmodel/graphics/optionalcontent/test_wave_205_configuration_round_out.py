"""Wave 205 — extend :class:`PDOptionalContentConfiguration` with bulk
``/ON`` / ``/OFF`` setters, idempotent add / remove helpers, the
``is_intent`` predicate, and typed-enum :class:`BaseState` round-tripping.

These additions sit on the pypdfbox-original wrapper for the /D and
/Configs configuration dictionaries (PDF 32000-1 §8.11.4.3). Apache
PDFBox 3.0 inlines the corresponding /D accessors inside
``PDOptionalContentProperties`` and never exposes a /Configs surface,
so the gaps targeted here are pypdfbox enrichment rather than upstream
parity.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    BaseState,
    PDOptionalContentConfiguration,
    PDOptionalContentGroup,
)


# ----- /BaseState typed-enum overload -------------------------------------


def test_set_base_state_accepts_enum() -> None:
    cfg = PDOptionalContentConfiguration()
    cfg.set_base_state(BaseState.OFF)
    assert cfg.get_base_state() == "OFF"
    cfg.set_base_state(BaseState.UNCHANGED)
    assert cfg.get_base_state() == "Unchanged"
    cfg.set_base_state(BaseState.ON)
    assert cfg.get_base_state() == "ON"


def test_set_base_state_accepts_cos_name() -> None:
    cfg = PDOptionalContentConfiguration()
    cfg.set_base_state(COSName.get_pdf_name("OFF"))
    assert cfg.get_base_state() == "OFF"
    cfg.set_base_state(COSName.get_pdf_name("Unchanged"))
    assert cfg.get_base_state() == "Unchanged"


def test_set_base_state_rejects_unknown_cos_name() -> None:
    cfg = PDOptionalContentConfiguration()
    with pytest.raises(ValueError):
        cfg.set_base_state(COSName.get_pdf_name("Bogus"))


def test_set_base_state_rejects_non_string_non_enum() -> None:
    cfg = PDOptionalContentConfiguration()
    with pytest.raises(TypeError):
        cfg.set_base_state(42)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        cfg.set_base_state(None)  # type: ignore[arg-type]


def test_get_base_state_enum_default_and_roundtrip() -> None:
    cfg = PDOptionalContentConfiguration()
    # Spec default when /BaseState absent is ON.
    assert cfg.get_base_state_enum() is BaseState.ON
    cfg.set_base_state("OFF")
    assert cfg.get_base_state_enum() is BaseState.OFF
    cfg.set_base_state(BaseState.UNCHANGED)
    assert cfg.get_base_state_enum() is BaseState.UNCHANGED


# ----- /ON + /OFF bulk setters -------------------------------------------


def test_set_on_replaces_array() -> None:
    cfg = PDOptionalContentConfiguration()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    cfg.set_on([a, b])
    on_arr = cfg.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("ON")
    )
    assert isinstance(on_arr, COSArray)
    assert on_arr.size() == 2
    assert [g.get_name() for g in cfg.get_on()] == ["A", "B"]
    # Re-set replaces, doesn't append.
    cfg.set_on([a])
    assert [g.get_name() for g in cfg.get_on()] == ["A"]


def test_set_on_none_removes_key() -> None:
    cfg = PDOptionalContentConfiguration()
    cfg.set_on([PDOptionalContentGroup("A")])
    cfg.set_on(None)
    assert cfg.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("ON")
    ) is None
    assert cfg.get_on() == []


def test_set_on_rejects_non_ocg_entries() -> None:
    cfg = PDOptionalContentConfiguration()
    with pytest.raises(TypeError):
        cfg.set_on(["nope"])  # type: ignore[list-item]


def test_set_off_replaces_and_removes() -> None:
    cfg = PDOptionalContentConfiguration()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    cfg.set_off([a, b])
    assert [g.get_name() for g in cfg.get_off()] == ["A", "B"]
    cfg.set_off(None)
    assert cfg.get_off() == []


# ----- /ON + /OFF add / remove helpers -----------------------------------


def test_add_on_creates_array_and_is_idempotent() -> None:
    cfg = PDOptionalContentConfiguration()
    a = PDOptionalContentGroup("A")
    cfg.add_on(a)
    assert cfg.is_on(a) is True
    # Idempotent — second add does not duplicate.
    cfg.add_on(a)
    on_arr = cfg.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("ON")
    )
    assert isinstance(on_arr, COSArray)
    assert on_arr.size() == 1


def test_add_off_creates_array_and_is_idempotent() -> None:
    cfg = PDOptionalContentConfiguration()
    a = PDOptionalContentGroup("A")
    cfg.add_off(a)
    assert cfg.is_off(a) is True
    cfg.add_off(a)
    off_arr = cfg.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("OFF")
    )
    assert isinstance(off_arr, COSArray)
    assert off_arr.size() == 1


def test_remove_on_round_trip() -> None:
    cfg = PDOptionalContentConfiguration()
    a = PDOptionalContentGroup("A")
    b = PDOptionalContentGroup("B")
    cfg.set_on([a, b])
    assert cfg.remove_on(a) is True
    assert [g.get_name() for g in cfg.get_on()] == ["B"]
    # Idempotent: removing again returns False, no mutation.
    assert cfg.remove_on(a) is False
    # Group not present at all -> False.
    assert cfg.remove_on(PDOptionalContentGroup("Z")) is False
    # Drain the rest.
    assert cfg.remove_on(b) is True
    assert cfg.get_on() == []


def test_remove_off_when_key_absent() -> None:
    cfg = PDOptionalContentConfiguration()
    assert cfg.remove_off(PDOptionalContentGroup("A")) is False


def test_remove_on_matches_by_identity_not_name() -> None:
    """Two OCGs that share a /Name have distinct ``COSDictionary``
    instances; ``remove_on`` should remove only the listed one."""
    cfg = PDOptionalContentConfiguration()
    a = PDOptionalContentGroup("Same")
    twin = PDOptionalContentGroup("Same")  # same name, different dict
    cfg.set_on([a])
    # Removing the twin (different identity) must not match.
    assert cfg.remove_on(twin) is False
    assert cfg.is_on(a) is True


# ----- /Intent predicate --------------------------------------------------


def test_is_intent_default_view() -> None:
    """When /Intent is absent the spec default is ``"View"``."""
    cfg = PDOptionalContentConfiguration()
    assert cfg.is_intent("View") is True
    assert cfg.is_intent("Design") is False


def test_is_intent_single_name() -> None:
    cfg = PDOptionalContentConfiguration()
    cfg.set_intent("Design")
    assert cfg.is_intent("Design") is True
    assert cfg.is_intent("View") is False


def test_is_intent_array() -> None:
    cfg = PDOptionalContentConfiguration()
    cfg.set_intent(["View", "Design"])
    assert cfg.is_intent("View") is True
    assert cfg.is_intent("Design") is True
    assert cfg.is_intent("Other") is False


def test_is_intent_with_non_name_array_entries() -> None:
    """Non-COSName entries in /Intent are ignored, mirroring the lenient
    read shape of :meth:`get_intents`."""
    cfg = PDOptionalContentConfiguration()
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Design"))
    # Inject a non-COSName entry as if a malformed file referenced a
    # dictionary where a name should be.
    arr.add(COSDictionary())
    cfg.get_cos_object().set_item(COSName.get_pdf_name("Intent"), arr)
    assert cfg.is_intent("Design") is True
    assert cfg.is_intent("View") is False


def test_is_intent_with_unexpected_value_type() -> None:
    """If /Intent ever holds an unexpected COS type, ``is_intent`` is
    safe and returns ``False``."""
    cfg = PDOptionalContentConfiguration()
    cfg.get_cos_object().set_item(
        COSName.get_pdf_name("Intent"), COSDictionary()
    )
    assert cfg.is_intent("View") is False
    assert cfg.is_intent("Design") is False
