from __future__ import annotations

from pypdfbox.text import PDFTextStripperByArea


class _DuckRectangle:
    def get_lower_left_x(self) -> int:
        return 10

    def get_lower_left_y(self) -> str:
        return "20"

    def get_upper_right_x(self) -> float:
        return 30.5

    def get_upper_right_y(self) -> float:
        return 40.25


def test_wave806_add_region_accepts_duck_typed_pdrectangle() -> None:
    stripper = PDFTextStripperByArea()

    stripper.add_region("duck", _DuckRectangle())

    assert stripper.get_regions() == ["duck"]
    assert stripper._region_area["duck"] == (10.0, 20.0, 30.5, 40.25)
