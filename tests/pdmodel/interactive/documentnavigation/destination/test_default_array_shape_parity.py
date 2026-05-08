from __future__ import annotations

from pypdfbox.cos import COSNull
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageDestination,
    PDPageFitBoundingBoxHeightDestination,
    PDPageFitBoundingBoxWidthDestination,
    PDPageFitHeightDestination,
    PDPageFitRectangleDestination,
    PDPageFitWidthDestination,
    PDPageXYZDestination,
)


def test_default_coordinate_destinations_grow_optional_slots_to_null() -> None:
    cases: list[tuple[PDPageDestination, int, tuple[int, ...]]] = [
        (PDPageXYZDestination(), 5, (2, 3, 4)),
        (PDPageFitRectangleDestination(), 6, (2, 3, 4, 5)),
        (PDPageFitWidthDestination(), 3, (2,)),
        (PDPageFitHeightDestination(), 3, (2,)),
        (PDPageFitBoundingBoxWidthDestination(), 3, (2,)),
        (PDPageFitBoundingBoxHeightDestination(), 3, (2,)),
    ]

    for destination, expected_size, optional_slots in cases:
        array = destination.get_cos_array()

        assert array.size() == expected_size
        for slot in optional_slots:
            assert array.get(slot) is COSNull.NULL
