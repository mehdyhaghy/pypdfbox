"""Deep parity tests for ``BlendMode`` COSName ↔ enum dispatch.

Wave 1363 covered the per-channel formulas (``BlendChannelFunction``) and
the non-separable RGB-triple compose path (``BlendFunction``); the
``COSName`` ↔ singleton mapping was only spot-checked. This wave pins:

  * Symmetric dispatch for every one of the 16 standard modes via both
    ``get_instance(COSName)`` and ``from_cos(COSName)``.
  * Round-trip preservation: every singleton's ``get_cos_name()`` resolves
    back to the same singleton via ``get_instance``.
  * ``create_blend_mode_map()`` returns one entry per recognised name +
    ``Compatible`` (17 entries total).
  * ``Compatible`` alias maps to ``NORMAL`` in every dispatch entry point.
  * Mode-name lookup is case-sensitive (matches Java ``COSName.equals``).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode

# The 16 standard modes (PDF 32000-1 §11.3.5) — separable first, then HSL.
_ALL_SINGLETONS = (
    ("Normal", BlendMode.NORMAL),
    ("Multiply", BlendMode.MULTIPLY),
    ("Screen", BlendMode.SCREEN),
    ("Overlay", BlendMode.OVERLAY),
    ("Darken", BlendMode.DARKEN),
    ("Lighten", BlendMode.LIGHTEN),
    ("ColorDodge", BlendMode.COLOR_DODGE),
    ("ColorBurn", BlendMode.COLOR_BURN),
    ("HardLight", BlendMode.HARD_LIGHT),
    ("SoftLight", BlendMode.SOFT_LIGHT),
    ("Difference", BlendMode.DIFFERENCE),
    ("Exclusion", BlendMode.EXCLUSION),
    ("Hue", BlendMode.HUE),
    ("Saturation", BlendMode.SATURATION),
    ("Color", BlendMode.COLOR),
    ("Luminosity", BlendMode.LUMINOSITY),
)


@pytest.mark.parametrize("name,singleton", _ALL_SINGLETONS)
def test_get_instance_cos_name_returns_correct_singleton(name, singleton):
    """Every standard mode round-trips via COSName-based dispatch."""
    assert BlendMode.get_instance(COSName.get_pdf_name(name)) is singleton


@pytest.mark.parametrize("name,singleton", _ALL_SINGLETONS)
def test_get_instance_str_returns_correct_singleton(name, singleton):
    """String-form dispatch matches COSName-form dispatch."""
    assert BlendMode.get_instance(name) is singleton


@pytest.mark.parametrize("name,singleton", _ALL_SINGLETONS)
def test_from_cos_name_returns_correct_singleton(name, singleton):
    assert BlendMode.from_cos(COSName.get_pdf_name(name)) is singleton


@pytest.mark.parametrize("name,singleton", _ALL_SINGLETONS)
def test_round_trip_cos_name(name, singleton):
    """``get_cos_name()`` returns the canonical name; re-dispatching via
    that COSName yields the same singleton instance."""
    cos_name = singleton.get_cos_name()
    assert cos_name == COSName.get_pdf_name(name)
    assert BlendMode.get_instance(cos_name) is singleton


@pytest.mark.parametrize("name,singleton", _ALL_SINGLETONS)
def test_get_called_with_canonical_name_returns_singleton(name, singleton):
    assert BlendMode.get(name) is singleton


# ---------------------------------------------------------------------------
# Compatible alias — Adobe-recognised synonym for Normal (§11.6.5.2 footnote)
# ---------------------------------------------------------------------------


def test_compatible_class_attribute_is_normal():
    assert BlendMode.COMPATIBLE is BlendMode.NORMAL


def test_compatible_name_resolves_to_normal_via_get():
    assert BlendMode.get("Compatible") is BlendMode.NORMAL


def test_compatible_name_resolves_to_normal_via_get_instance_str():
    assert BlendMode.get_instance("Compatible") is BlendMode.NORMAL


def test_compatible_name_resolves_to_normal_via_get_instance_cos_name():
    assert (
        BlendMode.get_instance(COSName.get_pdf_name("Compatible"))
        is BlendMode.NORMAL
    )


def test_compatible_array_position_inside_fallback_chain():
    # COSArray fallback chain: Compatible at position 0 → NORMAL.
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Compatible"))
    arr.add(COSName.get_pdf_name("Multiply"))
    # Compatible's name is recognised and dispatches before Multiply.
    assert BlendMode.get_instance(arr) is BlendMode.NORMAL


# ---------------------------------------------------------------------------
# Case sensitivity — Java COSName.equals is exact-string match
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "variant",
    [
        "multiply",  # lowercase
        "MULTIPLY",  # uppercase
        "MultIply",  # mixed
        "Multipl",  # truncated
        "MultiplyExtra",  # suffix
    ],
)
def test_get_instance_rejects_case_variants_falls_back_to_normal(variant):
    """COSName matching is case-sensitive (Java equals), so any case
    variant is treated as unknown and falls back to ``NORMAL``."""
    assert BlendMode.get_instance(COSName.get_pdf_name(variant)) is BlendMode.NORMAL


# ---------------------------------------------------------------------------
# create_blend_mode_map — upstream's static dispatch table
# ---------------------------------------------------------------------------


def test_create_blend_mode_map_has_17_entries():
    """16 standard modes + Compatible alias = 17 entries."""
    m = BlendMode.create_blend_mode_map()
    assert len(m) == 17


def test_create_blend_mode_map_compatible_maps_to_normal():
    m = BlendMode.create_blend_mode_map()
    assert m[COSName.get_pdf_name("Compatible")] is BlendMode.NORMAL


@pytest.mark.parametrize("name,singleton", _ALL_SINGLETONS)
def test_create_blend_mode_map_contains_each_standard_mode(name, singleton):
    m = BlendMode.create_blend_mode_map()
    assert m[COSName.get_pdf_name(name)] is singleton


def test_create_blend_mode_map_returns_fresh_dict_each_call():
    # Upstream's table is package-private and memoised; pypdfbox exposes
    # the builder which constructs a fresh dict each call. Mutating the
    # returned dict must not affect future calls.
    m1 = BlendMode.create_blend_mode_map()
    m1.clear()
    m2 = BlendMode.create_blend_mode_map()
    assert len(m2) == 17


# ---------------------------------------------------------------------------
# Unsupported COS types — must all degrade to ``NORMAL`` per spec
# ---------------------------------------------------------------------------


def test_get_instance_cos_dictionary_falls_back_to_normal():
    assert BlendMode.get_instance(COSDictionary()) is BlendMode.NORMAL


def test_get_instance_cos_string_falls_back_to_normal():
    # COSString is not a valid /BM payload; degrade gracefully.
    assert BlendMode.get_instance(COSString(b"Multiply")) is BlendMode.NORMAL


def test_get_instance_empty_array_falls_back_to_normal():
    # No fallback chain → spec-mandated default Normal.
    assert BlendMode.get_instance(COSArray()) is BlendMode.NORMAL


def test_from_cos_for_unsupported_type_returns_none():
    """Unlike ``get_instance`` (which always returns NORMAL as the default),
    ``from_cos`` returns ``None`` for unsupported types — callers can
    distinguish "absent" from "fallback applied"."""
    assert BlendMode.from_cos(None) is None
    assert BlendMode.from_cos(COSDictionary()) is None
    assert BlendMode.from_cos(COSString(b"Multiply")) is None


# ---------------------------------------------------------------------------
# Singleton consistency across all dispatch entry points
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,singleton", _ALL_SINGLETONS)
def test_all_dispatch_entry_points_yield_same_singleton(name, singleton):
    """``get(name)`` / ``get_instance(name)`` / ``get_instance(COSName)`` /
    ``from_cos(COSName)`` must all resolve to the same interned instance."""
    via_get = BlendMode.get(name)
    via_get_instance_str = BlendMode.get_instance(name)
    via_get_instance_cosname = BlendMode.get_instance(COSName.get_pdf_name(name))
    via_from_cos = BlendMode.from_cos(COSName.get_pdf_name(name))
    assert via_get is singleton
    assert via_get_instance_str is singleton
    assert via_get_instance_cosname is singleton
    assert via_from_cos is singleton


def test_iter_standard_matches_dispatch_table_singletons():
    """Every singleton emitted by ``iter_standard()`` should be the same
    object as the dispatch-table value for its name."""
    table = BlendMode.create_blend_mode_map()
    for singleton in BlendMode.iter_standard():
        assert table[singleton.get_cos_name()] is singleton


def test_standard_names_match_iter_standard_names():
    standards = {bm.get_name() for bm in BlendMode.iter_standard()}
    assert standards == BlendMode.STANDARD_NAMES
