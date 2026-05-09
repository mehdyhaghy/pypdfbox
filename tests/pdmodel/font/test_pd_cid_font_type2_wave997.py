from __future__ import annotations

import pytest

from tests.pdmodel.font.test_pd_cid_font_type2_wave599 import (
    _BrokenAdvanceTTF,
    _PathTable,
)


def test_wave997_broken_advance_units_per_em_helper_is_exercised() -> None:
    assert _BrokenAdvanceTTF().get_units_per_em() == 1000


def test_wave997_path_table_rejects_unknown_gid() -> None:
    with pytest.raises(KeyError, match="2"):
        _PathTable().getGlyphName(2)
