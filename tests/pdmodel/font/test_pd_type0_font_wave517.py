from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSObject, COSStream
from pypdfbox.pdmodel import PDResources
from pypdfbox.pdmodel.font import pd_type0_font as type0_module
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache


def test_wave517_to_unicode_stream_parses_once_and_wins_over_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.fontbox.cmap import CMapParser

    parsed = SimpleNamespace(
        has_unicode_mappings=lambda: True,
        to_unicode=lambda code: "A" if code == 65 else None,
    )
    calls: list[bytes] = []

    def parse(self: CMapParser, data: bytes) -> object:
        calls.append(data)
        return parsed

    stream = COSStream()
    stream.set_raw_data(b"to-unicode-cmap")
    font = PDType0Font()
    font.get_cos_object().set_item(COSName.get_pdf_name("ToUnicode"), stream)
    monkeypatch.setattr(CMapParser, "parse", parse)
    monkeypatch.setattr(
        font,
        "get_cmap",
        lambda: SimpleNamespace(
            has_unicode_mappings=lambda: True,
            to_unicode=lambda _code: "encoding",
        ),
    )

    assert font.to_unicode(65) == "A"
    assert font.get_to_unicode_cmap() is parsed
    assert calls == [b"to-unicode-cmap"]


def test_wave517_vertical_basefont_state_and_descendant_predicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "WaveFont")
    font.get_cos_object().set_name(COSName.get_pdf_name("Encoding"), "Identity-V")
    monkeypatch.setattr(
        font,
        "get_cmap",
        lambda: SimpleNamespace(get_wmode=lambda: 1),
    )
    descendant = SimpleNamespace(
        get_cid_system_info=lambda: SimpleNamespace(
            get_registry=lambda: "Adobe",
            get_ordering=lambda: "GB1",
        ),
        is_embedded=lambda: True,
        is_damaged=lambda: True,
    )
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)

    assert font.is_vertical() is True
    assert font.is_vertical_writing() is True
    assert font.is_cmap_predefined() is True
    assert font.is_descendant_cjk() is True
    assert font.is_embedded() is True
    assert font.is_damaged() is True
    assert font.get_base_font() == "WaveFont"
    assert "WaveFont" in repr(font)

    monkeypatch.setattr(font, "get_cid_system_info", lambda: None)
    assert font.is_descendant_cjk() is False


def test_wave517_encode_string_uses_identity_gsub_run_and_plain_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    monkeypatch.setattr(
        font,
        "get_cmap",
        lambda: SimpleNamespace(get_name=lambda: "Identity-H"),
    )
    monkeypatch.setattr(font, "_get_gsub_table", lambda: object())
    monkeypatch.setattr(font, "code_to_gid", lambda code: code + 1)
    monkeypatch.setattr(font, "apply_gsub_features", lambda gids: [0x1234, *gids])

    assert font.encode_string("") == b""
    assert font.encode_string("A") == b"\x12\x34\x00\x42"

    monkeypatch.setattr(
        font,
        "get_cmap",
        lambda: SimpleNamespace(get_name=lambda: "Custom-H"),
    )
    monkeypatch.setattr(font, "encode", lambda text: b"plain:" + text.encode("ascii"))

    assert font.encode_string("A") == b"plain:A"


def test_wave517_embedded_ttf_unicode_fallback_maps_gid_to_codepoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class InnerTTF(dict):
        def getGlyphOrder(self) -> list[str]:
            return [".notdef", "A", "B"]

    inner = InnerTTF(
        cmap=SimpleNamespace(getBestCmap=lambda: {0x41: "A", 0x42: "B"})
    )
    descendant = PDCIDFontType2(COSDictionary())
    monkeypatch.setattr(descendant, "get_true_type_font", lambda: SimpleNamespace(_tt=inner))
    monkeypatch.setattr(descendant, "is_embedded", lambda: True)
    monkeypatch.setattr(descendant, "code_to_gid", lambda cid: cid)
    font = PDType0Font()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    monkeypatch.setattr(font, "code_to_cid", lambda code: code - 0x40)

    assert font.to_unicode(0x42) == "B"

    monkeypatch.setattr(descendant, "code_to_gid", lambda _cid: 0)
    assert font._unicode_from_embedded_cmap(0x42) is None  # noqa: SLF001


def test_wave517_subset_embeds_bytes_tags_basefont_and_clears_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.fontbox import ttf as ttf_module
    from pypdfbox.pdmodel.font import pd_true_type_font

    calls: dict[str, object] = {}

    class Subsetter:
        def __init__(self, ttf: object) -> None:
            calls["ttf"] = ttf

        def add_all(self, codepoints: set[int]) -> None:
            calls["codepoints"] = codepoints

        def set_prefix(self, prefix: str) -> None:
            calls["prefix"] = prefix

        def to_bytes(self) -> bytes:
            return b"subset-bytes"

    descendant = PDCIDFontType2(COSDictionary())
    descendant._ttf = object()  # noqa: SLF001
    monkeypatch.setattr(descendant, "get_true_type_font", lambda: descendant._ttf)
    monkeypatch.setattr(ttf_module, "TTFSubsetter", Subsetter)
    monkeypatch.setattr(
        pd_true_type_font,
        "_embed_subset_bytes",
        lambda desc, data, tag: calls.update(embed=(desc, data, tag)),
    )
    font = PDType0Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "BasePS")
    font.add_to_subset(ord("A"))
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)

    assert font.subset("B", used_chars=[ord("C")], prefix="ABCDEF") == b"subset-bytes"
    assert calls["codepoints"] == {ord("A"), ord("B"), ord("C")}
    assert calls["prefix"] == "ABCDEF"
    assert calls["embed"] == (descendant, b"subset-bytes", "ABCDEF")
    assert font.get_base_font() == "ABCDEF+BasePS"
    assert descendant._ttf is None  # noqa: SLF001
    assert font._collect_subset_codepoints(None, None) == set()  # noqa: SLF001


def test_wave517_read_font_bytes_accepts_path_and_decode_delegates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "font.bin"
    path.write_bytes(b"path-bytes")

    assert type0_module._read_font_bytes(path) == b"path-bytes"  # noqa: SLF001

    font = PDType0Font()
    monkeypatch.setattr(font, "read_code", lambda data, offset: (data[offset], 1))

    assert font.decode(b"XYZ") == ord("X")
    assert font.read(bytearray(b"YZ")) == ord("Y")


def test_wave517_resources_register_and_cache_type0_font() -> None:
    resources = PDResources(resource_cache=DefaultResourceCache())
    direct_font = PDType0Font()
    direct_key = resources.add(direct_font)

    assert direct_key.get_name() == "F0"
    assert resources.add(direct_font) == direct_key
    assert resources.get_font(direct_key) is direct_font.get_cos_object()
    assert resources.get_x_object("Missing") is None

    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("Subtype"), "Type0")
    indirect = COSObject(12, 0, resolved=font_dict)
    fonts = COSDictionary()
    fonts.set_item(COSName.get_pdf_name("F1"), indirect)
    resources.get_cos_object().set_item(PDResources.FONT, fonts)

    first = resources.get_font(COSName.get_pdf_name("F1"))
    second = resources.get_font(COSName.get_pdf_name("F1"))

    assert isinstance(first, PDType0Font)
    assert second is first
