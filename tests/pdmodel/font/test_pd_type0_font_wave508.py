from __future__ import annotations

import io
from types import SimpleNamespace

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.font import pd_type0_font as type0_module
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font


def test_wave508_get_cmap_stream_parser_failure_is_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.fontbox.cmap import CMapParser

    calls: list[bytes] = []

    def parse(self: CMapParser, data: bytes) -> object:
        calls.append(data)
        raise ValueError("bad cmap")

    stream = COSStream()
    stream.set_raw_data(b"not a cmap")
    font = PDType0Font()
    font.get_cos_object().set_item(COSName.get_pdf_name("Encoding"), stream)
    monkeypatch.setattr(CMapParser, "parse", parse)

    assert font.get_cmap() is None
    assert font.get_cmap() is None
    assert calls == [b"not a cmap"]


def test_wave508_get_to_unicode_predefined_name_success_is_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.fontbox.cmap import CMapParser

    parsed = object()
    calls: list[str] = []

    def parse_predefined(name: str) -> object:
        calls.append(name)
        return parsed

    font = PDType0Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("ToUnicode"), "Identity-H")
    monkeypatch.setattr(CMapParser, "parse_predefined", parse_predefined)

    assert font.get_to_unicode_cmap() is parsed
    assert font.get_to_unicode_cmap() is parsed
    assert calls == ["Identity-H"]


def test_wave508_read_stream_rewinds_overread_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    stream = io.BytesIO(b"abcdef")
    monkeypatch.setattr(font, "read_code", lambda data, offset: (0xAB, 2))

    assert font.read(stream) == 0xAB
    assert stream.read() == b"cdef"


def test_wave508_read_stream_without_data_returns_zero() -> None:
    assert PDType0Font().read(io.BytesIO()) == 0


def test_wave508_read_code_uses_cmap_and_forces_positive_consumed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class CMap:
        def read_code(self, stream: io.BytesIO) -> int:
            return 99

    font = PDType0Font()
    monkeypatch.setattr(font, "get_cmap", lambda: CMap())

    assert font.read_code(b"abc", 1) == (99, 1)


def test_wave508_encoding_helpers_handle_reverse_lookup_and_notdef() -> None:
    good = SimpleNamespace(
        get_codes_from_unicode=lambda text: b"\x01\x02" if text == "A" else None,
        get_name=lambda: "Custom-H",
        code_length_at=lambda _code: 3,
    )
    bad = SimpleNamespace(
        get_codes_from_unicode=lambda _text: (_ for _ in ()).throw(RuntimeError("bad")),
        get_name=lambda: "Custom-H",
        code_length_at=lambda _code: 4,
    )

    assert PDType0Font._encode_codepoint(ord("A"), good) == b"\x01\x02"  # noqa: SLF001
    assert PDType0Font._encode_codepoint(ord("B"), good) == b"\x00\x00\x00"  # noqa: SLF001
    assert PDType0Font._encode_codepoint(ord("C"), bad) == b"\x00\x00\x00\x00"  # noqa: SLF001


def test_wave508_identity_encoding_truncates_supplementary_codepoint() -> None:
    identity = SimpleNamespace(
        get_codes_from_unicode=lambda _text: None,
        get_name=lambda: "Identity-V",
        code_length_at=lambda _code: 2,
    )

    assert PDType0Font._encode_codepoint(0x10042, identity) == b"\x00\x42"  # noqa: SLF001


def test_wave508_is_latin_script_handles_gsub_errors_and_script_sets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()

    monkeypatch.setattr(
        font,
        "_get_gsub_table",
        lambda: SimpleNamespace(
            get_supported_script_tags=lambda: (_ for _ in ()).throw(RuntimeError("bad"))
        ),
    )
    assert font.get_gsub_features() == ["liga"]

    monkeypatch.setattr(
        font,
        "_get_gsub_table",
        lambda: SimpleNamespace(get_supported_script_tags=lambda: ["arab"]),
    )
    assert font.get_gsub_features() == []


def test_wave508_get_gsub_table_swallows_descendant_and_ttf_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    monkeypatch.setattr(
        font,
        "get_descendant_font",
        lambda: SimpleNamespace(
            get_true_type_font=lambda: (_ for _ in ()).throw(RuntimeError("bad"))
        ),
    )
    assert font._get_gsub_table() is None  # noqa: SLF001

    monkeypatch.setattr(
        font,
        "get_descendant_font",
        lambda: SimpleNamespace(
            get_true_type_font=lambda: SimpleNamespace(
                get_gsub=lambda: (_ for _ in ()).throw(RuntimeError("bad"))
            )
        ),
    )
    assert font._get_gsub_table() is None  # noqa: SLF001


def test_wave508_collect_gsub_feature_indices_reads_required_and_langsys() -> None:
    raw = SimpleNamespace(
        FeatureList=SimpleNamespace(
            FeatureRecord=[
                SimpleNamespace(FeatureTag="liga"),
                SimpleNamespace(FeatureTag="smcp"),
                SimpleNamespace(FeatureTag="kern"),
            ]
        ),
        ScriptList=SimpleNamespace(
            ScriptRecord=[
                SimpleNamespace(
                    Script=SimpleNamespace(
                        DefaultLangSys=SimpleNamespace(
                            ReqFeatureIndex=2,
                            FeatureIndex=[0],
                        ),
                        LangSysRecord=[
                            SimpleNamespace(
                                LangSys=SimpleNamespace(
                                    ReqFeatureIndex=0xFFFF,
                                    FeatureIndex=[1],
                                )
                            )
                        ],
                    )
                )
            ]
        ),
    )

    assert PDType0Font._collect_gsub_feature_indices(raw, ["smcp", "liga"]) == [1, 0]  # noqa: SLF001


def test_wave508_read_font_bytes_rejects_unknown_source_and_text_stream() -> None:
    with pytest.raises(TypeError, match="cannot read font bytes"):
        type0_module._read_font_bytes(object())  # noqa: SLF001

    with pytest.raises(TypeError, match="must yield bytes"):
        type0_module._read_font_bytes(io.StringIO("not bytes"))  # noqa: SLF001
