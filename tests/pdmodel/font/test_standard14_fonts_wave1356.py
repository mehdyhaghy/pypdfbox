"""Wave 1356 final-push coverage tests for
:mod:`pypdfbox.pdmodel.font.standard14_fonts`.

Closes the last residual lines in 0.9.0rc1:

* Lines 280-281 — ``_ttf_glyph_path_for_gid`` swallowing an exception
  raised by the glyph's ``draw`` callback (distinct from the
  glyph-set lookup exception at lines 274-275, which is already covered).
* Line 1037 — ``Standard14Fonts.get_glyph_path`` returning the
  ``uniXXXX`` outline from the mapped-font wrapper after the direct AGL
  name misses (the non-PUA, non-SymbolMT branch).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from pypdfbox.pdmodel.font.standard14_fonts import (
    Standard14Fonts,
    _ttf_glyph_path_for_gid,
)

# ---------- _ttf_glyph_path_for_gid lines 280-281 --------------------------


def test_ttf_glyph_path_for_gid_returns_empty_when_draw_raises() -> None:
    """Lines 280-281 — ``glyph.draw(pen)`` raises; the second ``try``
    arm swallows and returns ``[]``."""

    def _draw(_pen: Any) -> None:
        raise RuntimeError("malformed glyph")

    class _GlyphSet:
        def __getitem__(self, _name: str) -> Any:
            return SimpleNamespace(draw=_draw)

    class _InnerTT:
        def getGlyphSet(self) -> Any:  # noqa: N802 — fontTools name
            return _GlyphSet()

        def getGlyphName(self, _gid: int) -> str:  # noqa: N802 — fontTools name
            return "A"

    class _StubTTF:
        _tt = _InnerTT()

    assert _ttf_glyph_path_for_gid(_StubTTF(), 5) == []  # type: ignore[arg-type]


# ---------- get_glyph_path line 1037 ---------------------------------------


def test_get_glyph_path_returns_uni_xxxx_outline_from_wrapper() -> None:
    """Line 1037 — direct ``has_glyph(glyph_name)`` misses but the
    ``uniXXXX`` form is present in the wrapper. Returns the outline
    via the AGL fallback (not the SymbolMT PUA branch)."""

    class _FakeMapped:
        def has_glyph(self, name: str) -> bool:
            # Reject the direct AGL name; accept only the uniXXXX form.
            return name == "uni0041"

        def get_path(self, _name: str) -> list[tuple[Any, ...]]:
            return [("moveto", 7.0, 8.0)]

        def get_name(self) -> str:
            # Anything but "SymbolMT" so the PUA branch stays inert.
            return "LiberationSans"

    saved_sub = Standard14Fonts.get_substitute_ttf
    saved_map = Standard14Fonts.get_mapped_font
    Standard14Fonts.get_substitute_ttf = staticmethod(  # type: ignore[assignment, method-assign]
        lambda _name: None
    )
    Standard14Fonts.get_mapped_font = classmethod(  # type: ignore[assignment, method-assign]
        lambda _cls, _name: _FakeMapped()
    )
    try:
        # "A" → AGL → "A" string. has_glyph("A") is False, then
        # to_unicode("A") → "A" (U+0041) → uni0041 → has_glyph True →
        # return list(...) on line 1037.
        result = Standard14Fonts.get_glyph_path("Helvetica", "A")
        assert result == [("moveto", 7.0, 8.0)]
    finally:
        Standard14Fonts.get_substitute_ttf = saved_sub  # type: ignore[method-assign]
        Standard14Fonts.get_mapped_font = saved_map  # type: ignore[method-assign]
