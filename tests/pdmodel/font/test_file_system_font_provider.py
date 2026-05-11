"""Tests for :mod:`pypdfbox.pdmodel.font.file_system_font_provider`.

No upstream JUnit test exists — :class:`FileSystemFontProvider` is
package-private. We cover the publicly-observable behaviour:

* Constructing with an empty directory list yields zero fonts.
* Cache wiring (the provider exposes its :class:`FontCache`).
* The debug-string aggregator joins per-font ``__str__`` lines.
"""

from __future__ import annotations

import pathlib

from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.pdmodel.font.cid_system_info import CIDSystemInfo
from pypdfbox.pdmodel.font.file_system_font_provider import FileSystemFontProvider
from pypdfbox.pdmodel.font.font_cache import FontCache
from pypdfbox.pdmodel.font.fs_font_info import FSFontInfo


def test_empty_directory_list_yields_no_fonts() -> None:
    provider = FileSystemFontProvider(cache=FontCache(), directories=[])
    assert list(provider.get_font_info()) == []


def test_missing_directory_is_skipped(tmp_path: pathlib.Path) -> None:
    missing = tmp_path / "does-not-exist"
    provider = FileSystemFontProvider(cache=FontCache(), directories=[missing])
    assert list(provider.get_font_info()) == []


def test_get_cache_returns_constructor_arg() -> None:
    cache = FontCache()
    provider = FileSystemFontProvider(cache=cache, directories=[])
    assert provider.get_cache() is cache


def test_to_debug_string_with_no_fonts() -> None:
    provider = FileSystemFontProvider(cache=FontCache(), directories=[])
    assert provider.to_debug_string() == ""


def test_to_debug_string_with_synthetic_fonts(tmp_path: pathlib.Path) -> None:
    """Inject a synthetic :class:`FSFontInfo` to exercise ``__str__`` join."""
    provider = FileSystemFontProvider(cache=FontCache(), directories=[])
    info = FSFontInfo(
        file=tmp_path / "Fake.ttf",
        font_format=FontFormat.TTF,
        post_script_name="FakeFont",
        cid_system_info=CIDSystemInfo("Adobe", "Identity", 0),
        us_weight_class=400,
        s_family_class=0,
        ul_code_page_range1=0,
        ul_code_page_range2=0,
        mac_style=0,
        panose=None,
        parent=provider,
        font_hash="abc",
        last_modified=0,
    )
    provider._font_info_list.append(info)  # type: ignore[attr-defined]
    debug = provider.to_debug_string()
    assert "FakeFont" in debug
    assert "abc" in debug


def test_scan_skips_non_font_files(tmp_path: pathlib.Path) -> None:
    """Files without a TTF/OTF/PFB extension don't get picked up."""
    (tmp_path / "readme.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "ignored.bin").write_bytes(b"\0\0")
    provider = FileSystemFontProvider(cache=FontCache(), directories=[tmp_path])
    assert list(provider.get_font_info()) == []


def test_scan_silently_drops_unparseable_ttf(tmp_path: pathlib.Path) -> None:
    """Garbage .ttf files don't propagate the parse error."""
    (tmp_path / "garbage.ttf").write_bytes(b"\x00" * 32)
    # The provider should not raise.
    provider = FileSystemFontProvider(cache=FontCache(), directories=[tmp_path])
    assert list(provider.get_font_info()) == []
