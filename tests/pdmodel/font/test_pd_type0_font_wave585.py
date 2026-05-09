from __future__ import annotations

import io
from types import SimpleNamespace

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.font import pd_type0_font as type0_module
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font


def test_wave585_wraps_type0_descendant_and_missing_info_branches() -> None:
    descendant_dict = COSDictionary()
    descendant_dict.set_name(COSName.SUBTYPE, PDCIDFontType0.SUB_TYPE)  # type: ignore[attr-defined]
    parent = PDType0Font()
    wrapped = PDType0Font._wrap_descendant(descendant_dict, parent)  # noqa: SLF001

    assert isinstance(wrapped, PDCIDFontType0)
    assert PDType0Font().get_cid_system_info() is None
    assert PDType0Font().code_to_cid(37) == 37


def test_wave585_own_descriptor_and_simple_predicate_defaults() -> None:
    descriptor = PDFontDescriptor()
    descriptor.set_font_name("OwnDescriptor")
    font = PDType0Font()
    font.set_font_descriptor(descriptor)

    assert font.get_font_descriptor().get_font_name() == "OwnDescriptor"
    assert font.read_code(b"abc", len(b"abc")) == (0, 0)
    assert font.is_vertical() is False
    assert font.is_embedded() is False
    assert font.is_damaged() is False
    assert font.is_standard14() is False


def test_wave585_descendant_cjk_false_for_non_adobe_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    monkeypatch.setattr(
        font,
        "get_cid_system_info",
        lambda: SimpleNamespace(get_registry=lambda: "Other", get_ordering=lambda: "GB1"),
    )

    assert font.is_descendant_cjk() is False


def test_wave585_string_encode_and_none_cmap_codepoint_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    monkeypatch.setattr(
        font,
        "get_cmap",
        lambda: SimpleNamespace(get_codes_from_unicode=lambda ch: bytes([ord(ch)])),
    )

    assert font.encode("AZ") == b"AZ"
    assert PDType0Font._encode_codepoint(0x1234, None) == b"\x12\x34"  # noqa: SLF001


def test_wave585_read_font_bytes_accepts_binary_stream_and_rejects_object() -> None:
    assert type0_module._read_font_bytes(io.BytesIO(b"font-data")) == b"font-data"  # noqa: SLF001

    with pytest.raises(TypeError, match="cannot read font bytes"):
        type0_module._read_font_bytes(object())  # noqa: SLF001


def test_wave585_ps_name_uses_non_empty_record_text() -> None:
    record = SimpleNamespace(toUnicode=lambda: "  PostScriptName  ")
    name_table = SimpleNamespace(getName=lambda *_args: record)
    ttf = SimpleNamespace(_tt={"name": name_table})

    assert type0_module._ps_name_from_ttf(ttf, "Fallback") == "PostScriptName"  # noqa: SLF001


def test_wave585_build_type0_from_ttf_wires_parent_and_descendant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_ttf = object()
    fake_widths = COSArray()
    calls: list[object] = []

    import pypdfbox.fontbox.ttf as ttf_module

    monkeypatch.setattr(
        ttf_module.TrueTypeFont,
        "from_bytes",
        staticmethod(lambda data: fake_ttf if data == b"ttf" else None),
    )
    monkeypatch.setattr(type0_module, "_ps_name_from_ttf", lambda *_args: "BuiltPS")
    monkeypatch.setattr(
        type0_module,
        "_populate_descriptor_from_ttf",
        lambda *args: calls.append(args),
    )
    monkeypatch.setattr(type0_module, "_build_w_array", lambda _ttf: fake_widths)

    font = type0_module._build_type0_from_ttf(b"ttf", fallback_name="Fallback")  # noqa: SLF001

    assert font.get_base_font() == "BuiltPS"
    assert font.get_encoding().name == "Identity-H"
    descendant = font.get_descendant_font()
    assert isinstance(descendant, PDCIDFontType2)
    assert (
        descendant.get_cos_object().get_dictionary_object(COSName.get_pdf_name("W"))
        is fake_widths
    )
    assert calls


def test_wave585_subset_preserves_existing_subset_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Subsetter:
        def __init__(self, ttf: object) -> None:
            self.ttf = ttf

        def add_all(self, codepoints: set[int]) -> None:
            assert codepoints == {65}

        def set_prefix(self, prefix: str) -> None:
            assert prefix == "NEWTAG"

        def to_bytes(self) -> bytes:
            return b"subset"

    import pypdfbox.fontbox.ttf as ttf_module
    import pypdfbox.pdmodel.font.pd_true_type_font as true_type_module

    descendant = PDCIDFontType2()
    descendant.set_true_type_font(object())
    font = PDType0Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "ABCDEF+Original")
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    monkeypatch.setattr(descendant, "get_true_type_font", lambda: object())
    monkeypatch.setattr(ttf_module, "TTFSubsetter", Subsetter)
    monkeypatch.setattr(true_type_module, "_embed_subset_bytes", lambda *_args: None)

    assert font.subset("A", prefix="NEWTAG") == b"subset"
    assert font.get_base_font() == "ABCDEF+Original"
