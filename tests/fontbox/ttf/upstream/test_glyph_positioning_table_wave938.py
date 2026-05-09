from __future__ import annotations

from pathlib import Path

import pytest

from . import test_glyph_positioning_table as gpos_tests


def test_wave938_gpos_fixture_missing_skip_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gpos_tests, "FIXTURE", Path("/missing/LiberationSans-Regular.ttf"))

    with pytest.raises(pytest.skip.Exception, match="Fixture font not present"):
        gpos_tests.test_get_gpos_data()
    with pytest.raises(pytest.skip.Exception, match="Fixture font not present"):
        gpos_tests.test_gpos_lookup_list_breadth()
    with pytest.raises(pytest.skip.Exception, match="Fixture font not present"):
        gpos_tests.test_gpos_kern_feature_lookup_indices_are_pair_adjustment()

