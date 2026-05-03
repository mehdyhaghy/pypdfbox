"""Tests for :class:`CIDFontMapping`.

Upstream Java has no checked-in unit tests for
``org.apache.pdfbox.pdmodel.font.CIDFontMapping``. These tests pin the
two-slot constructor shape, ``is_cid_font`` semantics, and the
``FontMapping`` inheritance contract.
"""

from __future__ import annotations

from pypdfbox.fontbox.cid_font_mapping import CIDFontMapping
from pypdfbox.fontbox.font_mapper import DefaultFontMapper
from pypdfbox.fontbox.font_mapping import FontMapping


def _wrapper(name: str) -> object:
    """Pull a real :class:`Standard14FontWrapper` out of the default mapper.

    Convenient FontBox-shaped object for the TTF slot — saves writing a
    bespoke stub for each test.
    """
    mapping = DefaultFontMapper().get_font_box_font(name, None)
    assert mapping is not None
    return mapping.get_font()


# ---------------------------------------------------------------------------
# OTF-only branch — CID hit
# ---------------------------------------------------------------------------


def test_otf_only_constructor_sets_cid_flag() -> None:
    otf = _wrapper("Helvetica")
    cm = CIDFontMapping(otf, None, is_fallback=False)
    assert cm.is_cid_font() is True
    assert cm.get_font() is otf
    assert cm.get_true_type_font() is None
    assert cm.is_fallback() is False


# ---------------------------------------------------------------------------
# TTF-only branch — CID miss
# ---------------------------------------------------------------------------


def test_ttf_only_constructor_clears_cid_flag() -> None:
    ttf = _wrapper("Times-Roman")
    cm = CIDFontMapping(None, ttf, is_fallback=True)
    assert cm.is_cid_font() is False
    assert cm.get_font() is None
    assert cm.get_true_type_font() is ttf
    assert cm.is_fallback() is True


# ---------------------------------------------------------------------------
# FontMapping inheritance contract
# ---------------------------------------------------------------------------


def test_is_subclass_of_font_mapping() -> None:
    assert issubclass(CIDFontMapping, FontMapping)


def test_inherits_font_mapping_accessors() -> None:
    """Inherited :meth:`FontMapping.get_font` / :meth:`is_fallback` keep working."""
    otf = _wrapper("Courier")
    cm = CIDFontMapping(otf, None, is_fallback=False)
    assert cm.get_font() is otf
    assert cm.is_fallback() is False


# ---------------------------------------------------------------------------
# repr — both slots surfaced for diagnostics
# ---------------------------------------------------------------------------


def test_repr_includes_both_slot_names_when_set() -> None:
    otf = _wrapper("Helvetica")
    ttf = _wrapper("Times-Roman")
    cm = CIDFontMapping(otf, ttf, is_fallback=False)
    text = repr(cm)
    assert "Helvetica" in text
    assert "Times-Roman" in text
    assert "is_fallback=False" in text


def test_repr_uses_none_when_slot_empty() -> None:
    otf = _wrapper("Helvetica")
    cm = CIDFontMapping(otf, None, is_fallback=False)
    text = repr(cm)
    assert "Helvetica" in text
    assert "ttf=None" in text
