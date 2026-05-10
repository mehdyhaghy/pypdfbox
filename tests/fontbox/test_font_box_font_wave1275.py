"""Wave 1275 — FontBoxFont.get_font_b_box helper parity."""

from __future__ import annotations

from pypdfbox.fontbox.font_box_font import FontBoxFont, get_font_b_box


class _FontWithBBox:
    """Minimal duck-typed FontBoxFont that exposes the contracted spelling only."""

    def get_name(self) -> str:
        return "X"

    def get_font_bbox(self) -> tuple[float, float, float, float]:
        return (-1.0, -2.0, 3.0, 4.0)

    def get_font_matrix(self) -> list[float]:
        return [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]

    def get_path(self, name: str) -> list[tuple[str, ...]]:
        return []

    def get_width(self, name: str) -> float:
        return 1.0

    def has_glyph(self, name: str) -> bool:
        return False


class _FontWithStrictBBox(_FontWithBBox):
    """Concrete font that prefers the strict spelling and overrides it."""

    def get_font_b_box(self) -> tuple[float, float, float, float]:
        return (10.0, 20.0, 30.0, 40.0)


def test_helper_dispatches_to_get_font_bbox_when_strict_absent() -> None:
    f = _FontWithBBox()
    assert isinstance(f, FontBoxFont)
    assert get_font_b_box(f) == (-1.0, -2.0, 3.0, 4.0)


def test_helper_prefers_strict_spelling_when_present() -> None:
    f = _FontWithStrictBBox()
    assert isinstance(f, FontBoxFont)
    # Strict override wins over the contracted accessor.
    assert get_font_b_box(f) == (10.0, 20.0, 30.0, 40.0)
