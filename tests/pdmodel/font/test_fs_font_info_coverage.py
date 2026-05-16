"""Coverage tests for :mod:`pypdfbox.pdmodel.font.fs_font_info`.

Focused on the on-disk font-loading branches: parent-cache add path,
TTF/OTF/PFB loader variants, TTC-suffix path, and the public
``get_true_type_font`` / ``get_otf_font`` / ``get_type1_font`` wrappers.

The existing ``test_fs_font_info`` file exercises the metadata accessors;
this module adds the load-path coverage so the module clears 75%.
"""

from __future__ import annotations

import pathlib
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.pdmodel.font.fs_font_info import FSFontInfo


_LIBERATION_TTF = (
    Path(__file__).resolve().parents[3]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "LiberationSans-Bold.ttf"
)


def _make_info(
    file: Path,
    fmt: FontFormat = FontFormat.TTF,
    parent: Any | None = None,
    ps_name: str = "LiberationSans-Bold",
) -> FSFontInfo:
    return FSFontInfo(
        file=file,
        font_format=fmt,
        post_script_name=ps_name,
        cid_system_info=None,
        us_weight_class=400,
        s_family_class=0,
        ul_code_page_range1=0,
        ul_code_page_range2=0,
        mac_style=0,
        panose=None,
        parent=parent,
        font_hash="abc",
        last_modified=0,
    )


class _RecordingCache:
    """Minimal fake matching :class:`FontCache`'s ``get_font`` / ``add_font``."""

    def __init__(self) -> None:
        self.store: dict[Any, Any] = {}
        self.add_calls = 0

    def get_font(self, info: Any) -> Any:
        return self.store.get(info)

    def add_font(self, info: Any, font: Any) -> None:
        self.store[info] = font
        self.add_calls += 1


class _RecordingParent:
    def __init__(self) -> None:
        self.cache = _RecordingCache()

    def get_cache(self) -> _RecordingCache:
        return self.cache


@pytest.mark.skipif(
    not _LIBERATION_TTF.exists(), reason="Liberation TTF resource missing"
)
def test_get_font_loads_and_adds_to_parent_cache() -> None:
    """``get_font`` should cache the loaded font in the parent provider."""
    parent = _RecordingParent()
    info = _make_info(_LIBERATION_TTF, parent=parent)
    font = info.get_font()
    assert font is not None
    # Subsequent call hits the cache rather than reloading.
    again = info.get_font()
    assert again is font
    assert parent.cache.add_calls == 1


@pytest.mark.skipif(
    not _LIBERATION_TTF.exists(), reason="Liberation TTF resource missing"
)
def test_load_truetype_succeeds_for_real_ttf() -> None:
    info = _make_info(_LIBERATION_TTF, parent=None)
    font = info.get_font()
    assert font is not None


def test_load_truetype_returns_none_for_garbage(tmp_path: pathlib.Path) -> None:
    fake = tmp_path / "junk.ttf"
    fake.write_bytes(b"not a font")
    info = _make_info(fake)
    assert info.get_font() is None


def test_load_type1_returns_none_for_garbage(tmp_path: pathlib.Path) -> None:
    fake = tmp_path / "junk.pfb"
    fake.write_bytes(b"not a pfb")
    info = _make_info(fake, fmt=FontFormat.PFB)
    assert info.get_font() is None


def test_load_unknown_format_returns_none(tmp_path: pathlib.Path) -> None:
    """Format not in {TTF, OTF, PFB} falls through to ``return None``."""
    # Use raw construction with an unknown format value via a side-channel.
    fake = tmp_path / "x.bin"
    fake.write_bytes(b"")
    info = _make_info(fake, fmt=FontFormat.TTF)
    # Swap the private format to a sentinel that is not any of TTF/OTF/PFB.
    info._format = object()  # type: ignore[assignment]
    assert info._load_font() is None


def test_read_true_type_font_raises_for_unknown_ps_in_ttc(
    tmp_path: pathlib.Path,
) -> None:
    """When the file name ends with .ttc we exercise the TTC branch."""
    info = _make_info(tmp_path / "fake.ttf")
    fake_ttc = tmp_path / "fake.ttc"
    fake_ttc.write_bytes(b"not a ttc")
    # The TTC loader raises when fontTools can't open the file — we catch
    # the outer Exception in ``get_true_type_font`` and return None.
    assert info.get_true_type_font("NoSuch", fake_ttc) is None


@pytest.mark.skipif(
    not _LIBERATION_TTF.exists(), reason="Liberation TTF resource missing"
)
def test_get_true_type_font_returns_ttfont_for_ttf() -> None:
    info = _make_info(_LIBERATION_TTF)
    font = info.get_true_type_font("LiberationSans-Bold", _LIBERATION_TTF)
    assert font is not None


def test_get_true_type_font_returns_none_on_io_error(tmp_path: pathlib.Path) -> None:
    info = _make_info(tmp_path / "fake.ttf")
    bogus = tmp_path / "bogus.ttf"
    bogus.write_bytes(b"")
    assert info.get_true_type_font("X", bogus) is None


def test_get_otf_font_returns_none_on_failure(tmp_path: pathlib.Path) -> None:
    info = _make_info(tmp_path / "fake.otf", fmt=FontFormat.OTF)
    bogus = tmp_path / "bogus.otf"
    bogus.write_bytes(b"junk")
    assert info.get_otf_font("X", bogus) is None


@pytest.mark.skipif(
    not _LIBERATION_TTF.exists(), reason="Liberation TTF resource missing"
)
def test_get_otf_font_loads_real_font() -> None:
    info = _make_info(_LIBERATION_TTF, fmt=FontFormat.OTF)
    # ``get_otf_font`` delegates to ``read_true_type_font`` and tolerates
    # a TTF presented under the OTF surface (both are OpenType containers).
    out = info.get_otf_font("LiberationSans-Bold", _LIBERATION_TTF)
    assert out is not None


def test_get_type1_font_returns_none_for_invalid_pfb(tmp_path: pathlib.Path) -> None:
    info = _make_info(tmp_path / "fake.pfb", fmt=FontFormat.PFB)
    bogus = tmp_path / "bogus.pfb"
    bogus.write_bytes(b"")
    assert info.get_type1_font("X", bogus) is None


def test_hash_and_mtime_properties(tmp_path: pathlib.Path) -> None:
    p = tmp_path / "x.ttf"
    p.write_bytes(b"\0")
    info = FSFontInfo(
        file=p,
        font_format=FontFormat.TTF,
        post_script_name="X",
        cid_system_info=None,
        us_weight_class=0,
        s_family_class=0,
        ul_code_page_range1=0,
        ul_code_page_range2=0,
        mac_style=0,
        panose=None,
        parent=None,
        font_hash="deadbeef",
        last_modified=1234,
    )
    assert info.font_hash == "deadbeef"
    assert info.last_modified == 1234


def test_load_truetype_ttc_returns_none_for_invalid_path(
    tmp_path: pathlib.Path,
) -> None:
    """A non-existent .ttc file triggers the TTC-open exception branch
    and returns None (matching the null-on-error contract)."""
    fake_ttc = tmp_path / "nonexistent.ttc"
    # No write — the file does not exist.
    info = _make_info(fake_ttc, ps_name="Anything")
    assert info._load_truetype() is None
