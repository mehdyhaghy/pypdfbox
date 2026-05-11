"""Tests for :mod:`pypdfbox.pdmodel.font.pd_true_type_font_embedder`.

We test the surface that doesn't require a real TTF:

* The class refuses to ``build_subset`` (raises) — upstream throws
  ``UnsupportedOperationException``.

A full embedding round-trip needs a fixture; that path is exercised by
:class:`PDTrueTypeFont` integration tests rather than here.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.font.pd_true_type_font_embedder import PDTrueTypeFontEmbedder


def test_build_subset_raises_unsupported() -> None:
    # We can't easily build a real embedder without a TTF — but we can
    # bypass __init__ and check the abstract-method override directly.
    obj = object.__new__(PDTrueTypeFontEmbedder)
    with pytest.raises(NotImplementedError):
        obj.build_subset(b"", "ABCDEF+", {})  # type: ignore[arg-type]
