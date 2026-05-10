"""Hand-written tests for the :class:`GlyphArraySplitter` interface."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.gsub import GlyphArraySplitter


def test_abstract_base_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        GlyphArraySplitter()  # type: ignore[abstract]
