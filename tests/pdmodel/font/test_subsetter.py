"""Tests for :mod:`pypdfbox.pdmodel.font.subsetter`.

The upstream type is a package-private interface — no JUnit tests
exist. We verify the ABC shape so subclasses can't elide the two
methods.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.font.subsetter import Subsetter


def test_cannot_instantiate_abc_directly() -> None:
    with pytest.raises(TypeError):
        Subsetter()  # type: ignore[abstract]


def test_concrete_subclass_works() -> None:
    class _Sub(Subsetter):
        def __init__(self) -> None:
            self.added: list[int] = []
            self.subset_called = False

        def add_to_subset(self, code_point: int) -> None:
            self.added.append(code_point)

        def subset(self) -> None:
            self.subset_called = True

    s = _Sub()
    s.add_to_subset(65)
    s.add_to_subset(66)
    s.subset()
    assert s.added == [65, 66]
    assert s.subset_called


def test_abstract_methods_must_both_be_overridden() -> None:
    class _Partial(Subsetter):
        def add_to_subset(self, code_point: int) -> None:
            del code_point
        # missing subset() — instantiation must fail.

    with pytest.raises(TypeError):
        _Partial()  # type: ignore[abstract]
