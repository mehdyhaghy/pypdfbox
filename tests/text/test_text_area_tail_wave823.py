from __future__ import annotations

from pypdfbox.text import PDFTextStripperByArea


class _RectangleLike:
    def get_lower_left_x(self) -> str:
        return "1.25"

    def get_lower_left_y(self) -> int:
        return 2

    def get_upper_right_x(self) -> float:
        return 30.5

    def get_upper_right_y(self) -> str:
        return "40.75"


def test_wave823_add_region_accepts_pdrectangle_like_accessors() -> None:
    stripper = PDFTextStripperByArea()

    stripper.add_region("duck", _RectangleLike())

    assert stripper.get_regions() == ["duck"]
    assert stripper._region_area["duck"] == (1.25, 2.0, 30.5, 40.75)
