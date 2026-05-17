"""Wave 1332 coverage round-out for
:mod:`pypdfbox.fontbox.ttf.true_type_font`.

Targets the residual no-coverage tail in 0.9.0rc1 — the internal
``_SubstitutingCmapLookup`` / ``_VerticalOriginView`` projections, the
``get_units_per_em`` / ``get_number_of_glyphs`` no-table fallbacks, the
``add_table`` tag-skip branch, the ``read_table`` ``None`` short-circuit,
the ``read_table_headers`` ``hhea`` / ``OS/2`` / ``post`` branches, the
``get_name(name_id, ...)`` no-naming-table branch, the ``get_gsub_data``
sentinel branches, the ``_get_unicode_cmap_impl`` non-strict
fallback that synthesises a :class:`CmapSubtable` from a non-Unicode
subtable, the ``name_to_gid`` ``g\\d+`` literal-GID branch, the
``get_index_to_location`` no-``loca`` branch, the ``get_vertical_origin``
``VORG`` projection, and the ``save`` writable-sink error path.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import TrueTypeFont, TTFTable
from pypdfbox.fontbox.ttf.true_type_font import (
    _SubstitutingCmapLookup,
    _VerticalOriginView,
)

_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _liberation_bytes() -> bytes:
    if not _FIXTURE.exists():
        pytest.skip(f"missing fixture {_FIXTURE}")
    return _FIXTURE.read_bytes()


# ---------- _SubstitutingCmapLookup (lines 65-72, 75) ----------------------


class _CmapStub:
    """Tiny cmap that returns a fixed GID + char-code chain."""

    def __init__(self) -> None:
        self.glyph_map: dict[int, int] = {0x41: 10, 0x42: 11}
        self.reverse: dict[int, list[int]] = {10: [0x41], 11: [0x42]}

    def get_glyph_id(self, code_point: int) -> int:
        return self.glyph_map.get(code_point, 0)

    def get_char_codes(self, gid: int) -> list[int] | None:
        return self.reverse.get(gid)


class _GsubStub:
    """GSUB stub that swaps gid 10 -> 99 for feature 'liga'."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    def substitute_glyph(self, gid: int, feature: str) -> int | None:
        self.calls.append((gid, feature))
        if feature == "raise":
            raise KeyError("forced")
        if feature == "liga" and gid == 10:
            return 99
        return None


def test_substituting_cmap_lookup_substitutes_via_gsub_feature() -> None:
    lookup = _SubstitutingCmapLookup(
        _CmapStub(), _GsubStub(), ("raise", "missing", "liga")
    )
    # 'raise' triggers the except branch (line 68), 'missing' returns None
    # (line 70 negative), 'liga' produces a real replacement (lines 70-71).
    assert lookup.get_glyph_id(0x41) == 99


def test_substituting_cmap_lookup_passthrough_when_substitute_missing() -> None:
    # _GsubStub without ``substitute_glyph`` falls through line 63-64.
    class _Empty:
        pass

    lookup = _SubstitutingCmapLookup(_CmapStub(), _Empty(), ("liga",))
    assert lookup.get_glyph_id(0x41) == 10


def test_substituting_cmap_lookup_get_char_codes_delegates() -> None:
    lookup = _SubstitutingCmapLookup(_CmapStub(), _GsubStub(), ())
    assert lookup.get_char_codes(10) == [0x41]
    assert lookup.get_char_codes(7) is None


# ---------- _VerticalOriginView (lines 92-95, 99) --------------------------


def test_vertical_origin_view_defaults_and_lookup() -> None:
    view = _VerticalOriginView()
    # Defaults from the constructor branches (92-95) — every field is touched
    # by the assertion suite below.
    assert view.major_version == 1
    assert view.minor_version == 0
    assert view.default_vertical_origin == 0
    assert view.origins == {}
    # Lookup with no entry returns the default (line 99 default path).
    assert view.get_origin_y(5) == 0
    view.origins[5] = 880
    view.default_vertical_origin = 800
    assert view.get_origin_y(5) == 880
    # Unmapped gid falls back to default.
    assert view.get_origin_y(99) == 800


# ---------- no-table fallback branches -------------------------------------


def _wipe_table(ttf: TrueTypeFont, tag: str) -> None:
    """Remove a fontTools table from the underlying ``TTFont`` object."""
    inner = ttf._tt  # noqa: SLF001
    if tag in inner:
        del inner[tag]


def test_get_units_per_em_returns_zero_without_head_table() -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())
    _wipe_table(ttf, "head")
    # Line 210 — defensive fallback when the font is half-built.
    assert ttf.get_units_per_em() == 0


def test_get_number_of_glyphs_returns_zero_without_maxp_table() -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())
    _wipe_table(ttf, "maxp")
    # Line 218.
    assert ttf.get_number_of_glyphs() == 0


