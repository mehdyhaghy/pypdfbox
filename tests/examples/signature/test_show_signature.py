"""Tests for ``ShowSignature``."""

from __future__ import annotations

import pytest

from pypdfbox.examples.signature.show_signature import ShowSignature


def test_construction():
    show = ShowSignature()
    assert show._results == []


def test_show_signature_raises_on_missing_file(tmp_path):
    show = ShowSignature()
    with pytest.raises(FileNotFoundError):
        show.show_signature(None, tmp_path / "missing.pdf")
