"""Hand-written tests for the fontbox base protocols.

Covers :class:`pypdfbox.fontbox.FontBoxFont` and
:class:`pypdfbox.fontbox.EncodedFont` — the two ``Protocol``-modeled
upstream interfaces.
"""

from __future__ import annotations

from pypdfbox.fontbox import EncodedFont, FontBoxFont


# ---------- FontBoxFont protocol ------------------------------------------


class _MinimalFont:
    """Minimal duck-typed implementation of the FontBoxFont surface."""

    def get_name(self) -> str | None:
        return "MyFont"

    def get_font_bbox(self) -> tuple[float, float, float, float]:
        return (-100.0, -200.0, 1000.0, 900.0)

    def get_font_matrix(self) -> list[float]:
        return [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]

    def get_path(self, name: str) -> list[tuple[str, tuple[float, ...]]]:
        return []

    def get_width(self, name: str) -> float:
        return 500.0

    def has_glyph(self, name: str) -> bool:
        return name == "A"


def test_font_box_font_is_runtime_checkable() -> None:
    # @runtime_checkable means isinstance must work without raising.
    f = _MinimalFont()
    assert isinstance(f, FontBoxFont)


def test_font_box_font_rejects_missing_methods() -> None:
    class Incomplete:
        # Only implements two of the six required methods.
        def get_name(self) -> str:
            return "x"

        def get_width(self, name: str) -> float:
            return 0.0

    assert not isinstance(Incomplete(), FontBoxFont)


def test_font_box_font_accepts_concrete_pypdfbox_font() -> None:
    # Type1Font already implements the full FontBoxFont surface; this
    # confirms the duck-typed protocol is satisfied without inheritance.
    from pypdfbox.fontbox.type1.type1_font import Type1Font

    font = Type1Font()
    assert isinstance(font, FontBoxFont)


def test_minimal_font_round_trip_values() -> None:
    f = _MinimalFont()
    assert f.get_name() == "MyFont"
    assert f.get_font_bbox() == (-100.0, -200.0, 1000.0, 900.0)
    assert f.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
    assert f.get_path("A") == []
    assert f.get_width("A") == 500.0
    assert f.has_glyph("A") is True
    assert f.has_glyph("Z") is False


# ---------- EncodedFont protocol ------------------------------------------


class _EncodedDummy:
    def get_encoding(self) -> dict[int, str]:
        return {65: "A"}


def test_encoded_font_is_runtime_checkable() -> None:
    assert isinstance(_EncodedDummy(), EncodedFont)


def test_encoded_font_rejects_missing_method() -> None:
    class NoEncoding:
        def get_name(self) -> str:
            return "x"

    assert not isinstance(NoEncoding(), EncodedFont)


def test_encoded_font_accepts_type1_font() -> None:
    # Type1Font implements EncodedFont upstream and ports the surface.
    from pypdfbox.fontbox.type1.type1_font import Type1Font

    font = Type1Font()
    assert isinstance(font, EncodedFont)


def test_encoded_font_accepts_cff_type1_font() -> None:
    # CFFType1Font also implements EncodedFont upstream.
    from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font

    font = CFFType1Font()
    assert isinstance(font, EncodedFont)


def test_encoded_font_independent_of_font_box_font() -> None:
    # A font may satisfy EncodedFont without satisfying FontBoxFont and
    # vice versa — the two protocols should not transitively imply each
    # other in the runtime check.
    encoded_only = _EncodedDummy()
    assert isinstance(encoded_only, EncodedFont)
    assert not isinstance(encoded_only, FontBoxFont)

    fontbox_only = _MinimalFont()
    assert isinstance(fontbox_only, FontBoxFont)
    assert not isinstance(fontbox_only, EncodedFont)