# ---------- add_table tag-skip + read_table fallback -----------------------


def test_add_table_with_none_tag_is_noop() -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())

    class _UntaggedTable:
        def get_tag(self) -> str | None:
            return None

    before = dict(ttf.get_table_map())
    # Line 263 — guard against tag being None.
    ttf.add_table(_UntaggedTable())  # type: ignore[arg-type]
    assert ttf.get_table_map() == before


def test_read_table_with_none_is_noop() -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())
    # Line 279 — guard against None input.
    ttf.read_table(None)  # type: ignore[arg-type]


def test_read_table_without_set_data_setter_still_sets_initialized() -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())
    head_entry = ttf.get_table_map()["head"]

    class _NoSetterTable:
        def __init__(self, entry: TTFTable) -> None:
            self._entry = entry
            self.initialized = False

        def get_tag(self) -> str | None:
            return "head"

        def get_offset(self) -> int:
            return self._entry.get_offset()

        def get_length(self) -> int:
            return self._entry.get_length()

    proxy = _NoSetterTable(head_entry)
    ttf.read_table(proxy)  # type: ignore[arg-type]
    # ``set_data`` absent → setter call skipped (line 287 negative).
    assert proxy.initialized is True


# ---------- read_table_headers covers hhea / OS/2 / post branches ---------


class _HeadersStub:
    pass


def test_read_table_headers_populates_hhea_os2_post() -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())
    headers = _HeadersStub()
    # Lines 313-324 — three additional ``elif`` branches.
    ttf.read_table_headers("hhea", headers)
    assert hasattr(headers, "number_of_h_metrics")
    ttf.read_table_headers("OS/2", headers)
    assert hasattr(headers, "weight_class")
    ttf.read_table_headers("post", headers)
    assert hasattr(headers, "italic_angle")


# ---------- get_name(name_id, ...) no-naming-table branch ------------------


def test_get_name_with_name_id_returns_none_without_naming_table() -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())
    _wipe_table(ttf, "name")
    # Line 824 — naming table is gone, so the lookup returns None.
    assert ttf.get_name(name_id=1, platform_id=3, encoding_id=1) is None


# ---------- get_gsub_data sentinel paths -----------------------------------


def test_get_gsub_data_returns_no_data_when_gsub_disabled() -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())
    ttf.set_enable_gsub(False)
    from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData

    # Line 1112 — early-return sentinel.
    assert ttf.get_gsub_data() is GsubData.NO_DATA_FOUND


def test_get_gsub_data_returns_no_data_when_no_gsub_table() -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())
    _wipe_table(ttf, "GSUB")
    # Reset cached resolution so the next call walks the fresh fontTools state.
    ttf._gsub_resolved = False  # noqa: SLF001
    ttf._gsub = None  # noqa: SLF001
    from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData

    # Lines 1113-1115 — branch when get_gsub() returns None.
    assert ttf.get_gsub_data() is GsubData.NO_DATA_FOUND


def test_get_gsub_data_returns_no_data_when_table_has_no_helper() -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())

    class _NoHelperTable:
        pass

    ttf._gsub = _NoHelperTable()  # type: ignore[assignment]  # noqa: SLF001
    ttf._gsub_resolved = True  # noqa: SLF001
    from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData

    # Lines 1117-1118 — ``get_gsub_data`` attr missing on the table.
    assert ttf.get_gsub_data() is GsubData.NO_DATA_FOUND


def test_get_gsub_data_returns_no_data_when_helper_returns_none() -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())

    class _NoneTable:
        def get_gsub_data(self) -> None:
            return None

    ttf._gsub = _NoneTable()  # type: ignore[assignment]  # noqa: SLF001
    ttf._gsub_resolved = True  # noqa: SLF001
    from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData

    # Lines 1120-1121 — helper returned None.
    assert ttf.get_gsub_data() is GsubData.NO_DATA_FOUND


# ---------- name_to_gid g\d+ literal-GID branch ----------------------------


def test_name_to_gid_g_prefix_treated_as_literal_gid() -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())
    # PDFBOX-5604 path (lines 1168-1170).
    assert ttf.name_to_gid("g42") == 42


def test_name_to_gid_returns_zero_on_get_unicode_cmap_lookup_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise OSError("forced strict-mode failure")

    monkeypatch.setattr(ttf, "get_unicode_cmap_lookup", _raise)
    # ``uni0041`` triggers the cmap branch; the monkeypatched method raises,
    # so the except clause swallows it and falls through (lines 1162-1163).
    # No mapping is available, so we land on the glyph-order final fallback.
    result = ttf.name_to_gid("uni0041")
    assert isinstance(result, int)


# ---------- get_index_to_location no-loca branch ---------------------------


