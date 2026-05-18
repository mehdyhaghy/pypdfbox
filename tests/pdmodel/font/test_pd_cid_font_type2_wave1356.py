"""Wave 1356 final-push coverage tests for
:mod:`pypdfbox.pdmodel.font.pd_cid_font_type2`.

Closes the last residual lines in 0.9.0rc1:

* Lines 643-644 — ``get_path_from_outlines`` ``code_to_gid`` exception
  branch returning ``None`` before the glyph-set walk.
* Line 727 — ``encode`` falling through the embedded branch with
  ``cid == -1`` (neither Identity-H/V nor predefined CMap resolved a
  CID and no ``/ToUnicode`` fallback was supplied), where ``cid`` is
  forced back to 0 before raising ``ValueError``.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

# ---------- get_path_from_outlines lines 643-644 ---------------------------


def test_get_path_from_outlines_returns_none_when_code_to_gid_raises() -> None:
    """Lines 643-644 — ``code_to_gid`` blows up; the ``except`` arm
    swallows and returns ``None`` before the glyph-set walk."""

    class _StubOTF:
        _tt = object()

        def is_post_script(self) -> bool:
            return True

    stub = _StubOTF()
    font = PDCIDFontType2()
    font.get_true_type_font = lambda: stub  # type: ignore[assignment,method-assign,return-value]

    def _raise(_code: int) -> int:
        raise RuntimeError("forced")

    font.code_to_gid = _raise  # type: ignore[assignment,method-assign]
    assert font.get_path_from_outlines(0x41) is None


# ---------- encode line 727 ------------------------------------------------


def test_encode_embedded_resets_cid_to_zero_when_minus_one_falls_through() -> None:
    """Line 727 — Embedded font, no Identity- parent CMap, no UCS-2
    fallback, no ``/ToUnicode`` map. ``cid`` stays ``-1`` through the
    if/elif chain; ``cid in (-1, 0)`` then triggers, the ``/ToUnicode``
    branch is skipped because the parent has no map, and the
    ``if cid == -1: cid = 0`` reset runs before the final raise."""
    from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

    class _StubParent(PDType0Font):
        def get_cmap(self) -> Any:  # type: ignore[override]
            # No CMap at all — parent_cmap_name stays None so neither the
            # Identity branch nor the UCS-2 branch runs.
            return None

        def get_cmap_ucs2(self) -> Any:  # type: ignore[override]
            return None

        def get_to_unicode_cmap(self) -> Any:  # type: ignore[override]
            return None

    parent = _StubParent()
    font = PDCIDFontType2(parent_type0_font=parent)

    class _StubTTF:
        def get_unicode_cmap_subtable(self) -> Any:
            # The embedded branch never touches the unicode cmap when
            # neither Identity- nor predefined-CMap branches fire, so
            # leaving it set is fine; we still need a truthy ttf for
            # ``is_embedded`` to be plausible.
            return None

    stub_ttf = _StubTTF()
    font.get_true_type_font = lambda: stub_ttf  # type: ignore[assignment,method-assign,return-value]
    font.is_embedded = lambda: True  # type: ignore[assignment,method-assign,return-value]

    # cid stays at -1 through the if/elif chain, the fallback at 714
    # finds no ToUnicode map, then line 727 forces cid = 0 → ValueError
    # at line 736.
    with pytest.raises(ValueError, match="No glyph"):
        font.encode(0x41)
