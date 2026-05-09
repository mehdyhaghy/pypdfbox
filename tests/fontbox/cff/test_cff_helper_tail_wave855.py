from __future__ import annotations

import builtins
from types import ModuleType

import pytest

from tests.fontbox.cff import test_cff_cid_font as cid_mod
from tests.fontbox.cff import test_cff_font_parity as parity_mod
from tests.fontbox.cff import test_cff_type1_font as type1_mod
from tests.fontbox.cff import test_type2_char_string as type2_mod

_HELPERS = [
    (parity_mod, "_OTF_CANDIDATES", "_load_cff_bytes"),
    (type1_mod, "_TYPE1_OTF_CANDIDATES", "_load_type1_cff_bytes"),
    (cid_mod, "_CID_OTF_CANDIDATES", "_load_cid_cff_bytes"),
    (type2_mod, "_OTF_CANDIDATES", "_load_cff_bytes"),
]


def _raise_fonttools_import(
    real_import: object,
) -> object:
    def fake_import(
        name: str,
        globals_: object = None,
        locals_: object = None,
        fromlist: tuple[object, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "fontTools.ttLib":
            raise ImportError("simulated missing fontTools")
        return real_import(name, globals_, locals_, fromlist, level)  # type: ignore[operator]

    return fake_import


@pytest.mark.parametrize(("module", "candidates_name", "loader_name"), _HELPERS)
def test_wave855_cff_loader_helpers_return_none_without_fonttools(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    candidates_name: str,
    loader_name: str,
) -> None:
    monkeypatch.setattr(module, candidates_name, ["unused"])
    monkeypatch.setattr(
        builtins,
        "__import__",
        _raise_fonttools_import(builtins.__import__),
    )

    assert getattr(module, loader_name)() is None


class _MissingPath:
    def __init__(self, _candidate: str) -> None:
        pass

    def exists(self) -> bool:
        return False


@pytest.mark.parametrize(("module", "candidates_name", "loader_name"), _HELPERS)
def test_wave855_cff_loader_helpers_skip_missing_candidate_paths(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    candidates_name: str,
    loader_name: str,
) -> None:
    monkeypatch.setattr(module, candidates_name, ["missing.otf"])
    monkeypatch.setattr(module, "Path", _MissingPath)

    assert getattr(module, loader_name)() is None


class _ExistingPath:
    def __init__(self, candidate: str) -> None:
        self.candidate = candidate

    def exists(self) -> bool:
        return True

    def __str__(self) -> str:
        return self.candidate


class _NoCFFFont:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def __contains__(self, _key: str) -> bool:
        return False


@pytest.mark.parametrize(("module", "candidates_name", "loader_name"), _HELPERS)
def test_wave855_cff_loader_helpers_ignore_fonts_without_cff_table(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    candidates_name: str,
    loader_name: str,
) -> None:
    import fontTools.ttLib as ttlib

    monkeypatch.setattr(module, candidates_name, ["plain.ttf"])
    monkeypatch.setattr(module, "Path", _ExistingPath)
    monkeypatch.setattr(ttlib, "TTFont", _NoCFFFont)

    assert getattr(module, loader_name)() is None


class _BrokenTTFont:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("cannot open fixture")


@pytest.mark.parametrize(("module", "candidates_name", "loader_name"), _HELPERS)
def test_wave855_cff_loader_helpers_ignore_unreadable_candidates(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    candidates_name: str,
    loader_name: str,
) -> None:
    import fontTools.ttLib as ttlib

    monkeypatch.setattr(module, candidates_name, ["broken.otf"])
    monkeypatch.setattr(module, "Path", _ExistingPath)
    monkeypatch.setattr(ttlib, "TTFont", _BrokenTTFont)

    assert getattr(module, loader_name)() is None
