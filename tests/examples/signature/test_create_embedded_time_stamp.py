"""Tests for ``CreateEmbeddedTimeStamp``."""

from __future__ import annotations

import pytest

from pypdfbox.examples.signature.create_embedded_time_stamp import (
    CreateEmbeddedTimeStamp,
)


def test_construction():
    inst = CreateEmbeddedTimeStamp("http://tsa.test.invalid")
    assert inst._tsa_url == "http://tsa.test.invalid"


def test_missing_file_raises(tmp_path):
    inst = CreateEmbeddedTimeStamp("http://tsa.test.invalid")
    with pytest.raises(FileNotFoundError):
        inst.embed_time_stamp(tmp_path / "does-not-exist.pdf")
