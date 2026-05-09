from __future__ import annotations

from collections.abc import Callable

import pytest

from tests.fontbox.ttf import test_digital_signature_table as dsig_mod


class _MissingFixture:
    def exists(self) -> bool:
        return False


@pytest.mark.parametrize(
    "test_func",
    [
        dsig_mod.test_get_dsig_returns_none_when_absent,
        dsig_mod.test_get_dsig_caches_negative_result,
        dsig_mod.test_get_dsig_reads_synthetic_table,
        dsig_mod.test_get_dsig_caches_positive_result,
    ],
)
def test_wave884_fixture_dependent_tests_skip_when_ttf_fixture_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    test_func: Callable[[], None],
) -> None:
    monkeypatch.setattr(dsig_mod, "_FIXTURE", _MissingFixture())

    with pytest.raises(pytest.skip.Exception):
        test_func()
