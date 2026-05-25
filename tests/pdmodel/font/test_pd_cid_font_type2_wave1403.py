"""Wave 1403 branch-closure tests for
:meth:`PDCIDFontType2.encode`.

Closes the untested *false* sides of the parent-type / cmap / ToUnicode
conditionals in ``encode`` (source lines 706-732):

* ``706->710`` / ``715->720`` / ``724->732`` — an *embedded* font whose
  ``parent`` is **not** a :class:`PDType0Font`: ``parent_cmap_name``
  stays ``None``, the Identity- branch is skipped, neither ``elif
  isinstance(parent, PDType0Font)`` fires, and the ToUnicode fallback's
  ``isinstance`` guard is also false — so ``cid`` stays -1 and the
  method raises.
* ``713->720`` — Identity- parent CMap but the TTF exposes **no** unicode
  cmap subtable, so the ``if cmap_subtable is not None`` guard is false.
* ``730->732`` — Identity- parent, cmap returns notdef, ToUnicode CMap is
  present but ``get_codes_from_unicode`` returns ``None`` for the char.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font


class _FakeCmapSubtable:
    def __init__(self, mapping: dict[int, int]) -> None:
        self._mapping = mapping

    def get_glyph_id(self, codepoint: int) -> int:
        return self._mapping.get(codepoint, 0)


class _FakeCmap:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeToUnicodeCmap:
    def __init__(self, mapping: dict[str, bytes]) -> None:
        self._mapping = mapping

    def get_codes_from_unicode(self, s: str) -> bytes | None:
        return self._mapping.get(s)


def _stub_ttf(cmap_mapping: dict[int, int] | None) -> Any:
    class _StubTTF:
        def get_unicode_cmap_subtable(self) -> Any:
            return (
                _FakeCmapSubtable(cmap_mapping) if cmap_mapping is not None else None
            )

    return _StubTTF()


def _embedded_font_with_ttf(cmap_mapping: dict[int, int] | None) -> PDCIDFontType2:
    font = PDCIDFontType2()
    stub_ttf = _stub_ttf(cmap_mapping)
    font.get_true_type_font = lambda: stub_ttf  # type: ignore[assignment,method-assign,return-value]
    font.is_embedded = lambda: True  # type: ignore[assignment,method-assign,return-value]
    return font


# ---------- 706->710 / 715->720 / 724->732 : non-PDType0Font parent ----------


def test_encode_embedded_non_type0_parent_raises_and_skips_all_parent_branches() -> None:
    """Embedded font whose parent is not a PDType0Font.

    ``parent_cmap_name`` stays None (706 false → 710), the Identity-
    branch is skipped, ``elif isinstance(parent, PDType0Font)`` is false
    (715 false → 720), and the ToUnicode fallback's ``isinstance`` guard
    is also false (724 false → 732). ``cid`` is never set above -1, so
    the final guard raises.
    """
    font = _embedded_font_with_ttf(cmap_mapping={ord("A"): 0x41})
    # A non-PDType0Font parent object.
    font._parent = object()  # noqa: SLF001
    with pytest.raises(ValueError, match="No glyph"):
        font.encode(ord("A"))


# ---------- 713->720 : Identity- parent CMap but no unicode subtable ----------


def test_encode_identity_parent_with_no_cmap_subtable_skips_glyph_lookup() -> None:
    """Identity-H parent CMap but the TTF has no unicode cmap subtable
    (``cmap_mapping=None`` → subtable None): ``if cmap_subtable is not
    None`` is false (713 → 720), ``cid`` stays -1, ToUnicode is absent,
    and the method raises."""

    class _StubParent(PDType0Font):
        def get_cmap(self) -> Any:  # type: ignore[override]
            return _FakeCmap("Identity-H")

        def get_cmap_ucs2(self) -> Any:  # type: ignore[override]
            return None

        def get_to_unicode_cmap(self) -> Any:  # type: ignore[override]
            return None

    font = _embedded_font_with_ttf(cmap_mapping=None)
    font._parent = _StubParent()  # noqa: SLF001
    with pytest.raises(ValueError, match="No glyph"):
        font.encode(ord("A"))


# ---------- 730->732 : ToUnicode present but no codes for the char ----------


def test_encode_to_unicode_present_but_returns_none_falls_through() -> None:
    """Identity- parent, cmap returns notdef (cid==0), ToUnicode CMap is
    present but ``get_codes_from_unicode`` returns None for the codepoint
    (730 false → 732). ``cid`` is then forced to 0 and the method raises.
    """

    class _StubParent(PDType0Font):
        def get_cmap(self) -> Any:  # type: ignore[override]
            return _FakeCmap("Identity-H")

        def get_cmap_ucs2(self) -> Any:  # type: ignore[override]
            return None

        def get_to_unicode_cmap(self) -> Any:  # type: ignore[override]
            # Maps a *different* char, so the requested one yields None.
            return _FakeToUnicodeCmap({"Z": b"\x00\x01"})

    font = _embedded_font_with_ttf(cmap_mapping={ord("C"): 0})
    font._parent = _StubParent()  # noqa: SLF001
    with pytest.raises(ValueError, match="No glyph"):
        font.encode(ord("C"))
