"""Hand-written tests for ``ColorToolTip.get_mark_up`` (upstream alias)."""

from __future__ import annotations

from pypdfbox.debugger.streampane.tooltip import ColorToolTip


class _Concrete(ColorToolTip):
    """A trivial concrete subclass used purely to exercise the alias."""


def test_get_mark_up_returns_same_payload_as_get_markup() -> None:
    ctt = _Concrete()
    via_alias = ctt.get_mark_up("12ab34")
    via_primary = ctt.get_markup("12ab34")
    assert via_alias.plain == via_primary.plain
    assert via_alias.segments[0].color_hex == via_primary.segments[0].color_hex


def test_get_mark_up_encodes_hex_in_segment() -> None:
    ctt = _Concrete()
    payload = ctt.get_mark_up("ff0000")
    assert payload.plain == "#ff0000"
    assert len(payload.segments) == 1
    assert payload.segments[0].color_hex == "ff0000"


def test_get_mark_up_available_as_instance_method() -> None:
    # Mirrors the upstream contract — `getMarkUp` is an instance method on
    # ColorToolTip subclasses, not a static helper.
    ctt = _Concrete()
    assert callable(ctt.get_mark_up)
    # Public name matches the upstream Java spelling (capital U on "Up").
    assert "get_mark_up" in dir(ctt)
