"""Tests for :mod:`pypdfbox.pdmodel.font.uni_util`.

No upstream JUnit test exists — :class:`UniUtil` is package-private and
exercised only through font-name generation. We cover all four
length-branches of the upstream switch ladder.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.font.uni_util import UniUtil, get_uni_name_of_code_point


def test_length_one_pads_to_four() -> None:
    # ``hex.length() == 1`` branch (UniUtil.java line 37).
    assert get_uni_name_of_code_point(0x1) == "uni0001"
    assert get_uni_name_of_code_point(0xA) == "uni000A"


def test_length_two_pads_to_four() -> None:
    # ``hex.length() == 2`` branch (UniUtil.java line 39).
    assert get_uni_name_of_code_point(0x10) == "uni0010"
    assert get_uni_name_of_code_point(0xFF) == "uni00FF"


def test_length_three_pads_to_four() -> None:
    # ``hex.length() == 3`` branch (UniUtil.java line 41).
    assert get_uni_name_of_code_point(0x100) == "uni0100"
    assert get_uni_name_of_code_point(0xFFF) == "uni0FFF"


def test_length_four_passes_through() -> None:
    # ``default`` branch (UniUtil.java line 43).
    assert get_uni_name_of_code_point(0x1000) == "uni1000"
    assert get_uni_name_of_code_point(0xFFFF) == "uniFFFF"


def test_supplementary_plane_no_truncation() -> None:
    # Upstream uses ``Integer.toString(codePoint, 16).toUpperCase`` which
    # handles >0xFFFF naturally — verify pypdfbox does the same.
    assert get_uni_name_of_code_point(0x10000) == "uni10000"
    assert get_uni_name_of_code_point(0x2F884) == "uni2F884"


def test_namespace_class_static_method() -> None:
    assert UniUtil.get_uni_name_of_code_point(0xAB) == "uni00AB"


def test_namespace_class_rejects_instantiation() -> None:
    # Upstream constructor is private; pypdfbox raises TypeError.
    with pytest.raises(TypeError):
        UniUtil()
