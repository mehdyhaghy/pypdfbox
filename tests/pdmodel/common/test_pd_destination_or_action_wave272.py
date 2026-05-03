"""Wave 272 — PDDestinationOrAction predicate / factory round-out tests."""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.common.pd_destination_or_action import (
    PDDestinationOrAction,
    create_from_open_action_entry,
    is_action,
    is_destination,
    kind_of,
)


def _make_xyz_array() -> COSArray:
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.get_pdf_name("XYZ"))
    arr.add(COSFloat(1.0))
    arr.add(COSFloat(2.0))
    arr.add(COSFloat(3.0))
    return arr


def _make_goto_action() -> COSDictionary:
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("S"), "GoTo")
    return d


# ---------- is_action() ----------


def test_is_action_true_for_action_wave272() -> None:
    action = PDDestinationOrAction.create(_make_goto_action())
    assert is_action(action) is True


def test_is_action_false_for_destination_wave272() -> None:
    dest = PDDestinationOrAction.create(_make_xyz_array())
    assert is_action(dest) is False


def test_is_action_false_for_none_wave272() -> None:
    assert is_action(None) is False


def test_is_action_false_for_raw_cos_dictionary_wave272() -> None:
    """The predicate checks the wrapper type — raw COS values are not
    actions until promoted via :meth:`PDDestinationOrAction.create`."""
    assert is_action(_make_goto_action()) is False


# ---------- is_destination() ----------


def test_is_destination_true_for_destination_wave272() -> None:
    dest = PDDestinationOrAction.create(_make_xyz_array())
    assert is_destination(dest) is True


def test_is_destination_true_for_named_destination_wave272() -> None:
    dest = PDDestinationOrAction.create(COSName.get_pdf_name("MyDest"))
    assert is_destination(dest) is True


def test_is_destination_false_for_action_wave272() -> None:
    action = PDDestinationOrAction.create(_make_goto_action())
    assert is_destination(action) is False


def test_is_destination_false_for_none_wave272() -> None:
    assert is_destination(None) is False


# ---------- kind_of() ----------


def test_kind_of_returns_action_for_action_wave272() -> None:
    assert kind_of(PDDestinationOrAction.create(_make_goto_action())) == "action"


def test_kind_of_returns_destination_for_destination_wave272() -> None:
    assert (
        kind_of(PDDestinationOrAction.create(_make_xyz_array())) == "destination"
    )


def test_kind_of_returns_destination_for_named_destination_wave272() -> None:
    """Named destinations (created from a ``COSName``) round-trip through
    the same factory and should be tagged ``destination``."""
    assert (
        kind_of(PDDestinationOrAction.create(COSString("ByName"))) == "destination"
    )


def test_kind_of_returns_none_for_unknown_value_wave272() -> None:
    assert kind_of(None) is None
    assert kind_of("plain string") is None
    assert kind_of(_make_goto_action()) is None  # raw dict, never promoted


# ---------- create_from_open_action_entry() ----------


def test_create_from_open_action_entry_dispatches_dict_wave272() -> None:
    """The free-function factory mirrors :meth:`PDDestinationOrAction.create`
    for action-shaped dictionaries."""
    result = create_from_open_action_entry(_make_goto_action())
    assert is_action(result)


def test_create_from_open_action_entry_dispatches_array_wave272() -> None:
    result = create_from_open_action_entry(_make_xyz_array())
    assert is_destination(result)


def test_create_from_open_action_entry_returns_none_for_none_wave272() -> None:
    assert create_from_open_action_entry(None) is None


def test_create_from_open_action_entry_matches_static_method_wave272() -> None:
    """The free function must produce the same arm as the static factory
    for every dispatch path in :meth:`PDDestinationOrAction.create`."""
    cases = [
        _make_goto_action(),
        _make_xyz_array(),
        COSName.get_pdf_name("MyDest"),
        COSString("MyDest"),
        None,
    ]
    for case in cases:
        free = create_from_open_action_entry(case)
        static = PDDestinationOrAction.create(case)
        assert kind_of(free) == kind_of(static)
