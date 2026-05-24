"""Wave 1391 — coverage round-out for :mod:`pypdfbox.pdmodel.font.font_mapper_impl`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.fontbox.font_info import FontInfo
from pypdfbox.fontbox.font_provider import FontProvider
from pypdfbox.pdmodel.font.font_cache import FontCache as _FontCache
from pypdfbox.pdmodel.font.font_mapper_impl import FontMapperImpl
from pypdfbox.pdmodel.font.pd_cid_system_info import PDCIDSystemInfo
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor


class _FakeFontInfo(FontInfo):
    def __init__(self, name: str, font: Any, file: Path | None = None) -> None:
        self._name = name
        self._font = font
        self._file = file

    def get_post_script_name(self) -> str:
        return self._name

    def get_format(self) -> FontFormat:
        return FontFormat.TTF

    def get_cid_system_info(self) -> Any:
        return None

    def get_font(self) -> Any:
        return self._font

    def get_family_class(self) -> int:
        return 0

    def get_code_page_range1(self) -> int:
        return 0

    def get_code_page_range2(self) -> int:
        return 0

    def get_weight_class(self) -> int:
        return 400

    def get_panose(self) -> Any:
        return None

    def get_mac_style(self) -> int:
        return 0

    @property
    def file(self) -> Path | None:
        return self._file


class _NoScanProvider(FontProvider):
    def __init__(self, fonts: list[FontInfo]) -> None:
        self._fonts = fonts
        self._cache = _FontCache()

    def to_debug_string(self) -> str:
        return ""

    def get_font_info(self) -> list[FontInfo]:
        return list(self._fonts)

    def get_cache(self) -> _FontCache:
        return self._cache


class _ScanProvider(FontProvider):
    def __init__(
        self,
        fonts: list[FontInfo],
        *,
        raise_on_scan: bool = False,
        on_scan_add: list[FontInfo] | None = None,
    ) -> None:
        self._fonts = fonts
        self._cache = _FontCache()
        self.scanned_paths: list[Path] = []
        self._raise_on_scan = raise_on_scan
        self._on_scan_add = on_scan_add or []

    def to_debug_string(self) -> str:
        return ""

    def get_font_info(self) -> list[FontInfo]:
        return list(self._fonts)

    def get_cache(self) -> _FontCache:
        return self._cache

    def scan_fonts(self, paths: list[Path]) -> None:
        self.scanned_paths.extend(paths)
        if self._raise_on_scan:
            raise OSError("simulated scan failure")
        self._fonts.extend(self._on_scan_add)


def test_try_fetch_noto_cjk_returns_none_when_ensure_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(
        "pypdfbox.fontbox.cjk_loader.ensure_language", lambda ordering: None
    )
    impl = FontMapperImpl()
    assert impl._try_fetch_noto_cjk("Japan1") is None


def test_try_fetch_noto_cjk_returns_none_when_provider_lacks_scan(
    monkeypatch, tmp_path: Path
) -> None:
    fake_path = tmp_path / "NotoSansJP-Regular.ttf"
    fake_path.write_bytes(b"")
    monkeypatch.setattr(
        "pypdfbox.fontbox.cjk_loader.ensure_language", lambda ordering: fake_path
    )
    impl = FontMapperImpl()
    impl.set_provider(_NoScanProvider([]))
    assert impl._try_fetch_noto_cjk("Japan1") is None


def test_try_fetch_noto_cjk_returns_none_on_scan_oserror(
    monkeypatch, tmp_path: Path
) -> None:
    fake_path = tmp_path / "NotoSansJP-Regular.ttf"
    fake_path.write_bytes(b"")
    monkeypatch.setattr(
        "pypdfbox.fontbox.cjk_loader.ensure_language", lambda ordering: fake_path
    )
    impl = FontMapperImpl()
    impl.set_provider(_ScanProvider([], raise_on_scan=True))
    assert impl._try_fetch_noto_cjk("Japan1") is None


def test_try_fetch_noto_cjk_resolves_by_stem_match(
    monkeypatch, tmp_path: Path
) -> None:
    fake_path = tmp_path / "NotoSansJP-Regular.ttf"
    fake_path.write_bytes(b"")
    monkeypatch.setattr(
        "pypdfbox.fontbox.cjk_loader.ensure_language", lambda ordering: fake_path
    )
    sentinel = object()
    info = _FakeFontInfo("NotoSansJP-Regular", sentinel)
    impl = FontMapperImpl()
    impl.set_provider(_ScanProvider([], on_scan_add=[info]))
    assert impl._try_fetch_noto_cjk("Japan1") is sentinel


def test_try_fetch_noto_cjk_resolves_via_regular_fallback(
    monkeypatch, tmp_path: Path
) -> None:
    fake_path = tmp_path / "Mismatch.ttf"
    fake_path.write_bytes(b"")
    monkeypatch.setattr(
        "pypdfbox.fontbox.cjk_loader.ensure_language", lambda ordering: fake_path
    )
    sentinel = object()
    info = _FakeFontInfo("NotoSansKR-Regular", sentinel)
    impl = FontMapperImpl()
    impl.set_provider(_ScanProvider([], on_scan_add=[info]))
    assert impl._try_fetch_noto_cjk("Korea1") is sentinel


def test_try_fetch_noto_cjk_returns_none_when_no_indexed_font_matches(
    monkeypatch, tmp_path: Path
) -> None:
    fake_path = tmp_path / "Mismatch.ttf"
    fake_path.write_bytes(b"")
    monkeypatch.setattr(
        "pypdfbox.fontbox.cjk_loader.ensure_language", lambda ordering: fake_path
    )
    impl = FontMapperImpl()
    impl.set_provider(_ScanProvider([]))
    assert impl._try_fetch_noto_cjk("Japan1") is None


def test_get_cid_font_falls_through_to_noto_cjk(monkeypatch, tmp_path: Path) -> None:
    fake_path = tmp_path / "NotoSansJP-Regular.ttf"
    fake_path.write_bytes(b"")
    monkeypatch.setattr(
        "pypdfbox.fontbox.cjk_loader.ensure_language", lambda ordering: fake_path
    )
    sentinel = object()
    info = _FakeFontInfo("NotoSansJP-Regular", sentinel)
    impl = FontMapperImpl()
    impl.set_provider(_ScanProvider([], on_scan_add=[info]))
    descriptor = PDFontDescriptor()
    descriptor.set_font_name("DroidSans")
    cid = PDCIDSystemInfo("Adobe", "Japan1", 6)
    mapping = impl.get_cid_font("DroidSans", descriptor, cid)
    assert mapping is not None
    assert mapping.get_true_type_font() is sentinel
    assert mapping.is_fallback() is True


def test_get_last_resort_returns_legacy_single_slot_when_descriptor_is_none() -> None:
    impl = FontMapperImpl()
    sentinel = object()
    impl._last_resort_font = sentinel
    assert impl._get_last_resort_font(None) is sentinel


def test_get_last_resort_returns_none_when_ensure_font_returns_none(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "pypdfbox.fontbox.liberation_loader.ensure_font",
        lambda descriptor: None,
    )
    impl = FontMapperImpl()
    assert impl._get_last_resort_font(None) is None


def test_load_bundled_path_returns_none_when_provider_lacks_scan(
    tmp_path: Path,
) -> None:
    fake_path = tmp_path / "Whatever.ttf"
    fake_path.write_bytes(b"")
    impl = FontMapperImpl()
    impl.set_provider(_NoScanProvider([]))
    assert impl._load_bundled_path(fake_path) is None


def test_load_bundled_path_returns_none_on_scan_oserror(tmp_path: Path) -> None:
    fake_path = tmp_path / "Whatever.ttf"
    fake_path.write_bytes(b"")
    impl = FontMapperImpl()
    impl.set_provider(_ScanProvider([], raise_on_scan=True))
    assert impl._load_bundled_path(fake_path) is None


def test_load_bundled_path_resolves_via_stem_suffix_strip(tmp_path: Path) -> None:
    fake_path = tmp_path / "LiberationSans-Regular.ttf"
    fake_path.write_bytes(b"")
    sentinel = object()
    info = _FakeFontInfo("LiberationSans", sentinel)
    impl = FontMapperImpl()
    impl.set_provider(_ScanProvider([], on_scan_add=[info]))
    assert impl._load_bundled_path(fake_path) is sentinel


def test_load_bundled_path_resolves_via_file_path_fallback(
    tmp_path: Path,
) -> None:
    fake_path = tmp_path / "LiberationSans-Regular.ttf"
    fake_path.write_bytes(b"")
    sentinel = object()
    info = _FakeFontInfo("CompletelyOther", sentinel, file=fake_path)
    impl = FontMapperImpl()
    impl.set_provider(_ScanProvider([], on_scan_add=[info]))
    assert impl._load_bundled_path(fake_path) is sentinel


def test_load_bundled_path_returns_none_when_no_matching_font(
    tmp_path: Path,
) -> None:
    fake_path = tmp_path / "WhateverElse.ttf"
    fake_path.write_bytes(b"")
    impl = FontMapperImpl()
    impl.set_provider(_ScanProvider([]))
    assert impl._load_bundled_path(fake_path) is None