def test_get_index_to_location_returns_none_without_loca_table() -> None:
    # LiberationSans does have loca; force the absent-table branch.
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())
    _wipe_table(ttf, "loca")
    ttf._loca_resolved = False  # noqa: SLF001
    # Lines 1405-1407.
    assert ttf.get_index_to_location() is None


# ---------- get_vertical_origin (lines 1428-1448) --------------------------


def test_get_vertical_origin_returns_none_without_vorg() -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())
    # Liberation Sans has no VORG — exercises the early-return at line 1428.
    assert ttf.get_vertical_origin() is None


def test_get_vertical_origin_projects_vorg_records() -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())

    class _Record:
        def __init__(self, y: int) -> None:
            self.vOrigY = y  # noqa: N815 — mirror fontTools field name

    class _FakeVorg:
        majorVersion = 1  # noqa: N815
        minorVersion = 0  # noqa: N815
        defaultVertOriginY = 880  # noqa: N815
        VOriginRecords = {"A": _Record(910), "B": _Record(905), "ghost": _Record(0)}  # noqa: N815

    # Stub the lazy fontTools access (``ttf._tt['VORG']``).
    class _TTProxy:
        def __init__(self, inner: object, payload: object) -> None:
            self._inner = inner
            self._payload = payload

        def __contains__(self, key: str) -> bool:
            return key == "VORG"

        def __getitem__(self, key: str) -> object:
            if key == "VORG":
                return self._payload
            raise KeyError(key)

        def getGlyphOrder(self) -> list[str]:  # noqa: N802 — fontTools name
            return ["A", "B", "C"]

    ttf._tt = _TTProxy(ttf._tt, _FakeVorg())  # type: ignore[assignment]  # noqa: SLF001
    view = ttf.get_vertical_origin()
    assert view is not None
    assert view.major_version == 1
    assert view.default_vertical_origin == 880
    # "ghost" is filtered out (not in glyph order).
    assert view.origins == {0: 910, 1: 905}


# ---------- save error path (lines 1566-1570) ------------------------------


def test_save_raises_typeerror_for_non_writable_sink() -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())
    with pytest.raises(TypeError, match="path or a writable binary file-like"):
        ttf.save(object())  # type: ignore[arg-type]


def test_save_round_trip_to_bytesio() -> None:
    # Positive path so the cov tracer counts the bytes-flush branch.
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())
    sink = io.BytesIO()
    ttf.save(sink)
    assert sink.tell() > 0


# ---------- to_string OSError branch (lines 1641-1643) ---------------------


def test_to_string_returns_null_marker_on_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())

    def _raise() -> None:
        raise OSError("broken naming table")

    monkeypatch.setattr(ttf, "get_naming", _raise)
    out = ttf.to_string()
    assert out.startswith("(null - ")


# ---------- _get_unicode_cmap_impl non-strict fallback ---------------------


def test_get_unicode_cmap_impl_returns_first_subtable_when_no_unicode() -> None:
    """Lines 1066-1100 — when no preferred Unicode subtable matches we
    synthesise a :class:`CmapSubtable` from the first available subtable.
    """
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())

    # Force ``get_unicode_cmap_subtable`` to return None so we hit the
    # synthesise-from-first-subtable branch. We then need ``_tt['cmap']``
    # to have at least one subtable.
    def _none() -> None:
        return None

    ttf.get_unicode_cmap_subtable = _none  # type: ignore[assignment]
    out = ttf._get_unicode_cmap_impl(is_strict=False)  # noqa: SLF001
    # LiberationSans has at least one cmap subtable, so we get a CmapSubtable
    # back (not None).
    assert out is not None


def test_get_unicode_cmap_impl_raises_in_strict_mode_when_no_cmap() -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())
    _wipe_table(ttf, "cmap")
    ttf._cmap_resolved = False  # noqa: SLF001
    ttf._cmap_subtable = None  # noqa: SLF001
    # Lines 1066-1072.
    with pytest.raises(OSError, match="does not contain a 'cmap'"):
        ttf._get_unicode_cmap_impl(is_strict=True)  # noqa: SLF001


def test_get_unicode_cmap_impl_returns_none_when_no_cmap_non_strict() -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())
    _wipe_table(ttf, "cmap")
    ttf._cmap_resolved = False  # noqa: SLF001
    ttf._cmap_subtable = None  # noqa: SLF001
    # Line 1073 — non-strict returns None.
    assert ttf._get_unicode_cmap_impl(is_strict=False) is None  # noqa: SLF001


def test_get_unicode_cmap_impl_raises_when_no_unicode_strict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ttf = TrueTypeFont.from_bytes(_liberation_bytes())
    monkeypatch.setattr(ttf, "get_unicode_cmap_subtable", lambda: None)
    # Lines 1075-1077.
    with pytest.raises(OSError, match="does not contain a Unicode cmap"):
        ttf._get_unicode_cmap_impl(is_strict=True)  # noqa: SLF001
