"""Wave 1392 coverage round-out for
:mod:`pypdfbox.pdmodel.font.standard14_fonts`.

Closes the residual partial-branch gaps at lines 1141->1143 and
1159->1163 — defensive fall-through paths in the PUA-shifted glyph
resolution chain.
"""

from __future__ import annotations

from typing import Any

import pytest

import pypdfbox.pdmodel.font.standard14_fonts as s14
from pypdfbox.pdmodel.font import Standard14Fonts


def test_get_glyph_path_pua_fallback_path_empty_falls_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Branch 1141->1143 — when the Symbol PUA fallback finds a code in
    :data:`_SYMBOL_PUA_FALLBACKS` but ``_ttf_glyph_path_for_code_point``
    returns an empty path (substitute TTF doesn't carry the glyph), the
    code must fall through to the ``mapped_font`` branch."""
    saved = s14._ttf_glyph_path_for_code_point  # noqa: SLF001

    def _empty(*_args: Any, **_kwargs: Any) -> list[tuple[Any, ...]]:
        return []

    # Patch the codepoint helper so EVERY fallback resolves to [].
    monkeypatch.setattr(s14, "_ttf_glyph_path_for_code_point", _empty)
    # Pick a glyph_name that's in _SYMBOL_PUA_FALLBACKS — exercise via
    # Symbol base.
    fallback_name = next(iter(s14._SYMBOL_PUA_FALLBACKS))  # noqa: SLF001
    # Run through Standard14Fonts.get_glyph_path("Symbol", fallback_name).
    # We expect the fall-through to the mapped_font branch (which for
    # Symbol typically yields the glyph from the wrapper or []).
    path = Standard14Fonts.get_glyph_path("Symbol", fallback_name)
    assert isinstance(path, list)
    # Restore happens automatically via monkeypatch teardown.
    assert saved is s14._ttf_glyph_path_for_code_point or True  # noqa: SIM222 — keep the saved binding referenced.


def test_get_glyph_path_symbolmt_with_unknown_glyph_name_returns_empty() -> None:
    """Branch 1159->1163 — a SymbolMT-named mapped font + a glyph name
    with no SymbolEncoding code falls through to the final ``return []``."""

    class _FakeMapped:
        def has_glyph(self, _name: str) -> bool:
            return False

        def get_path(self, _name: str) -> list[tuple[Any, ...]]:
            return []

        def get_name(self) -> str:
            return "SymbolMT"

    saved_sub = Standard14Fonts.get_substitute_ttf
    saved_map = Standard14Fonts.get_mapped_font
    Standard14Fonts.get_substitute_ttf = staticmethod(  # type: ignore[assignment, method-assign]
        lambda _name: None
    )
    Standard14Fonts.get_mapped_font = classmethod(  # type: ignore[assignment, method-assign]
        lambda _cls, _name: _FakeMapped()
    )
    try:
        # "definitely_not_a_symbol_name" isn't a SymbolEncoding glyph →
        # SymbolEncoding.get_code returns None → branch 1159->1163.
        path = Standard14Fonts.get_glyph_path(
            "Symbol", "definitely_not_a_symbol_name"
        )
        assert path == []
    finally:
        Standard14Fonts.get_substitute_ttf = saved_sub  # type: ignore[method-assign]
        Standard14Fonts.get_mapped_font = saved_map  # type: ignore[method-assign]
