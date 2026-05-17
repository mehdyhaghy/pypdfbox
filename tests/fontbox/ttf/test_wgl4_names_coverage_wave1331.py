"""Wave 1331 coverage boost: ``WGL4Names`` static façade.

The module-level helpers are already covered by the existing test
file; only the staticmethod wrappers on the ``WGL4Names`` class (lines
92/97/102) were untouched.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.wgl4_names import (
    NUMBER_OF_MAC_GLYPHS,
    WGL4Names,
    get_all_names,
    get_glyph_index,
    get_glyph_name,
)


def test_class_constant_matches_module_constant() -> None:
    assert WGL4Names.NUMBER_OF_MAC_GLYPHS == NUMBER_OF_MAC_GLYPHS == 258


# --------------------------------------------------------------------------
# Static façade delegates straight to the module-level helpers
# --------------------------------------------------------------------------


def test_class_get_glyph_index_matches_module_helper() -> None:
    """Line 92: ``WGL4Names.get_glyph_index`` delegates to module helper."""
    for sample in (".notdef", "space", "A", "dcroat"):
        assert WGL4Names.get_glyph_index(sample) == get_glyph_index(sample)


def test_class_get_glyph_index_returns_none_for_unknown() -> None:
    assert WGL4Names.get_glyph_index("not_a_real_glyph_name") is None


def test_class_get_glyph_name_matches_module_helper() -> None:
    """Line 97: ``WGL4Names.get_glyph_name`` delegates to module helper."""
    for sample in (0, 1, 3, 36, NUMBER_OF_MAC_GLYPHS - 1):
        assert WGL4Names.get_glyph_name(sample) == get_glyph_name(sample)


def test_class_get_glyph_name_out_of_range_returns_none() -> None:
    assert WGL4Names.get_glyph_name(-1) is None
    assert WGL4Names.get_glyph_name(NUMBER_OF_MAC_GLYPHS) is None


def test_class_get_all_names_matches_module_helper() -> None:
    """Line 102: ``WGL4Names.get_all_names`` delegates to module helper."""
    assert WGL4Names.get_all_names() == get_all_names()


def test_class_get_all_names_returns_fresh_list_each_call() -> None:
    """Mutating one returned list must not affect subsequent calls."""
    a = WGL4Names.get_all_names()
    a[0] = "MUTATED"
    assert WGL4Names.get_all_names()[0] == ".notdef"
