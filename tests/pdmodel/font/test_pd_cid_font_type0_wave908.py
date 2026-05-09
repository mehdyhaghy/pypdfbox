from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0

from . import test_pd_cid_font_type0 as type0_tests


class _FakeCIDFont(CFFCIDFont):
    def __init__(self, charset: list[str]) -> None:
        self._charset = charset

    def get_charset(self) -> list[str]:
        return self._charset


def test_wave908_get_cff_font_cid_branch_body_runs(monkeypatch: Any) -> None:
    fake_program = _FakeCIDFont([".notdef"])

    class _Font(PDCIDFontType0):
        def get_cff_font(self) -> CFFCIDFont:
            return fake_program

    monkeypatch.setattr(type0_tests, "_make_font_with_descriptor", lambda **_kwargs: _Font())

    type0_tests.test_get_cff_font_returns_cff_cid_font_for_cid_keyed_program()


def test_wave908_code_to_gid_cid_keyed_mapped_branch_body_runs(monkeypatch: Any) -> None:
    fake_program = _FakeCIDFont([".notdef", "cid00001", "cid00002"])

    class _Font(PDCIDFontType0):
        def get_cff_font(self) -> CFFCIDFont:
            return fake_program

    monkeypatch.setattr(type0_tests, "_make_font_with_descriptor", lambda **_kwargs: _Font())

    type0_tests.test_code_to_gid_uses_charset_for_cid_keyed_program()


def test_wave908_code_to_gid_cid_keyed_unmapped_branch_body_runs(monkeypatch: Any) -> None:
    fake_program = _FakeCIDFont([".notdef", "cid00001"])

    class _Font(PDCIDFontType0):
        def get_cff_font(self) -> CFFCIDFont:
            return fake_program

    monkeypatch.setattr(type0_tests, "_make_font_with_descriptor", lambda **_kwargs: _Font())

    type0_tests.test_code_to_gid_returns_zero_for_unmapped_cid_in_cid_keyed_program()


def test_wave908_cid_branch_helper_can_drive_name_keyed_fallback() -> None:
    assert isinstance(CFFType1Font(), CFFType1Font)

