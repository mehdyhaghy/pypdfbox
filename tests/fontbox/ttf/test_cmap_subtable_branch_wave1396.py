"""Wave 1396 branch-coverage tests for ``CmapSubtable``.

Closes the False-branch arrow at line 391->390 in
``pypdfbox/fontbox/ttf/cmap_subtable.py`` — ``get_glyph_id_uvs``
walking past a default UVS entry whose selector OR code-point range
doesn't match the request.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable


def test_get_glyph_id_uvs_default_uvs_no_selector_match_returns_zero() -> None:
    """default_uvs entry whose selector doesn't match yields the loop
    continuing rather than matching.

    Closes False arm of ``sel == variation_selector and ...`` at line
    391: the False-from-selector-mismatch path.
    """
    sub = CmapSubtable()
    # default UVS entry: selector=0xE0100, range [0x4E00, 0x4F00]
    sub._default_uvs = [(0xE0100, 0x4E00, 0x4F00)]  # noqa: SLF001
    sub._uvs_mapping = {}  # noqa: SLF001
    # Request with a different selector → loop continues, no match.
    assert sub.get_glyph_id_uvs(0x4E00, 0xE0101) == 0


def test_get_glyph_id_uvs_default_uvs_code_point_out_of_range() -> None:
    """default_uvs entry where the selector matches but the code-point
    is out of range yields the loop continuing.

    Closes the False arm of ``start <= code_point <= end`` at line 391.
    """
    sub = CmapSubtable()
    sub._default_uvs = [(0xE0100, 0x4E00, 0x4F00)]  # noqa: SLF001
    sub._uvs_mapping = {}  # noqa: SLF001
    # Selector matches but code-point is below range.
    assert sub.get_glyph_id_uvs(0x4000, 0xE0100) == 0
    # And above range.
    assert sub.get_glyph_id_uvs(0x5000, 0xE0100) == 0


def test_get_glyph_id_uvs_direct_mapping_hit_short_circuits() -> None:
    """A direct (non-default) UVS hit returns the mapped glyph immediately,
    skipping the default_uvs walk entirely.
    """
    sub = CmapSubtable()
    sub._uvs_mapping = {(0x4E00, 0xE0100): 42}  # noqa: SLF001
    sub._default_uvs = []  # noqa: SLF001
    assert sub.get_glyph_id_uvs(0x4E00, 0xE0100) == 42


def test_get_glyph_id_uvs_default_uvs_match_returns_zero_for_base_glyph_fallback() -> None:
    """A default-UVS match still returns 0 — the protocol is that the
    caller falls back to the base glyph via ``get_glyph_id``.
    """
    sub = CmapSubtable()
    sub._uvs_mapping = {}  # noqa: SLF001
    sub._default_uvs = [(0xE0100, 0x4E00, 0x4F00)]  # noqa: SLF001
    # Direct match — both selector + code-point in range.
    assert sub.get_glyph_id_uvs(0x4E50, 0xE0100) == 0


def test_has_uvs_returns_false_for_empty_subtable() -> None:
    """Default subtable (no UVS data) reports False.

    Sanity check around the ``or`` in ``has_uvs``.
    """
    sub = CmapSubtable()
    assert sub.has_uvs() is False


def test_has_uvs_returns_true_when_default_uvs_populated() -> None:
    """A subtable with only default UVS entries still reports True."""
    sub = CmapSubtable()
    sub._default_uvs = [(0xE0100, 0x4E00, 0x4F00)]  # noqa: SLF001
    assert sub.has_uvs() is True
