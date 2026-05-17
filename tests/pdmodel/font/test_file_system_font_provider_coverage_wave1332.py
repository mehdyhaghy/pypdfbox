"""Wave-1332 coverage-boost tests for ``pypdfbox.pdmodel.font.file_system_font_provider``.

Pre-wave coverage was 88% (29 lines missing). The dropped lines fall
into three buckets:

* ``_scan_fonts`` exception-swallow (lines 366-367) when ``_add_*``
  raises an unexpected error mid-scan;
* the ``ImportError`` fallbacks for ``fontTools.ttLib.TTFont`` /
  ``TTCollection`` / ``fontTools.t1Lib.T1Font`` (lines 378-379,
  400-401, 494-495);
* the ``_add_ttf_metadata`` defensive branches (line 421 — missing
  ``post_script_name``; 453-454 — missing OS/2 table; 459-460 —
  missing ``head`` table; 466-467 — ``file.stat`` OSError) and the
  ``_add_type1_font`` happy path (lines 501-523).

Pushes the file to >=95%.
"""

from __future__ import annotations

import builtins
import logging
import pathlib
from typing import Any
from unittest.mock import patch

import pytest

from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.pdmodel.font.file_system_font_provider import FileSystemFontProvider

# ---------- _scan_fonts exception swallow ---------------------------------


