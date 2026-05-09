from __future__ import annotations

import pytest

from tests.fontbox.cff import test_cff_type1_font as type1_mod


class _ExistingPath:
    def __init__(self, candidate: str) -> None:
        self.candidate = candidate

    def exists(self) -> bool:
        return True

    def __str__(self) -> str:
        return self.candidate


class _CIDKeyedTop:
    ROS = ("Adobe", "Identity", 0)


class _CFFProgram:
    fontNames = ["CIDFont"]  # noqa: N815 - mirrors fontTools attribute

    def __getitem__(self, _name: str) -> _CIDKeyedTop:
        return _CIDKeyedTop()


class _CFFTable:
    cff = _CFFProgram()


class _CIDKeyedTTFont:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def __contains__(self, tag: str) -> bool:
        return tag == "CFF "

    def __getitem__(self, tag: str) -> _CFFTable:
        assert tag == "CFF "
        return _CFFTable()


def test_wave906_type1_loader_skips_cid_keyed_cff_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fontTools.ttLib as ttlib

    monkeypatch.setattr(type1_mod, "_TYPE1_OTF_CANDIDATES", ["cid-keyed.otf"])
    monkeypatch.setattr(type1_mod, "Path", _ExistingPath)
    monkeypatch.setattr(ttlib, "TTFont", _CIDKeyedTTFont)

    assert type1_mod._load_type1_cff_bytes() is None  # noqa: SLF001


class _NoCFFTTFont:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def __contains__(self, _tag: str) -> bool:
        return False


class _RaisesTTFont:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("broken fixture")


def test_wave906_cid_rejection_helper_skips_after_no_cff_and_broken_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fontTools.ttLib as ttlib

    calls = iter([_NoCFFTTFont, _RaisesTTFont])

    def fake_ttfont(*args: object, **kwargs: object) -> object:
        return next(calls)(*args, **kwargs)

    monkeypatch.setattr(type1_mod, "Path", _ExistingPath)
    monkeypatch.setattr(ttlib, "TTFont", fake_ttfont)

    with pytest.raises(pytest.skip.Exception, match="no CIDKeyed font"):
        type1_mod.TestCFFType1FontFromCIDFontRaises().test_from_bytes_rejects_cid_keyed()
