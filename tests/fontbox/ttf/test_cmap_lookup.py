from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.cmap_lookup import CmapLookup


def test_cmap_lookup_is_abstract_cannot_instantiate() -> None:
    with pytest.raises(TypeError):
        CmapLookup()  # type: ignore[abstract]


def test_cmap_lookup_subclass_missing_get_char_codes_cannot_instantiate() -> None:
    class Partial(CmapLookup):
        def get_glyph_id(self, code_point_at: int) -> int:  # noqa: ARG002
            return 0

    with pytest.raises(TypeError):
        Partial()  # type: ignore[abstract]


def test_cmap_lookup_subclass_missing_get_glyph_id_cannot_instantiate() -> None:
    class Partial(CmapLookup):
        def get_char_codes(self, gid: int) -> list[int] | None:  # noqa: ARG002
            return None

    with pytest.raises(TypeError):
        Partial()  # type: ignore[abstract]


def test_cmap_lookup_complete_subclass_can_instantiate() -> None:
    class Complete(CmapLookup):
        def get_glyph_id(self, code_point_at: int) -> int:
            return code_point_at + 1

        def get_char_codes(self, gid: int) -> list[int] | None:
            return [gid - 1] if gid > 0 else None

    inst = Complete()
    assert inst.get_glyph_id(65) == 66
    assert inst.get_char_codes(66) == [65]
    assert inst.get_char_codes(0) is None


def test_cmap_lookup_method_signatures_documented() -> None:
    # The abstract methods must exist on the class.
    assert hasattr(CmapLookup, "get_glyph_id")
    assert hasattr(CmapLookup, "get_char_codes")
    # Both must be marked abstract.
    assert "get_glyph_id" in CmapLookup.__abstractmethods__
    assert "get_char_codes" in CmapLookup.__abstractmethods__