def test_scan_fonts_swallows_unexpected_error(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A ``ValueError`` raised inside the dispatched ``_add_*`` is logged + skipped."""
    fake_font = tmp_path / "boom.ttf"
    fake_font.write_bytes(b"")

    provider = FileSystemFontProvider(directories=[])

    def _kaboom(self: Any, file: pathlib.Path) -> None:
        raise ValueError("explode")

    monkeypatch.setattr(FileSystemFontProvider, "_add_true_type_font", _kaboom)
    with caplog.at_level(
        logging.DEBUG, logger="pypdfbox.pdmodel.font.file_system_font_provider"
    ):
        provider.scan_fonts([fake_font])
    # No fonts added; debug log emitted.
    assert list(provider.get_font_info()) == []
    assert any("Could not load font" in rec.message for rec in caplog.records)


# ---------- fontTools.ttLib.TTFont ImportError fallback -------------------


def test_add_true_type_font_handles_missing_fonttools(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing ``fontTools.ttLib`` import returns without raising."""
    fake = tmp_path / "x.ttf"
    fake.write_bytes(b"")
    provider = FileSystemFontProvider(directories=[])

    def _no_ttlib(name: str, *args: object, **kwargs: object) -> Any:
        if name.startswith("fontTools.ttLib"):
            raise ImportError("no fontTools")
        return _orig_import(name, *args, **kwargs)

    _orig_import = builtins.__import__
    monkeypatch.setattr("builtins.__import__", _no_ttlib)
    # Must not raise; nothing added.
    provider.add_true_type_font(fake)
    assert list(provider.get_font_info()) == []


def test_add_true_type_collection_handles_missing_fonttools(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = tmp_path / "x.ttc"
    fake.write_bytes(b"")
    provider = FileSystemFontProvider(directories=[])

    def _no_ttlib(name: str, *args: object, **kwargs: object) -> Any:
        if name.startswith("fontTools.ttLib"):
            raise ImportError("no fontTools")
        return _orig_import(name, *args, **kwargs)

    _orig_import = builtins.__import__
    monkeypatch.setattr("builtins.__import__", _no_ttlib)
    provider.add_true_type_collection(fake)
    assert list(provider.get_font_info()) == []


def test_add_type1_font_handles_missing_fonttools(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = tmp_path / "x.pfb"
    fake.write_bytes(b"")
    provider = FileSystemFontProvider(directories=[])

    def _no_t1lib(name: str, *args: object, **kwargs: object) -> Any:
        if name.startswith("fontTools.t1Lib"):
            raise ImportError("no t1Lib")
        return _orig_import(name, *args, **kwargs)

    _orig_import = builtins.__import__
    monkeypatch.setattr("builtins.__import__", _no_t1lib)
    provider.add_type1_font(fake)
    assert list(provider.get_font_info()) == []


# ---------- _add_true_type_collection per-font extraction error -----------


def test_add_true_type_collection_swallows_per_font_oserror(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If ``_add_ttf_metadata`` raises ``OSError`` per font, the loop continues."""
    fake = tmp_path / "x.ttc"
    fake.write_bytes(b"")

    class _FakeTTC:
        fonts = [object(), object(), object()]

    def _fake_collection(*_args: object, **_kwargs: object) -> _FakeTTC:
        return _FakeTTC()

    provider = FileSystemFontProvider(directories=[])

    def _raise_oserror(self: Any, file: pathlib.Path, ttf: object) -> None:
        raise OSError("boom")

    with patch("fontTools.ttLib.TTCollection", _fake_collection):
        monkeypatch.setattr(
            FileSystemFontProvider, "_add_ttf_metadata", _raise_oserror
        )
        with caplog.at_level(
            logging.DEBUG,
            logger="pypdfbox.pdmodel.font.file_system_font_provider",
        ):
            provider.add_true_type_collection(fake)
    assert list(provider.get_font_info()) == []
    assert any("metadata" in rec.message for rec in caplog.records)


# ---------- _add_ttf_metadata defensive branches --------------------------


def test_add_ttf_metadata_returns_when_post_script_name_is_empty(
    tmp_path: pathlib.Path,
) -> None:
    """An empty ``getDebugName(6)`` short-circuits without adding an FSFontInfo."""

    class _NameTable:
        @staticmethod
        def getDebugName(_n: int) -> str:
            return ""

    class _FakeTTF:
        def __getitem__(self, key: str) -> Any:
            if key == "name":
                return _NameTable()
            raise KeyError(key)

    provider = FileSystemFontProvider(directories=[])
    provider._add_ttf_metadata(tmp_path / "x.ttf", _FakeTTF())  # noqa: SLF001
    assert list(provider.get_font_info()) == []


def test_add_ttf_metadata_handles_missing_os2_and_head(
    tmp_path: pathlib.Path,
) -> None:
    """Missing ``OS/2`` and ``head`` tables default to zeros."""

    class _NameTable:
        @staticmethod
        def getDebugName(_n: int) -> str:
            return "FakeFont"

    class _FakeTTF:
        def __getitem__(self, key: str) -> Any:
            if key == "name":
                return _NameTable()
            raise KeyError(key)  # OS/2 + head both missing

    f = tmp_path / "fake.ttf"
    f.write_bytes(b"")
    provider = FileSystemFontProvider(directories=[])
    provider._add_ttf_metadata(f, _FakeTTF())  # noqa: SLF001
    infos = list(provider.get_font_info())
    assert len(infos) == 1
    assert infos[0].get_post_script_name() == "FakeFont"
    # Zero defaults applied.
    assert infos[0].get_weight_class() == 0
    assert infos[0].get_mac_style() == 0


def test_add_ttf_metadata_handles_stat_oserror(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failing ``file.stat()`` produces ``last_modified=0`` rather than raising."""

    class _NameTable:
        @staticmethod
        def getDebugName(_n: int) -> str:
            return "StatBoom"

    class _FakeTTF:
        def __getitem__(self, key: str) -> Any:
            if key == "name":
                return _NameTable()
            raise KeyError(key)

    f = tmp_path / "missing.ttf"
    # File never created on disk — `stat` raises ``OSError``.
    provider = FileSystemFontProvider(directories=[])
    provider._add_ttf_metadata(f, _FakeTTF())  # noqa: SLF001
    infos = list(provider.get_font_info())
    assert len(infos) == 1
    assert infos[0].last_modified == 0


# ---------- _add_type1_font happy path ------------------------------------


def test_add_type1_font_with_real_font_name(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``t1.font['FontName']`` is used when the Type-1 dict carries one."""

    class _T1:
        font = {"FontName": "MyType1Font"}

    pfb = tmp_path / "fake.pfb"
    pfb.write_bytes(b"")

    def _fake_t1(*_args: object, **_kwargs: object) -> _T1:
        return _T1()

    provider = FileSystemFontProvider(directories=[])
    with patch("fontTools.t1Lib.T1Font", _fake_t1):
        provider.add_type1_font(pfb)
    infos = list(provider.get_font_info())
    assert len(infos) == 1
    assert infos[0].get_post_script_name() == "MyType1Font"
    assert infos[0].get_format() is FontFormat.PFB


def test_add_type1_font_falls_back_to_stem_when_no_font_name(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _T1:
        font: dict[str, Any] = {}

    pfb = tmp_path / "fallback.pfb"
    pfb.write_bytes(b"")

    def _fake_t1(*_args: object, **_kwargs: object) -> _T1:
        return _T1()

    provider = FileSystemFontProvider(directories=[])
    with patch("fontTools.t1Lib.T1Font", _fake_t1):
        provider.add_type1_font(pfb)
    infos = list(provider.get_font_info())
    assert len(infos) == 1
    # No FontName -> stem fallback.
    assert infos[0].get_post_script_name() == "fallback"


def test_add_type1_font_with_non_dict_font_falls_back_to_stem(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``t1.font`` is not a dict — fall through to ``file.stem``."""

    class _T1:
        font = ["not", "a", "dict"]

    pfb = tmp_path / "weird.pfb"
    pfb.write_bytes(b"")

    def _fake_t1(*_args: object, **_kwargs: object) -> _T1:
        return _T1()

    provider = FileSystemFontProvider(directories=[])
    with patch("fontTools.t1Lib.T1Font", _fake_t1):
        provider.add_type1_font(pfb)
    infos = list(provider.get_font_info())
    assert len(infos) == 1
    assert infos[0].get_post_script_name() == "weird"


def test_add_type1_font_stat_oserror_yields_zero_modified(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``stat`` ``OSError`` produces ``last_modified=0`` rather than raising."""

    class _T1:
        font = {"FontName": "Stat"}

    missing = tmp_path / "absent.pfb"

    def _fake_t1(*_args: object, **_kwargs: object) -> _T1:
        return _T1()

    provider = FileSystemFontProvider(directories=[])
    with patch("fontTools.t1Lib.T1Font", _fake_t1):
        provider.add_type1_font(missing)
    infos = list(provider.get_font_info())
    assert len(infos) == 1
    assert infos[0].last_modified == 0
