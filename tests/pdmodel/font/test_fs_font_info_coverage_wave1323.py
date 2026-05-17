"""Wave-1323 follow-up coverage for :mod:`pypdfbox.pdmodel.font.fs_font_info`.

The wave-1318 file (``test_fs_font_info_coverage.py``) lifted the module
from 57 percent to 81 percent. The remaining uncovered branches at the
start of wave 1323 are:

* :func:`FSFontInfo.read_true_type_font` — the ``ImportError`` guard
  (fontTools missing) and the TTC-iteration body (``KeyError`` skip,
  matched-name return, and the trailing ``OSError`` raise when no name
  matches).
* :func:`FSFontInfo.get_type1_font` — the ``ImportError`` guard.
* :func:`FSFontInfo._load_font` — the outer ``except Exception`` wrapper
  that swallows non-``OSError`` parse failures.
* :func:`FSFontInfo._load_truetype` — the ``ImportError`` guard, the
  TTC ``KeyError`` skip, the matched-name return, and the trailing
  ``return None`` when no PostScript name matches.
* :func:`FSFontInfo._load_type1` — the ``ImportError`` guard.

The TTC branches need a real on-disk ``.ttc`` file; we synthesise one
at test time from the bundled Liberation TTF resource so the test is
self-contained and does not need a new committed fixture.
"""

from __future__ import annotations

import pathlib
import sys
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


def _make_ttc(tmp_path: pathlib.Path, ps_names: list[str] | None = None) -> Path:
    """Build a one-or-many-font TTC from the Liberation TTF.

    If ``ps_names`` is provided the cloned TTFonts get those PostScript
    names so the TTC iteration loop can be exercised with multiple
    candidate fonts. fontTools' ``name`` table allows direct mutation
    of name records via ``setName``.
    """
    from fontTools.ttLib import TTCollection, TTFont

    fonts: list[Any] = []
    names = ps_names if ps_names is not None else ["LiberationSans-Bold"]
    for desired in names:
        font = TTFont(str(_LIBERATION_TTF))
        # Replace the PostScript name (nameID=6) on every record so the
        # debug-name lookup picks up the new value regardless of
        # platform/encoding/lang triple.
        name_table = font["name"]
        for rec in list(name_table.names):
            if rec.nameID == 6:
                rec.string = desired.encode(rec.getEncoding())
        fonts.append(font)
    ttc = TTCollection()
    ttc.fonts = fonts
    out = tmp_path / "synthetic.ttc"
    ttc.save(str(out))
    return out


# ---------- ImportError branches ----------


