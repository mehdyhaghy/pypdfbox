"""Extra branch coverage for cos files — wave 1400.

Closes additional partial branches uncovered after the main wave
batch:

* ``cos_array.clear()`` no-op when already empty (109 → 108).
* ``cos_array.remove_all`` with items not present (155 → 156, 158 → 159).
* ``cos_dictionary.add_all`` with empty source (353 → 351).
* ``cos_dictionary.get_name`` when value isn't a COSName (458 → 460).
* ``cos_dictionary.__contains__`` with non-name key (886 → 888).
* ``cos_stream.create_raw_input_stream`` buffer-None branch
  (235 → 236).
* ``cos_stream`` encoding-output double-close idempotence (68 → 90).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)

# ----------------------------------------------------------------------
# cos_array.clear() no-op when already empty
# ----------------------------------------------------------------------


def test_cos_array_clear_noop_when_already_empty() -> None:
    """Calling ``clear()`` on an already-empty array must not fire the
    update notification (the inner ``if self._items`` is False).

    Closes branch (109 → 108)."""
    arr = COSArray()
    # Idempotent clear — no exception, no side-effects beyond a no-op.
    arr.clear()
    arr.clear()
    assert arr.size() == 0


# ----------------------------------------------------------------------
# cos_array.remove_all with items absent
# ----------------------------------------------------------------------


def test_cos_array_remove_all_with_items_absent_is_noop() -> None:
    """``remove_all`` over items NOT in the array returns False without
    firing the update notification.

    Closes branches (155 → 156) and (158 → 159)."""
    arr = COSArray()
    arr.add(COSInteger.get(1))
    # Items missing from the array — while-loop body never runs.
    changed = arr.remove_all([COSString("not-here"), COSString("nope")])
    assert changed is False
    assert arr.size() == 1


def test_cos_array_remove_all_with_items_present_returns_true() -> None:
    """Positive control: items present → removed, returns True."""
    arr = COSArray()
    item = COSString("here")
    arr.add(item)
    assert arr.remove_all([item]) is True
    assert arr.size() == 0


# ----------------------------------------------------------------------
# cos_dictionary.add_all with empty source
# ----------------------------------------------------------------------


def test_cos_dictionary_add_all_with_empty_other_is_noop() -> None:
    """add_all from an empty dict skips the update notification.

    Closes branch (353 → 351)."""
    target = COSDictionary()
    target.set_int("Pre", 1)
    target.add_all(COSDictionary())  # empty other
    assert target.get_int("Pre") == 1
    assert target.size() == 1


# ----------------------------------------------------------------------
# cos_dictionary.get_name fallback when value is not a COSName
# ----------------------------------------------------------------------


def test_cos_dictionary_get_name_returns_default_when_value_not_a_name() -> None:
    """When the resolved value is not a COSName, ``get_name`` returns
    the supplied default.

    Closes branch (458 → 460)."""
    d = COSDictionary()
    d.set_int("X", 5)  # COSInteger, not COSName
    assert d.get_name("X", default="fallback") == "fallback"


def test_cos_dictionary_get_name_returns_value_when_value_is_a_name() -> None:
    """Positive control: when value IS a COSName, get_name returns the
    string form of its name (not the default)."""
    d = COSDictionary()
    d.set_item("Y", COSName.get_pdf_name("HelloName"))
    assert d.get_name("Y") == "HelloName"


# ----------------------------------------------------------------------
# cos_dictionary.__contains__ with non-name/str key
# ----------------------------------------------------------------------


def test_cos_dictionary_contains_non_name_key_returns_false() -> None:
    """``__contains__`` accepts only str / COSName keys; anything else
    returns False.

    Closes branch (886 → 888)."""
    d = COSDictionary()
    d.set_int("A", 7)
    # Non-name/str → False.
    assert (42 in d) is False
    assert (None in d) is False
    assert (COSFloat(3.14) in d) is False
    # Positive control: 'A' (str) and COSName('A') both True.
    assert "A" in d
    assert COSName.get_pdf_name("A") in d


# ----------------------------------------------------------------------
# cos_stream.create_raw_input_stream — buffer None raises
# ----------------------------------------------------------------------


def test_cos_stream_create_raw_input_stream_raises_when_no_buffer() -> None:
    """A freshly-constructed COSStream has no body — calling
    ``create_raw_input_stream`` raises OSError.

    Closes branch (235 → 236)."""
    stream = COSStream()
    with pytest.raises(OSError, match="no data"):
        stream.create_raw_input_stream()


# ----------------------------------------------------------------------
# cos_stream encoding-output double-close idempotence
# ----------------------------------------------------------------------


def test_cos_stream_encoding_output_close_is_idempotent() -> None:
    """A second ``close()`` on the encoding-output stream must not
    re-encode the bytes (which would rerun the filter chain and
    clobber the body with a re-encoded blob).

    Closes branch (68 → 90)."""
    stream = COSStream()
    out = stream.create_output_stream(COSName.FLATE_DECODE)
    out.write(b"hello")
    out.close()
    # Capture body after first close.
    in_view = stream.create_view()
    first = bytearray()
    while True:
        b = in_view.read()
        if b == -1:
            break
        first.append(b)
    # Second close — guard fires, no re-encode.
    out.close()
    in_view2 = stream.create_view()
    second = bytearray()
    while True:
        b = in_view2.read()
        if b == -1:
            break
        second.append(b)
    assert bytes(second) == bytes(first)
