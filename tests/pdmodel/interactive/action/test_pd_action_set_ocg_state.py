from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)
from pypdfbox.pdmodel.interactive.action import (
    PDAction,
    PDActionSetOCGState,
)


def _ocg_dict(name: str) -> COSDictionary:
    """Build a minimal /Type /OCG dictionary for round-trip testing."""
    return PDOptionalContentGroup(name).get_cos_object()


def test_default_constructor_sets_subtype_and_type() -> None:
    action = PDActionSetOCGState()
    assert action.get_sub_type() == "SetOCGState"
    cos = action.get_cos_object()
    assert cos.get_name(COSName.get_pdf_name("Type")) == "Action"
    assert cos.get_name(COSName.get_pdf_name("S")) == "SetOCGState"


def test_factory_dispatch_returns_set_ocg_state() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("S"), "SetOCGState")
    action = PDAction.create(raw)
    assert isinstance(action, PDActionSetOCGState)
    assert action.get_cos_object() is raw


def test_state_round_trip_with_cos_array() -> None:
    on = COSName.get_pdf_name("ON")
    off = COSName.get_pdf_name("OFF")
    ocg_a = _ocg_dict("A")
    ocg_b = _ocg_dict("B")
    arr = COSArray([on, ocg_a, off, ocg_b])

    action = PDActionSetOCGState()
    action.set_state(arr)

    assert action.get_cos_state() is arr
    assert action.get_state() == [on, ocg_a, off, ocg_b]


def test_state_round_trip_from_iterable_with_strings_and_ocgs() -> None:
    ocg_a = PDOptionalContentGroup("Layer A")
    ocg_b = PDOptionalContentGroup("Layer B")

    action = PDActionSetOCGState()
    action.set_state(["ON", ocg_a, "Toggle", ocg_b, "off"])

    items = action.get_state()
    assert items[0] == COSName.get_pdf_name("ON")
    assert items[1] is ocg_a.get_cos_object()
    assert items[2] == COSName.get_pdf_name("Toggle")
    assert items[3] is ocg_b.get_cos_object()
    assert items[4] == COSName.get_pdf_name("OFF")  # case-insensitive


def test_state_missing_returns_empty_list() -> None:
    action = PDActionSetOCGState()
    assert action.get_state() == []
    assert action.get_cos_state() is None


def test_state_set_none_removes_entry() -> None:
    action = PDActionSetOCGState()
    action.set_state([COSName.get_pdf_name("ON"), _ocg_dict("X")])
    assert action.get_cos_state() is not None

    action.set_state(None)
    assert action.get_cos_state() is None
    assert action.get_state() == []


def test_invalid_state_string_raises() -> None:
    action = PDActionSetOCGState()
    with pytest.raises(ValueError):
        action.set_state(["bogus"])


def test_invalid_state_entry_type_raises() -> None:
    action = PDActionSetOCGState()
    with pytest.raises(TypeError):
        action.set_state([42])  # type: ignore[list-item]


def test_preserve_rb_defaults_to_true() -> None:
    action = PDActionSetOCGState()
    assert action.is_preserve_rb() is True


def test_preserve_rb_round_trip() -> None:
    action = PDActionSetOCGState()
    action.set_preserve_rb(False)
    assert action.is_preserve_rb() is False
    cos = action.get_cos_object()
    assert cos.get_boolean(COSName.get_pdf_name("PreserveRB"), True) is False

    action.set_preserve_rb(True)
    assert action.is_preserve_rb() is True


def test_state_preamble_constants() -> None:
    """The PDF 32000-1 Table 207 preamble names are exposed as
    class-level constants for caller convenience."""
    assert PDActionSetOCGState.STATE_ON == "ON"
    assert PDActionSetOCGState.STATE_OFF == "OFF"
    assert PDActionSetOCGState.STATE_TOGGLE == "Toggle"


def test_state_preamble_constants_round_trip_via_set_state() -> None:
    """The exposed preamble constants drop straight into ``set_state``
    via the string-coercion path."""
    action = PDActionSetOCGState()
    ocg = _ocg_dict("L1")
    action.set_state(
        [
            PDActionSetOCGState.STATE_ON,
            ocg,
            PDActionSetOCGState.STATE_TOGGLE,
            ocg,
        ]
    )
    items = action.get_state()
    assert items[0] == COSName.get_pdf_name("ON")
    assert items[2] == COSName.get_pdf_name("Toggle")


def test_get_preserve_rb_alias_matches_is_preserve_rb() -> None:
    """``get_preserve_rb`` is a bean-style alias of ``is_preserve_rb``."""
    action = PDActionSetOCGState()
    assert action.get_preserve_rb() is True
    assert action.get_preserve_rb() == action.is_preserve_rb()

    action.set_preserve_rb(False)
    assert action.get_preserve_rb() is False
    assert action.get_preserve_rb() == action.is_preserve_rb()


def test_wrap_existing_dictionary_preserves_state() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("S"), "SetOCGState")
    arr = COSArray([COSName.get_pdf_name("OFF"), _ocg_dict("Layer")])
    raw.set_item(COSName.get_pdf_name("State"), arr)
    raw.set_boolean(COSName.get_pdf_name("PreserveRB"), False)

    action = PDActionSetOCGState(raw)
    assert action.get_cos_object() is raw
    assert action.get_cos_state() is arr
    assert action.is_preserve_rb() is False
