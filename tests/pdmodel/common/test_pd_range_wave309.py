from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat
from pypdfbox.pdmodel.common import PDRange


def test_negative_starting_index_constructor_is_rejected() -> None:
    array = COSArray(
        [COSFloat(0.0), COSFloat(1.0), COSFloat(10.0), COSFloat(20.0)]
    )

    with pytest.raises(ValueError, match="non-negative"):
        PDRange(array, -1)


def test_negative_starting_index_setter_leaves_current_pair_unchanged() -> None:
    array = COSArray(
        [COSFloat(0.0), COSFloat(1.0), COSFloat(10.0), COSFloat(20.0)]
    )
    rng = PDRange(array, 1)

    with pytest.raises(ValueError, match="non-negative"):
        rng.set_starting_index(-1)

    assert rng.get_starting_index() == 1
    assert rng.as_tuple() == (10.0, 20.0)
