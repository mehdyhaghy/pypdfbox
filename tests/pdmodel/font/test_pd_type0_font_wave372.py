"""Wave 372 synthetic GSUB coverage for PDType0Font."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font


def _feature(tag: str, lookup_indices: list[int]) -> SimpleNamespace:
    return SimpleNamespace(
        FeatureTag=tag,
        Feature=SimpleNamespace(LookupListIndex=lookup_indices),
    )


def _lang_sys(*, req: int = 0xFFFF, indices: list[int] | None = None) -> SimpleNamespace:
    return SimpleNamespace(ReqFeatureIndex=req, FeatureIndex=indices or [])


def _script_record(
    default_ls: SimpleNamespace | None, *lang_systems: SimpleNamespace
) -> SimpleNamespace:
    return SimpleNamespace(
        Script=SimpleNamespace(
            DefaultLangSys=default_ls,
            LangSysRecord=[SimpleNamespace(LangSys=ls) for ls in lang_systems],
        )
    )


def _raw_table(
    feature_records: list[SimpleNamespace],
    lookups: list[SimpleNamespace],
    script_records: list[SimpleNamespace],
) -> SimpleNamespace:
    return SimpleNamespace(
        FeatureList=SimpleNamespace(FeatureRecord=feature_records),
        LookupList=SimpleNamespace(Lookup=lookups),
        ScriptList=SimpleNamespace(ScriptRecord=script_records),
    )


class _FakeGsub:
    def __init__(
        self,
        raw: SimpleNamespace | None = None,
        *,
        glyph_order: list[str] | None = None,
        scripts: list[str] | None = None,
    ) -> None:
        self._raw = raw
        self._glyph_order = glyph_order or []
        self._glyph_name_to_gid = {name: i for i, name in enumerate(self._glyph_order)}
        self._scripts = scripts

    def get_raw_table(self) -> SimpleNamespace | None:
        return self._raw

    def get_supported_script_tags(self) -> list[str]:
        if self._scripts is None:
            raise RuntimeError("script parse failed")
        return self._scripts

    def get_substitution(self, gid: int, _script: object, _features: list[str]) -> int:
        return gid + 10


class _FakeTTF:
    def __init__(self, gsub: _FakeGsub | None = None, *, raises: bool = False) -> None:
        self._gsub = gsub
        self._raises = raises

    def get_gsub(self) -> _FakeGsub | None:
        if self._raises:
            raise RuntimeError("bad gsub")
        return self._gsub


class _FakeDescendant:
    def __init__(self, ttf: _FakeTTF | None = None, *, raises: bool = False) -> None:
        self._ttf = ttf
        self._raises = raises

    def get_true_type_font(self) -> _FakeTTF | None:
        if self._raises:
            raise RuntimeError("bad ttf")
        return self._ttf

    def cid_to_gid(self, cid: int) -> int:
        return cid + 1


def test_set_gsub_features_deduplicates_preserving_order_and_reset() -> None:
    font = PDType0Font()
    font.set_gsub_features(["liga", "liga", "sups", 7])

    assert font.get_gsub_features() == ["liga", "sups", "7"]

    font.set_gsub_features(None)

    assert font.get_gsub_features() == ["liga"]


def test_is_latin_script_false_when_gsub_has_only_non_latin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    monkeypatch.setattr(font, "_get_gsub_table", lambda: _FakeGsub(scripts=["arab"]))

    assert font.get_gsub_features() == []


def test_is_latin_script_true_when_gsub_script_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    monkeypatch.setattr(font, "_get_gsub_table", lambda: _FakeGsub(scripts=None))

    assert font.get_gsub_features() == ["liga"]


@pytest.mark.parametrize(
    ("descendant", "expected"),
    [
        (None, None),
        (object(), None),
        (_FakeDescendant(raises=True), None),
        (_FakeDescendant(None), None),
        (_FakeDescendant(_FakeTTF(raises=True)), None),
        (_FakeDescendant(_FakeTTF(_FakeGsub(scripts=[]))), _FakeGsub),
    ],
)
def test_get_gsub_table_defensive_descendant_paths(
    monkeypatch: pytest.MonkeyPatch,
    descendant: object,
    expected: type[_FakeGsub] | None,
) -> None:
    font = PDType0Font()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)

    out = font._get_gsub_table()  # noqa: SLF001

    if expected is None:
        assert out is None
    else:
        assert isinstance(out, expected)


def test_code_to_gid_applies_single_gsub_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    descendant = _FakeDescendant(_FakeTTF(_FakeGsub(scripts=["latn"])))
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    monkeypatch.setattr(font, "code_to_cid", lambda code: code + 4)

    assert font.code_to_gid(3) == 18


def test_apply_gsub_features_early_returns_are_copies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    glyphs = [1, 2]

    assert font.apply_gsub_features([]) == []

    monkeypatch.setattr(font, "_get_gsub_table", lambda: None)
    out = font.apply_gsub_features(glyphs)
    assert out == glyphs
    assert out is not glyphs

    monkeypatch.setattr(font, "_get_gsub_table", lambda: _FakeGsub(raw=None))
    assert font.apply_gsub_features(glyphs) == glyphs

    font.set_gsub_features([])
    raw = _raw_table([], [], [])
    monkeypatch.setattr(font, "_get_gsub_table", lambda: _FakeGsub(raw=raw))
    assert font.apply_gsub_features(glyphs) == glyphs


def test_collect_gsub_feature_indices_deduplicates_and_orders_enabled_tags() -> None:
    raw = _raw_table(
        [_feature("liga", []), _feature("smcp", []), _feature("kern", [])],
        [],
        [
            _script_record(
                _lang_sys(req=2, indices=[0, 1]),
                _lang_sys(indices=[1, 0]),
            )
        ],
    )

    assert PDType0Font._collect_gsub_feature_indices(raw, ["smcp", "liga"]) == [1, 0]


def test_apply_single_run_rewrites_known_glyphs_and_leaves_misses() -> None:
    lookup = SimpleNamespace(
        SubTable=[
            SimpleNamespace(mapping=None),
            SimpleNamespace(mapping={"a": "a.sc", "b": "missing"}),
        ]
    )

    out = PDType0Font._apply_single_run(
        lookup,
        [1, 2, 99],
        [".notdef", "a", "b"],
        {"a.sc": 7},
    )

    assert out == [7, 2, 99]


def test_apply_ligature_run_prefers_longest_match_and_leaves_partial_misses() -> None:
    lookup = SimpleNamespace(
        SubTable=[
            SimpleNamespace(ligatures=None),
            SimpleNamespace(
                ligatures={
                    "f": [
                        SimpleNamespace(Component=["i"], LigGlyph="fi"),
                        SimpleNamespace(Component=["i", "f"], LigGlyph="fif"),
                        SimpleNamespace(Component=["missing"], LigGlyph="bad"),
                    ]
                }
            ),
        ]
    )
    glyph_order = [".notdef", "f", "i", "fi", "fif", "x"]
    name_to_gid = {name: i for i, name in enumerate(glyph_order)}

    assert PDType0Font._apply_ligature_run(
        lookup, [1, 2, 5], glyph_order, name_to_gid
    ) == [3, 5]
    assert PDType0Font._apply_ligature_run(
        lookup, [1, 2, 1], glyph_order, name_to_gid
    ) == [4]


def test_apply_gsub_features_runs_ligature_and_single_features_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ligature_lookup = SimpleNamespace(
        LookupType=4,
        SubTable=[
            SimpleNamespace(
                ligatures={
                    "f": [SimpleNamespace(Component=["i"], LigGlyph="fi")]
                }
            )
        ],
    )
    single_lookup = SimpleNamespace(
        LookupType=1,
        SubTable=[SimpleNamespace(mapping={"a": "a.sc"})],
    )
    unsupported_lookup = SimpleNamespace(LookupType=7, SubTable=[])
    raw = _raw_table(
        [
            _feature("liga", [-1, 0, 99, 2]),
            _feature("smcp", [1]),
        ],
        [ligature_lookup, single_lookup, unsupported_lookup],
        [_script_record(_lang_sys(indices=[0, 1]))],
    )
    gsub = _FakeGsub(raw, glyph_order=[".notdef", "f", "i", "fi", "a", "a.sc"])
    font = PDType0Font()
    font.set_gsub_features(["liga", "smcp"])
    monkeypatch.setattr(font, "_get_gsub_table", lambda: gsub)

    assert font.apply_gsub_features([1, 2, 4]) == [3, 5]


def test_encode_string_falls_back_for_empty_non_identity_or_missing_gsub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()

    assert font.encode_string("") == b""

    monkeypatch.setattr(font, "get_cmap", lambda: SimpleNamespace(get_name=lambda: "Custom-H"))
    monkeypatch.setattr(font, "encode", lambda text: b"fallback")
    assert font.encode_string("A") == b"fallback"

    monkeypatch.setattr(font, "get_cmap", lambda: SimpleNamespace(get_name=lambda: "Identity-H"))
    monkeypatch.setattr(font, "_get_gsub_table", lambda: None)
    assert font.encode_string("A") == b"fallback"


def test_encode_string_emits_post_gsub_glyph_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    font = PDType0Font()
    monkeypatch.setattr(font, "get_cmap", lambda: SimpleNamespace(get_name=lambda: "Identity-H"))
    monkeypatch.setattr(font, "_get_gsub_table", lambda: _FakeGsub(scripts=["latn"]))
    monkeypatch.setattr(font, "code_to_gid", lambda code: code - 60)
    monkeypatch.setattr(font, "apply_gsub_features", lambda gids: [gids[0] + 100, 0x10042])

    assert font.encode_string("AB") == b"\x00\x69\x00\x42"
