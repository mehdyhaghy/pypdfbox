"""Sanity tests for the font-loading examples.

Both ``HelloWorldTTF`` and ``HelloWorldType1`` expect a real font file —
we only validate the usage gate here so the tests don't depend on an
external asset.
"""

from __future__ import annotations

import pytest

from pypdfbox.examples.pdmodel.hello_world_ttf import HelloWorldTTF
from pypdfbox.examples.pdmodel.hello_world_type1 import HelloWorldType1


def test_hello_world_ttf_usage() -> None:
    with pytest.raises(SystemExit):
        HelloWorldTTF.main([])


def test_hello_world_ttf_main_requires_real_ttf(tmp_path) -> None:
    out = tmp_path / "out.pdf"
    # Missing font file → opening it raises OSError / FileNotFoundError;
    # we accept any IO-shaped failure.
    with pytest.raises(OSError):
        HelloWorldTTF.main([str(out), "msg", str(tmp_path / "missing.ttf")])


def test_hello_world_type1_usage() -> None:
    with pytest.raises(SystemExit):
        HelloWorldType1.main([])


def test_hello_world_type1_main_requires_real_pfb(tmp_path) -> None:
    out = tmp_path / "out.pdf"
    with pytest.raises(OSError):
        HelloWorldType1.main([str(out), "msg", str(tmp_path / "missing.pfb")])