def _block_module(monkeypatch: pytest.MonkeyPatch, fullname: str) -> None:
    """Force ``import <fullname>`` to raise ``ImportError`` for this test."""

    real_import = __import__

    def fake_import(
        name: str,
        globals: Any = None,
        locals: Any = None,
        fromlist: Any = (),
        level: int = 0,
    ) -> Any:
        if name == fullname or name.startswith(fullname + "."):
            raise ImportError(f"blocked: {fullname}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)
    # Drop any cached entry so the next ``from ... import ...`` re-runs
    # the import machinery (and therefore our fake importer).
    for cached in [m for m in list(sys.modules) if m == fullname or m.startswith(fullname + ".")]:
        monkeypatch.delitem(sys.modules, cached, raising=False)


def test_read_true_type_font_returns_none_when_fonttools_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``read_true_type_font`` swallows the ``ImportError`` -> ``None``."""
    info = _make_info(tmp_path / "x.ttf")
    _block_module(monkeypatch, "fontTools.ttLib")
    assert info.read_true_type_font("X", tmp_path / "x.ttf") is None


def test_get_type1_font_returns_none_when_fonttools_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = _make_info(tmp_path / "x.pfb", fmt=FontFormat.PFB)
    _block_module(monkeypatch, "fontTools.t1Lib")
    assert info.get_type1_font("X", tmp_path / "x.pfb") is None


def test_load_truetype_returns_none_when_fonttools_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = _make_info(tmp_path / "x.ttf")
    _block_module(monkeypatch, "fontTools.ttLib")
    assert info._load_truetype() is None


def test_load_type1_returns_none_when_fonttools_missing(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = _make_info(tmp_path / "x.pfb", fmt=FontFormat.PFB)
    _block_module(monkeypatch, "fontTools.t1Lib")
    assert info._load_type1() is None


# ---------- TTC iteration branches ----------


@pytest.mark.skipif(
    not _LIBERATION_TTF.exists(), reason="Liberation TTF resource missing"
)
def test_read_true_type_font_finds_match_in_ttc(tmp_path: pathlib.Path) -> None:
    """The TTC loop returns the entry whose ``name`` table matches."""
    ttc_path = _make_ttc(tmp_path, ["Alpha-Regular", "Beta-Bold"])
    info = _make_info(tmp_path / "ignored.ttf", ps_name="Beta-Bold")
    out = info.read_true_type_font("Beta-Bold", ttc_path)
    assert out is not None
    assert out["name"].getDebugName(6) == "Beta-Bold"


@pytest.mark.skipif(
    not _LIBERATION_TTF.exists(), reason="Liberation TTF resource missing"
)
def test_read_true_type_font_raises_when_ttc_lacks_ps_name(
    tmp_path: pathlib.Path,
) -> None:
    """Trailing ``raise OSError`` fires when no font in the TTC matches."""
    ttc_path = _make_ttc(tmp_path, ["Alpha-Regular"])
    info = _make_info(tmp_path / "ignored.ttf")
    with pytest.raises(OSError):
        info.read_true_type_font("NoSuchPostScriptName", ttc_path)


@pytest.mark.skipif(
    not _LIBERATION_TTF.exists(), reason="Liberation TTF resource missing"
)
def test_read_true_type_font_skips_ttc_entry_without_name_table(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A TTC entry whose ``name`` table lookup raises ``KeyError`` is
    silently skipped — exercises the ``except KeyError: continue`` arm."""
    ttc_path = _make_ttc(tmp_path, ["Real-Bold"])
    info = _make_info(tmp_path / "ignored.ttf", ps_name="Real-Bold")

    from fontTools.ttLib import TTCollection as _RealTTC

    class _BadFont:
        """First-iteration font that raises ``KeyError`` on ``["name"]``."""

        def __getitem__(self, key: str) -> Any:
            raise KeyError(key)

    real_init = _RealTTC.__init__

    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        real_init(self, *args, **kwargs)
        # Inject the bad entry in front of the real Real-Bold font.
        self.fonts = [_BadFont(), *self.fonts]

    monkeypatch.setattr(_RealTTC, "__init__", patched_init)
    out = info.read_true_type_font("Real-Bold", ttc_path)
    assert out is not None
    assert out["name"].getDebugName(6) == "Real-Bold"


@pytest.mark.skipif(
    not _LIBERATION_TTF.exists(), reason="Liberation TTF resource missing"
)
def test_load_truetype_finds_match_in_ttc(tmp_path: pathlib.Path) -> None:
    ttc_path = _make_ttc(tmp_path, ["MatchMe-Regular"])
    info = _make_info(ttc_path, ps_name="MatchMe-Regular")
    out = info._load_truetype()
    assert out is not None
    assert out["name"].getDebugName(6) == "MatchMe-Regular"


@pytest.mark.skipif(
    not _LIBERATION_TTF.exists(), reason="Liberation TTF resource missing"
)
def test_load_truetype_returns_none_when_ttc_lacks_match(
    tmp_path: pathlib.Path,
) -> None:
    """Trailing ``return None`` after the TTC loop with no match."""
    ttc_path = _make_ttc(tmp_path, ["SomeOther-Name"])
    info = _make_info(ttc_path, ps_name="NotPresent")
    assert info._load_truetype() is None


@pytest.mark.skipif(
    not _LIBERATION_TTF.exists(), reason="Liberation TTF resource missing"
)
def test_load_truetype_skips_ttc_entry_without_name_table(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mirror the ``read_true_type_font`` KeyError-skip test for the
    private :meth:`_load_truetype` path."""
    ttc_path = _make_ttc(tmp_path, ["Wanted-Plain"])
    info = _make_info(ttc_path, ps_name="Wanted-Plain")

    from fontTools.ttLib import TTCollection as _RealTTC

    class _BadFont:
        def __getitem__(self, key: str) -> Any:
            raise KeyError(key)

    real_init = _RealTTC.__init__

    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        real_init(self, *args, **kwargs)
        self.fonts = [_BadFont(), *self.fonts]

    monkeypatch.setattr(_RealTTC, "__init__", patched_init)
    out = info._load_truetype()
    assert out is not None
    assert out["name"].getDebugName(6) == "Wanted-Plain"


# ---------- _load_font outer except branch ----------


def test_load_font_swallows_non_oserror_in_loader(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The outer ``except Exception`` in :meth:`_load_font` returns None
    when a loader raises a non-``OSError`` (e.g. fontTools' ``TTLibError``)."""
    info = _make_info(tmp_path / "x.ttf")

    def boom(self: Any) -> Any:
        raise RuntimeError("synthetic loader failure")

    monkeypatch.setattr(FSFontInfo, "_load_truetype", boom, raising=True)
    assert info._load_font() is None


def test_load_font_pfb_swallows_exception(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = _make_info(tmp_path / "x.pfb", fmt=FontFormat.PFB)

    def boom(self: Any) -> Any:
        raise RuntimeError("synthetic loader failure")

    monkeypatch.setattr(FSFontInfo, "_load_type1", boom, raising=True)
    assert info._load_font() is None


