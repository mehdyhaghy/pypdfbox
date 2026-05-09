from __future__ import annotations

import pytest

from tests.fontbox.cff import test_cff_tail_wave785 as cff_tail


def test_fdselect_fonttools_test_doubles_direct_methods() -> None:
    assert len(cff_tail._KeyErrorFDSelect()) == 2
    assert cff_tail._BadLengthFDSelect()[0] == 1

    with pytest.raises(KeyError):
        cff_tail._KeyErrorFDSelect()[0]
