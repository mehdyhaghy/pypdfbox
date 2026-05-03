"""Tests for :class:`pypdfbox.fontbox.font_mapping.FontMapping`.

Upstream Java has no checked-in unit tests for
``org.apache.pdfbox.pdmodel.font.FontMapping`` (it's a tiny final-fields
container). These tests pin the snake_case API surface, the
``bool``-coercion of the ``is_fallback`` flag, the
``OSError``-tolerant ``__repr__`` path, and the typing-protocol shape.
"""

from __future__ import annotations

from pypdfbox.fontbox.font_box_font import FontBoxFont
from pypdfbox.fontbox.font_mapper import DefaultFontMapper
from pypdfbox.fontbox.font_mapping import FontMapping


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _real_font(name: str) -> FontBoxFont:
    """Return a real FontBox font via the default mapper.

    Saves writing a bespoke stub when the test only needs a typical
    fontbox-shaped object.
    """
    mapping = DefaultFontMapper().get_font_box_font(name, None)
    assert mapping is not None
    return mapping.get_font()


class _StubFont:
    """Minimal FontBoxFont-shaped stub for repr / generic tests."""

    def __init__(self, name: str | None) -> None:
        self._name = name

    def get_name(self) -> str | None:
        return self._name


class _RaisingFont:
    """Stub whose ``get_name`` raises ``OSError`` — exercises repr fallback."""

    def get_name(self) -> str:
        raise OSError("broken stream")


# ---------------------------------------------------------------------------
# constructor + accessors
# ---------------------------------------------------------------------------


def test_get_font_returns_constructor_argument() -> None:
    font = _real_font("Helvetica")
    fm = FontMapping(font, is_fallback=False)
    assert fm.get_font() is font


def test_is_fallback_returns_constructor_argument_true() -> None:
    font = _real_font("Courier")
    fm = FontMapping(font, is_fallback=True)
    assert fm.is_fallback() is True


def test_is_fallback_returns_constructor_argument_false() -> None:
    font = _real_font("Times-Roman")
    fm = FontMapping(font, is_fallback=False)
    assert fm.is_fallback() is False


# ---------------------------------------------------------------------------
# is_fallback flag is coerced through ``bool(...)``
# ---------------------------------------------------------------------------


def test_is_fallback_coerces_truthy_int_to_true() -> None:
    fm = FontMapping(_StubFont("Stub"), is_fallback=1)  # type: ignore[arg-type]
    assert fm.is_fallback() is True


def test_is_fallback_coerces_zero_to_false() -> None:
    fm = FontMapping(_StubFont("Stub"), is_fallback=0)  # type: ignore[arg-type]
    assert fm.is_fallback() is False


def test_is_fallback_coerces_non_empty_str_to_true() -> None:
    fm = FontMapping(_StubFont("Stub"), is_fallback="yes")  # type: ignore[arg-type]
    assert fm.is_fallback() is True


def test_is_fallback_coerces_empty_str_to_false() -> None:
    fm = FontMapping(_StubFont("Stub"), is_fallback="")  # type: ignore[arg-type]
    assert fm.is_fallback() is False


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------


def test_repr_includes_font_name_and_fallback_flag() -> None:
    fm = FontMapping(_StubFont("MyFont"), is_fallback=False)
    text = repr(fm)
    assert "MyFont" in text
    assert "is_fallback=False" in text
    assert text.startswith("FontMapping(")


def test_repr_falls_back_to_type_name_when_get_name_returns_none() -> None:
    fm = FontMapping(_StubFont(None), is_fallback=True)
    text = repr(fm)
    assert "_StubFont" in text
    assert "is_fallback=True" in text


def test_repr_falls_back_to_type_name_when_get_name_raises_oserror() -> None:
    fm = FontMapping(_RaisingFont(), is_fallback=False)
    # Must not propagate the OSError — repr should be safe in tracebacks.
    text = repr(fm)
    assert "_RaisingFont" in text
    assert "is_fallback=False" in text


def test_repr_uses_real_font_name_for_standard14_wrapper() -> None:
    font = _real_font("Helvetica")
    fm = FontMapping(font, is_fallback=False)
    text = repr(fm)
    # The standard14 wrapper exposes the upstream PostScript name.
    assert "Helvetica" in text


# ---------------------------------------------------------------------------
# class shape
# ---------------------------------------------------------------------------


def test_uses_slots_to_keep_per_instance_layout_small() -> None:
    fm = FontMapping(_StubFont("Stub"), is_fallback=False)
    assert FontMapping.__slots__ == ("_font", "_is_fallback")
    # __slots__ means no __dict__ and no ad-hoc attributes.
    assert not hasattr(fm, "__dict__")


def test_no_camelcase_aliases_remain_on_class() -> None:
    """Strict snake_case rule — Java-name aliases must be gone."""
    assert not hasattr(FontMapping, "getFont")
    assert not hasattr(FontMapping, "isFallback")


def test_subscriptable_for_typed_generic_parameter() -> None:
    """``FontMapping[FontBoxFont]`` is the typed generic alias."""
    alias = FontMapping[FontBoxFont]
    assert alias.__origin__ is FontMapping  # type: ignore[attr-defined]
