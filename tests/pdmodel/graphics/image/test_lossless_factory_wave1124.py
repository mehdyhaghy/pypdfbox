from __future__ import annotations

import pytest

from tests.pdmodel.graphics.image import test_lossless_factory


def test_wave1124_static_factory_guard_failure_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class InstantiableFactory:
        pass

    monkeypatch.setattr(test_lossless_factory, "LosslessFactory", InstantiableFactory)

    with pytest.raises(AssertionError, match="LosslessFactory\\(\\) should raise TypeError"):
        test_lossless_factory.test_static_factory_cannot_be_instantiated()
