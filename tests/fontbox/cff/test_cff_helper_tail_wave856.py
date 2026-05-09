from __future__ import annotations

import builtins
from collections.abc import Callable
from types import ModuleType

import pytest

from tests.fontbox.cff import test_cff_cid_font as cid_mod
from tests.fontbox.cff import test_cff_font_parity as parity_mod
from tests.fontbox.cff import test_cff_type1_font as type1_mod
from tests.fontbox.cff import test_type2_char_string as type2_mod


class _MissingPath:
    def __init__(self, _candidate: str) -> None:
        pass

    def exists(self) -> bool:
        return False


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


class _BrokenTTFont:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("cannot open fixture")


def _fake_import_error(real_import: object) -> Callable[..., object]:
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


@pytest.mark.parametrize(
    ("module", "fixture_name", "bytes_name"),
    [
        (parity_mod, "cff_font", "_CFF_BYTES"),
        (type1_mod, "type1_font", "_TYPE1_BYTES"),
        (cid_mod, "cid_font", "_CID_BYTES"),
        (type2_mod, "cff_font", "_CFF_BYTES"),
    ],
)
def test_wave856_cff_font_fixtures_skip_when_host_fixture_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    module: ModuleType,
    fixture_name: str,
    bytes_name: str,
) -> None:
    monkeypatch.setattr(module, bytes_name, None)

    with pytest.raises(pytest.skip.Exception):
        getattr(module, fixture_name).__wrapped__()


def test_wave856_type1_predefined_encoding_test_exercises_expert_branch() -> None:
    class _ExpertFont:
        def is_standard_encoding(self) -> bool:
            return False

        def is_expert_encoding(self) -> bool:
            return True

        def code_to_name(self, code: int) -> str:
            assert code == 65
            return "Asmall"

    type1_mod.test_parsed_type1_code_to_name_predefined(_ExpertFont())


def test_wave856_type1_from_bytes_rejects_cid_skips_when_fonttools_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        builtins,
        "__import__",
        _fake_import_error(builtins.__import__),
    )

    with pytest.raises(pytest.skip.Exception):
        type1_mod.TestCFFType1FontFromCIDFontRaises().test_from_bytes_rejects_cid_keyed()


def test_wave856_type1_from_bytes_rejects_cid_skips_missing_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(type1_mod, "Path", _MissingPath)

    with pytest.raises(pytest.skip.Exception):
        type1_mod.TestCFFType1FontFromCIDFontRaises().test_from_bytes_rejects_cid_keyed()


def test_wave856_cid_from_bytes_rejects_name_keyed_skips_when_fonttools_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        builtins,
        "__import__",
        _fake_import_error(builtins.__import__),
    )

    with pytest.raises(pytest.skip.Exception):
        cid_mod.TestCFFCIDFontFromNonCIDRaises().test_from_bytes_rejects_name_keyed()


def test_wave856_cid_from_bytes_rejects_name_keyed_skips_missing_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cid_mod, "Path", _MissingPath)

    with pytest.raises(pytest.skip.Exception):
        cid_mod.TestCFFCIDFontFromNonCIDRaises().test_from_bytes_rejects_name_keyed()


def test_wave856_cid_from_bytes_rejects_name_keyed_ignores_non_cff_font(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fontTools.ttLib as ttlib

    monkeypatch.setattr(cid_mod, "Path", _ExistingPath)
    monkeypatch.setattr(ttlib, "TTFont", _NoCFFFont)

    with pytest.raises(pytest.skip.Exception):
        cid_mod.TestCFFCIDFontFromNonCIDRaises().test_from_bytes_rejects_name_keyed()


def test_wave856_cid_from_bytes_rejects_name_keyed_ignores_broken_font(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fontTools.ttLib as ttlib

    monkeypatch.setattr(cid_mod, "Path", _ExistingPath)
    monkeypatch.setattr(ttlib, "TTFont", _BrokenTTFont)

    with pytest.raises(pytest.skip.Exception):
        cid_mod.TestCFFCIDFontFromNonCIDRaises().test_from_bytes_rejects_name_keyed()
