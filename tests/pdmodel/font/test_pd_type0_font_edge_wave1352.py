"""Wave 1352 — PDType0Font: descendant-method-missing guards and the
``add_glyphs_to_subset`` pinning branch.

Targets the under-covered defensive branches in
``pypdfbox/pdmodel/font/pd_type0_font.py``:

* line 856 — ``get_path`` short-circuits when the descendant lacks a
  callable ``get_glyph_path`` attribute;
* line 873 — ``get_normalized_path`` same guard for
  ``get_normalized_path``;
* line 900 — ``get_cmap_lookup`` short-circuits when the descendant is
  not a ``PDCIDFontType2``;
* lines 908-917 — ``get_cmap_lookup`` exception + fontTools fallback +
  ``"cmap"`` missing + ``getBestCmap`` raising;
* line 949 — ``has_explicit_width`` returns ``False`` when descendant
  lacks the accessor;
* line 952 — same path for a non-callable attribute;
* line 1464 — ``subset()`` honours ``_subset_glyph_ids`` and forwards
  the registered raw GIDs to the subsetter.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.font import pd_type0_font as type0_module
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

# ---------- get_path / get_normalized_path guards ------------------------


class _BareDescendant:
    """Descendant that exposes neither ``get_glyph_path`` nor
    ``get_normalized_path``. ``code_to_cid`` on the parent is
    monkey-patched so we never reach the accessor call."""


def test_get_path_returns_empty_when_descendant_lacks_callable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 856: ``getattr(descendant, "get_glyph_path", None)`` returns
    a non-callable (here, ``None``) — accessor short-circuits to ``[]``.
    """
    font = PDType0Font()
    descendant = _BareDescendant()
    # Set the attribute to a non-callable to exercise the ``not callable``
    # branch specifically (rather than the missing-attr default).
    descendant.get_glyph_path = "not-callable"  # type: ignore[attr-defined]
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    monkeypatch.setattr(font, "code_to_cid", lambda code: code)
    assert font.get_path(0x41) == []


def test_get_normalized_path_returns_empty_when_descendant_lacks_callable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 873: same defensive guard for ``get_normalized_path``."""
    font = PDType0Font()
    descendant = _BareDescendant()
    descendant.get_normalized_path = 42  # type: ignore[attr-defined]
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    monkeypatch.setattr(font, "code_to_cid", lambda code: code)
    assert font.get_normalized_path(0x41) == []


# ---------- get_cmap_lookup branches -------------------------------------


def test_get_cmap_lookup_returns_none_for_non_cid_type2_descendant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 900: descendant is not a ``PDCIDFontType2`` — accessor bails
    out with ``None`` (CIDFontType0 is the realistic non-Type2 case)."""
    from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0

    font = PDType0Font()
    cid0 = PDCIDFontType0(COSDictionary())
    monkeypatch.setattr(font, "get_descendant_font", lambda: cid0)
    assert font.get_cmap_lookup() is None


def test_get_cmap_lookup_returns_none_when_unicode_lookup_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 906-909: descendant's TTF has ``get_unicode_cmap_lookup``
    but it raises — caller swallows and returns ``None``."""

    class _RaisingTTF:
        def get_unicode_cmap_lookup(self) -> Any:
            raise RuntimeError("broken cmap")

    descendant = PDCIDFontType2(COSDictionary())
    monkeypatch.setattr(descendant, "get_true_type_font", lambda: _RaisingTTF())
    font = PDType0Font()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    assert font.get_cmap_lookup() is None


def test_get_cmap_lookup_falls_back_to_font_tools_best_cmap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 910-915: descendant's TTF has no ``get_unicode_cmap_lookup``
    method; we fall back to ``_tt["cmap"].getBestCmap()``."""
    from types import SimpleNamespace

    class _InnerTT(dict):
        pass

    inner = _InnerTT(
        cmap=SimpleNamespace(getBestCmap=lambda: {0x41: "A"}),
    )
    ttf = SimpleNamespace(_tt=inner)
    descendant = PDCIDFontType2(COSDictionary())
    monkeypatch.setattr(descendant, "get_true_type_font", lambda: ttf)
    font = PDType0Font()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    assert font.get_cmap_lookup() == {0x41: "A"}


