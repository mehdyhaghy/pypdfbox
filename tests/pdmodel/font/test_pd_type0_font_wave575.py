from __future__ import annotations

from types import SimpleNamespace

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.font import pd_type0_font as type0_module
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font


def test_wave575_gsub_empty_scripts_and_apply_noop_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    monkeypatch.setattr(
        font,
        "_get_gsub_table",
        lambda: SimpleNamespace(
            get_supported_script_tags=lambda: [],
            get_raw_table=lambda: object(),
            _glyph_order=[],
            _glyph_name_to_gid={},
        ),
    )

    assert font.get_gsub_features() == ["liga"]
    assert font.apply_gsub_features([1, 2]) == [1, 2]

    monkeypatch.setattr(
        font,
        "_get_gsub_table",
        lambda: SimpleNamespace(
            get_raw_table=lambda: object(),
            _glyph_order=[".notdef"],
            _glyph_name_to_gid={".notdef": 0},
        ),
    )
    monkeypatch.setattr(font, "_collect_gsub_feature_indices", lambda *_args: [])

    assert font.apply_gsub_features([0]) == [0]


def test_wave575_apply_gsub_features_skips_out_of_range_feature_indices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature = SimpleNamespace(
        FeatureTag="liga",
        Feature=SimpleNamespace(LookupListIndex=[0]),
    )
    raw = SimpleNamespace(
        FeatureList=SimpleNamespace(FeatureRecord=[feature]),
        LookupList=SimpleNamespace(
            Lookup=[SimpleNamespace(LookupType=99, SubTable=[])]
        ),
    )
    font = PDType0Font()
    font.set_gsub_features(["liga"])
    monkeypatch.setattr(
        font,
        "_get_gsub_table",
        lambda: SimpleNamespace(
            get_raw_table=lambda: raw,
            _glyph_order=[".notdef", "A"],
            _glyph_name_to_gid={".notdef": 0, "A": 1},
        ),
    )
    monkeypatch.setattr(
        font, "_collect_gsub_feature_indices", lambda *_args: [-1, 99, 0]
    )

    assert font.apply_gsub_features([1]) == [1]


def test_wave575_collect_feature_indices_ignores_missing_langsys() -> None:
    raw = SimpleNamespace(
        FeatureList=SimpleNamespace(FeatureRecord=[]),
        ScriptList=SimpleNamespace(
            ScriptRecord=[
                SimpleNamespace(
                    Script=SimpleNamespace(DefaultLangSys=None, LangSysRecord=[])
                )
            ]
        ),
    )

    assert PDType0Font._collect_gsub_feature_indices(raw, ["liga"]) == []  # noqa: SLF001


def test_wave575_ligature_candidate_longer_than_run_is_ignored() -> None:
    lookup = SimpleNamespace(
        SubTable=[
            SimpleNamespace(
                ligatures={
                    "f": [
                        SimpleNamespace(Component=["i", "extra"], LigGlyph="f_i")
                    ]
                }
            )
        ]
    )

    assert PDType0Font._apply_ligature_run(  # noqa: SLF001
        lookup,
        [1, 2],
        [".notdef", "f", "i", "f_i"],
        {".notdef": 0, "f": 1, "i": 2, "f_i": 3},
    ) == [1, 2]


def test_wave575_explicit_writing_mode_false_for_non_stream_encoding() -> None:
    font = PDType0Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("Identity-H")
    )

    assert font.has_explicit_writing_mode() is False


def test_wave575_embedded_cmap_fallback_negative_shapes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()

    assert font._unicode_from_embedded_cmap(1) is None  # noqa: SLF001

    class InnerTTF(dict):
        def getGlyphOrder(self) -> list[str]:
            return [".notdef", "target"]

    descendant = PDCIDFontType2()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    monkeypatch.setattr(font, "code_to_cid", lambda code: code)
    monkeypatch.setattr(descendant, "is_embedded", lambda: True)
    monkeypatch.setattr(descendant, "code_to_gid", lambda _cid: 3)
    monkeypatch.setattr(
        descendant,
        "get_true_type_font",
        lambda: SimpleNamespace(_tt=InnerTTF(cmap=SimpleNamespace(getBestCmap=lambda: {}))),
    )

    assert font._unicode_from_embedded_cmap(1) is None  # noqa: SLF001

    monkeypatch.setattr(descendant, "code_to_gid", lambda _cid: 1)
    monkeypatch.setattr(
        descendant,
        "get_true_type_font",
        lambda: SimpleNamespace(
            _tt=InnerTTF(cmap=SimpleNamespace(getBestCmap=lambda: {65: "other"}))
        ),
    )

    assert font._unicode_from_embedded_cmap(1) is None  # noqa: SLF001


def test_wave575_ttf_helpers_fall_back_for_malformed_names_and_units() -> None:
    assert type0_module._ps_name_from_ttf(SimpleNamespace(_tt={}), "Fallback") == "Fallback"  # noqa: SLF001
    assert (
        type0_module._ps_name_from_ttf(  # noqa: SLF001
            SimpleNamespace(
                _tt={
                    "name": SimpleNamespace(
                        getName=lambda *_args: None,
                    )
                }
            ),
            "Fallback",
        )
        == "Fallback"
    )

    head = SimpleNamespace(
        get_units_per_em=lambda: 0,
        get_x_min=lambda: -1,
        get_y_min=lambda: -2,
        get_x_max=lambda: 3,
        get_y_max=lambda: 4,
    )
    hhea = SimpleNamespace(get_ascender=lambda: 8, get_descender=lambda: -3)
    descriptor = PDFontDescriptor()
    type0_module._populate_descriptor_from_ttf(  # noqa: SLF001
        descriptor,
        SimpleNamespace(get_header=lambda: head, get_horizontal_header=lambda: hhea),
    )

    assert descriptor.get_cos_object().get_int(COSName.get_pdf_name("Ascent")) == 8

    widths = type0_module._build_w_array(  # noqa: SLF001
        SimpleNamespace(get_header=lambda: head, advance_widths=[1, 2])
    )

    assert widths.get(1).size() == 2
