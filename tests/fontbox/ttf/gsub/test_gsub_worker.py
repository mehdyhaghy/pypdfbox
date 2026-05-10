"""Tests for the :class:`GsubWorker` abstract base."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.gsub.gsub_worker import GsubWorker


def test_gsub_worker_is_abstract() -> None:
    """``GsubWorker`` cannot be instantiated without implementing apply_transforms."""
    with pytest.raises(TypeError):
        GsubWorker()  # type: ignore[abstract]


def test_concrete_subclass_implements_apply_transforms() -> None:
    """A trivial subclass that overrides ``apply_transforms`` is constructible."""

    class _Identity(GsubWorker):
        def apply_transforms(self, original_glyph_ids: list[int]) -> list[int]:
            return list(original_glyph_ids)

    worker = _Identity()
    assert worker.apply_transforms([1, 2, 3]) == [1, 2, 3]


def test_missing_apply_transforms_blocks_instantiation() -> None:
    class _Bad(GsubWorker):
        pass

    with pytest.raises(TypeError):
        _Bad()  # type: ignore[abstract]