def test_get_cmap_lookup_returns_none_when_inner_tt_missing_cmap_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 911-913: ``_tt`` is present but the ``cmap`` key isn't —
    short-circuit to ``None``."""
    from types import SimpleNamespace

    ttf = SimpleNamespace(_tt={})  # no "cmap" key
    descendant = PDCIDFontType2(COSDictionary())
    monkeypatch.setattr(descendant, "get_true_type_font", lambda: ttf)
    font = PDType0Font()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    assert font.get_cmap_lookup() is None


def test_get_cmap_lookup_returns_none_when_inner_tt_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 911-913: ``_tt`` is ``None`` — same short-circuit branch
    via the first half of the ``or`` short-circuit."""
    from types import SimpleNamespace

    ttf = SimpleNamespace(_tt=None)
    descendant = PDCIDFontType2(COSDictionary())
    monkeypatch.setattr(descendant, "get_true_type_font", lambda: ttf)
    font = PDType0Font()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    assert font.get_cmap_lookup() is None


def test_get_cmap_lookup_returns_none_when_get_best_cmap_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lines 914-917: ``getBestCmap`` raises ``KeyError`` /
    ``AttributeError`` — caller swallows and returns ``None``."""
    from types import SimpleNamespace

    def boom() -> dict[int, str]:
        raise AttributeError("missing")

    inner = {"cmap": SimpleNamespace(getBestCmap=boom)}
    ttf = SimpleNamespace(_tt=inner)
    descendant = PDCIDFontType2(COSDictionary())
    monkeypatch.setattr(descendant, "get_true_type_font", lambda: ttf)
    font = PDType0Font()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    assert font.get_cmap_lookup() is None


# ---------- has_explicit_width descendant-missing guards -----------------


def test_has_explicit_width_returns_false_without_descendant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 949: descendant is ``None`` — accessor returns ``False``."""
    font = PDType0Font()
    monkeypatch.setattr(font, "get_descendant_font", lambda: None)
    assert font.has_explicit_width(65) is False


def test_has_explicit_width_returns_false_when_descendant_lacks_callable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 952: ``has_explicit_width`` on descendant is non-callable."""
    font = PDType0Font()
    descendant = _BareDescendant()
    descendant.has_explicit_width = "not-callable"  # type: ignore[attr-defined]
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    assert font.has_explicit_width(65) is False


# ---------- subset() honours add_glyphs_to_subset ------------------------


def test_subset_forwards_pinned_glyph_ids_to_subsetter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Line 1464: when ``_subset_glyph_ids`` is non-empty, the subset
    builder must call ``subsetter.add_glyph_ids`` with the registered
    raw GIDs (matches upstream ``PDCIDFontType2Embedder.addGlyphIds``).
    """
    from pypdfbox.fontbox import ttf as ttf_module
    from pypdfbox.pdmodel.font import pd_true_type_font

    captured: dict[str, Any] = {}

    class _Subsetter:
        def __init__(self, ttf: object) -> None:
            captured["ttf"] = ttf

        def add_all(self, codepoints: set[int]) -> None:
            captured["codepoints"] = codepoints

        def add_glyph_ids(self, glyph_ids: set[int]) -> None:
            captured["glyph_ids"] = set(glyph_ids)

        def set_prefix(self, prefix: str) -> None:
            captured["prefix"] = prefix

        def to_bytes(self) -> bytes:
            return b"subset-bytes-with-pinned-gids"

    descendant = PDCIDFontType2(COSDictionary())
    descendant._ttf = object()  # noqa: SLF001
    monkeypatch.setattr(descendant, "get_true_type_font", lambda: descendant._ttf)
    monkeypatch.setattr(ttf_module, "TTFSubsetter", _Subsetter)
    monkeypatch.setattr(
        pd_true_type_font,
        "_embed_subset_bytes",
        lambda desc, data, tag: captured.update(embed=(desc, data, tag)),
    )

    font = PDType0Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "BasePS")
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)

    # Mark the font as subsettable and register raw glyph IDs.
    font._will_be_subset = True  # noqa: SLF001
    font.add_glyphs_to_subset([3, 7, 11])

    result = font.subset("A", prefix="GIDPIN")
    assert result == b"subset-bytes-with-pinned-gids"
    # Exercises line 1464: the pinned set must reach the subsetter.
    assert captured["glyph_ids"] == {3, 7, 11}
    # After subset the pinned set is cleared (see line 1491).
    assert font._subset_glyph_ids == set()  # noqa: SLF001


def test_add_glyphs_to_subset_raises_when_subsetting_disabled() -> None:
    """Companion guard test for ``add_glyphs_to_subset``: matches
    upstream's ``IllegalStateException``."""
    font = PDType0Font()
    font._will_be_subset = False  # noqa: SLF001
    with pytest.raises(RuntimeError, match="created with subsetting disabled"):
        font.add_glyphs_to_subset([1, 2])


def test_pd_type0_font_module_exports_type0_font() -> None:
    """Sanity touch on the module export so the imports above stay
    pinned to the module path under test (defensive — keeps the test
    file's intent readable)."""
    assert type0_module.PDType0Font is PDType0Font
