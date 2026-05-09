from __future__ import annotations

from types import SimpleNamespace

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font


class _Descendant:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int] | str] = []

    def get_cid_system_info(self) -> SimpleNamespace:
        self.calls.append("info")
        return SimpleNamespace(
            get_registry=lambda: "Adobe",
            get_ordering=lambda: "KR",
        )

    def get_font_descriptor(self) -> str:
        self.calls.append("descriptor")
        return "descendant-descriptor"

    def code_to_cid(self, code: int) -> int:
        self.calls.append(("cid", code))
        return code + 100

    def cid_to_gid(self, cid: int) -> int:
        self.calls.append(("gid", cid))
        return cid + 1000


class _CMap:
    def __init__(self, cid: int, *, has_mappings: bool = True) -> None:
        self.cid = cid
        self.has_mappings = has_mappings

    def has_cid_mappings(self) -> bool:
        return self.has_mappings

    def to_cid(self, code: int) -> int:
        return self.cid if code != 0 else 7


def test_wave487_alias_descriptor_encoding_and_cid_info_delegate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    descendant = _Descendant()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    font.get_cos_object().set_name(COSName.get_pdf_name("Encoding"), "Identity-H")

    assert font.get_cid_font() is descendant
    assert font.get_cid_system_info().get_ordering() == "KR"
    assert font.get_font_descriptor() == "descendant-descriptor"
    assert font.get_encoding() == COSName.get_pdf_name("Identity-H")
    assert descendant.calls == ["info", "descriptor"]


def test_wave487_get_cmap_ucs2_uses_registry_ordering_and_caches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.fontbox.cmap import CMapParser

    parsed = object()
    calls: list[str] = []

    def parse_predefined(name: str) -> object:
        calls.append(name)
        return parsed

    font = PDType0Font()
    monkeypatch.setattr(
        font,
        "get_cid_system_info",
        lambda: SimpleNamespace(
            get_registry=lambda: "Adobe",
            get_ordering=lambda: "Japan1",
        ),
    )
    monkeypatch.setattr(CMapParser, "parse_predefined", parse_predefined)

    assert font.get_cmap_ucs2() is parsed
    assert font.get_cmap_ucs2() is parsed
    assert calls == ["Adobe-Japan1-UCS2"]


@pytest.mark.parametrize(
    "info",
    [
        None,
        SimpleNamespace(get_registry=lambda: None, get_ordering=lambda: "GB1"),
        SimpleNamespace(get_registry=lambda: "Adobe", get_ordering=lambda: None),
        SimpleNamespace(get_registry=lambda: "Adobe", get_ordering=lambda: "Identity"),
        SimpleNamespace(get_registry=lambda: "Other", get_ordering=lambda: "GB1"),
    ],
)
def test_wave487_get_cmap_ucs2_negative_paths_are_cached(
    monkeypatch: pytest.MonkeyPatch,
    info: object,
) -> None:
    font = PDType0Font()
    calls = 0

    def get_info() -> object:
        nonlocal calls
        calls += 1
        return info

    monkeypatch.setattr(font, "get_cid_system_info", get_info)

    assert font.get_cmap_ucs2() is None
    assert font.get_cmap_ucs2() is None
    assert calls == 1


def test_wave487_get_cmap_ucs2_parser_failure_caches_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.fontbox.cmap import CMapParser

    calls: list[str] = []

    def parse_predefined(name: str) -> object:
        calls.append(name)
        raise OSError("missing")

    font = PDType0Font()
    monkeypatch.setattr(
        font,
        "get_cid_system_info",
        lambda: SimpleNamespace(
            get_registry=lambda: "Adobe",
            get_ordering=lambda: "GB1",
        ),
    )
    monkeypatch.setattr(CMapParser, "parse_predefined", parse_predefined)

    assert font.get_cmap_ucs2() is None
    assert font.get_cmap_ucs2() is None
    assert calls == ["Adobe-GB1-UCS2"]


def test_wave487_code_to_cid_uses_cmap_hit_zero_code_and_descendant_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    descendant = _Descendant()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)

    monkeypatch.setattr(font, "get_cmap", lambda: _CMap(55))
    assert font.code_to_cid(8) == 55

    monkeypatch.setattr(font, "get_cmap", lambda: _CMap(0))
    assert font.code_to_cid(0) == 7
    assert font.code_to_cid(8) == 108

    monkeypatch.setattr(font, "get_cmap", lambda: _CMap(0, has_mappings=False))
    assert font.code_to_cid(9) == 109
    assert descendant.calls == [("cid", 8), ("cid", 9)]


def test_wave487_code_to_gid_handles_no_descendant_missing_cid_to_gid_and_gsub_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    monkeypatch.setattr(font, "get_descendant_font", lambda: None)
    monkeypatch.setattr(font, "code_to_cid", lambda code: code + 1)

    assert font.code_to_gid(4) == 5

    descendant = SimpleNamespace()
    gsub = SimpleNamespace(
        get_substitution=lambda *_args: (_ for _ in ()).throw(RuntimeError("bad"))
    )
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    monkeypatch.setattr(font, "_get_gsub_table", lambda: gsub)

    assert font.code_to_gid(4) == 5
