"""Tests for :mod:`pypdfbox.pdmodel.font.fs_font_info`.

No upstream JUnit test exists — :class:`FSFontInfo` is a private inner
class. We cover the :class:`FontInfo` accessors and the lazy ``get_font``
loader's null-on-error contract.
"""

from __future__ import annotations

import pathlib
from typing import Any

import pytest

from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.pdmodel.font.cid_system_info import CIDSystemInfo
from pypdfbox.pdmodel.font.fs_font_info import FSFontInfo


@pytest.fixture
def info(tmp_path: pathlib.Path) -> FSFontInfo:
    # Use a non-existent path — we only need the metadata accessors,
    # not the lazy ``get_font`` path (which would try to parse).
    path = tmp_path / "fake.ttf"
    path.write_bytes(b"\0\0\0\0")
    return FSFontInfo(
        file=path,
        font_format=FontFormat.TTF,
        post_script_name="FakeFont",
        cid_system_info=CIDSystemInfo("Adobe", "Identity", 0),
        us_weight_class=400,
        s_family_class=0x0801,
        ul_code_page_range1=1,
        ul_code_page_range2=2,
        mac_style=4,
        panose=b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09",
        parent=None,
        font_hash="abc123",
        last_modified=1700000000,
    )


def test_post_script_name(info: FSFontInfo) -> None:
    assert info.get_post_script_name() == "FakeFont"


def test_format(info: FSFontInfo) -> None:
    assert info.get_format() is FontFormat.TTF


def test_cid_system_info(info: FSFontInfo) -> None:
    cid = info.get_cid_system_info()
    assert cid is not None
    assert cid.get_registry() == "Adobe"


def test_metadata_accessors(info: FSFontInfo) -> None:
    assert info.get_weight_class() == 400
    assert info.get_family_class() == 0x0801
    assert info.get_code_page_range1() == 1
    assert info.get_code_page_range2() == 2
    assert info.get_mac_style() == 4


def test_panose_built_when_bytes_present(info: FSFontInfo) -> None:
    panose = info.get_panose()
    assert panose is not None


def test_panose_none_when_too_short(tmp_path: pathlib.Path) -> None:
    info = FSFontInfo(
        file=tmp_path / "x.ttf",
        font_format=FontFormat.TTF,
        post_script_name="X",
        cid_system_info=None,
        us_weight_class=0,
        s_family_class=0,
        ul_code_page_range1=0,
        ul_code_page_range2=0,
        mac_style=0,
        panose=b"\x00\x01",  # too short
        parent=None,
        font_hash="",
        last_modified=0,
    )
    assert info.get_panose() is None


def test_file_path_attribute(info: FSFontInfo, tmp_path: pathlib.Path) -> None:
    assert info.file == tmp_path / "fake.ttf"


def test_str_includes_path_and_hash(info: FSFontInfo) -> None:
    text = str(info)
    assert "FakeFont" in text
    assert "abc123" in text


def test_get_font_returns_none_for_invalid_file(info: FSFontInfo) -> None:
    # The fake bytes are not a parseable TTF; loader returns None.
    assert info.get_font() is None


def test_get_font_with_parent_cache_hit(
    tmp_path: pathlib.Path,
) -> None:
    """When the parent's cache has an entry, ``get_font`` returns it directly."""

    class _FakeCache:
        def __init__(self) -> None:
            self.fonts: dict[Any, Any] = {}

        def get_font(self, info: Any) -> Any:
            return self.fonts.get(info)

        def add_font(self, info: Any, font: Any) -> None:
            self.fonts[info] = font

    class _FakeParent:
        def __init__(self) -> None:
            self.cache = _FakeCache()

        def get_cache(self) -> _FakeCache:
            return self.cache

    parent = _FakeParent()
    path = tmp_path / "fake.ttf"
    path.write_bytes(b"\0\0\0\0")
    info = FSFontInfo(
        file=path,
        font_format=FontFormat.TTF,
        post_script_name="X",
        cid_system_info=None,
        us_weight_class=0,
        s_family_class=0,
        ul_code_page_range1=0,
        ul_code_page_range2=0,
        mac_style=0,
        panose=None,
        parent=parent,  # type: ignore[arg-type]
        font_hash="",
        last_modified=0,
    )
    sentinel = object()
    parent.cache.fonts[info] = sentinel
    assert info.get_font() is sentinel
