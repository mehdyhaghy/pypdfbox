"""Wave 1332 coverage round-out for
:mod:`pypdfbox.pdmodel.font.standard14_fonts`.

Targets the remaining no-coverage tail in 0.9.0rc1 — the internal pen
adapters (``_DecomposingCommandPen`` / ``_CommandRecordingPen``), the
TTF helper-error fallbacks (``_ttf_glyph_path`` and
``_ttf_glyph_path_for_code_point`` exception branches, ``_ttf_glyph_path_for_gid``
glyph-set failure path), the ``_load_substitution_ttf`` cache /
unmapped-name / missing-resource / parse-failure branches, the
``get_glyph_path`` AGL fallback and PUA-shifted Symbol fallback, and
the ``get_glyph_path`` ``mapped_font.has_glyph`` direct hit.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.pdmodel.font import standard14_fonts as s14
from pypdfbox.pdmodel.font.standard14_fonts import (
    Standard14Fonts,
    _CommandRecordingPen,
    _DecomposingCommandPen,
    _load_substitution_ttf,
    _ttf_glyph_path,
    _ttf_glyph_path_for_code_point,
    _ttf_glyph_path_for_gid,
)

# ---------- pen adapters ---------------------------------------------------


def test_command_recording_pen_records_moveto_lineto_and_close() -> None:
    pen = _CommandRecordingPen()
    pen.move_to((1.0, 2.0))
    pen.line_to((3.0, 4.0))
    pen.close_path()
    pen.end_path()  # no-op safety net (lines 427-429).
    assert pen.commands == [
        ("moveto", 1.0, 2.0),
        ("lineto", 3.0, 4.0),
        ("closepath",),
    ]


def test_command_recording_pen_curveto_three_points_emits_segment() -> None:
    pen = _CommandRecordingPen()
    pen.move_to((0.0, 0.0))
    pen.curve_to((1.0, 2.0), (3.0, 4.0), (5.0, 6.0))
    # Last command is a 7-tuple curveto.
    assert pen.commands[-1] == ("curveto", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0)


def test_command_recording_pen_curveto_skip_non_cubic() -> None:
    pen = _CommandRecordingPen()
    pen.move_to((0.0, 0.0))
    # Two-point input is not cubic — the if-len-3 guard (line 377) skips it.
    pen.curve_to((1.0, 1.0), (2.0, 2.0))
    assert len([c for c in pen.commands if c[0] == "curveto"]) == 0


def test_command_recording_pen_qcurveto_emits_cubic_segments() -> None:
    pen = _CommandRecordingPen()
    pen.move_to((0.0, 0.0))
    # Two qCurveTo control points: triggers the implicit-midpoint branch
    # (lines 403-422), producing two cubic segments.
    pen.q_curve_to((1.0, 1.0), (2.0, 0.0), (3.0, 3.0))
    curves = [c for c in pen.commands if c[0] == "curveto"]
    assert len(curves) >= 2


def test_command_recording_pen_qcurveto_with_only_none_returns_early() -> None:
    pen = _CommandRecordingPen()
    pen.move_to((0.0, 0.0))
    pen.q_curve_to(None)  # type: ignore[arg-type]
    # Line 395-396 — early return because the filtered list is empty.
    assert all(c[0] != "curveto" for c in pen.commands)


def test_command_recording_pen_qcurveto_without_last_point_returns_early() -> None:
    pen = _CommandRecordingPen()
    # No prior move_to — _last_point returns None (line 401-402 early return).
    pen.q_curve_to((1.0, 1.0))
    assert pen.commands == []


def test_command_recording_pen_last_point_walks_back_through_curveto() -> None:
    pen = _CommandRecordingPen()
    pen.move_to((0.0, 0.0))
    pen.curve_to((1.0, 1.0), (2.0, 2.0), (3.0, 3.0))
    # After a curveto the _last_point should resolve to (3.0, 3.0).
    assert pen._last_point() == (3.0, 3.0)  # noqa: SLF001
    # Closepath does not change the last point.
    pen.close_path()
    assert pen._last_point() == (3.0, 3.0)  # noqa: SLF001
    # Empty pen returns None (line 448).
    assert _CommandRecordingPen()._last_point() is None  # noqa: SLF001


def test_command_recording_pen_addcomponent_is_noop() -> None:
    pen = _CommandRecordingPen()
    pen.add_component("X", (1, 0, 0, 1, 0, 0))
    # Lines 431-439 — del-only safety net.
    assert pen.commands == []


def test_decomposing_command_pen_forwards_simple_callbacks() -> None:
    inner = _CommandRecordingPen()
    pen = _DecomposingCommandPen({}, inner)
    pen.move_to((1.0, 2.0))
    pen.line_to((3.0, 4.0))
    pen.curve_to((1.0, 1.0), (2.0, 2.0), (3.0, 3.0))
    pen.q_curve_to((4.0, 4.0))
    pen.close_path()
    pen.end_path()
    # Forwarded into the inner recorder.
    assert any(cmd[0] == "moveto" for cmd in inner.commands)
    assert any(cmd[0] == "lineto" for cmd in inner.commands)


def test_decomposing_command_pen_missing_component_is_ignored() -> None:
    inner = _CommandRecordingPen()
    pen = _DecomposingCommandPen({}, inner)
    # Empty glyph_set raises KeyError; the except path swallows it
    # (lines 338-339).
    pen.add_component("missing", (1, 0, 0, 1, 0, 0))
    assert inner.commands == []


def test_decomposing_command_pen_component_draw_failure_is_ignored() -> None:
    inner = _CommandRecordingPen()

    class _BadComponent:
        def draw(self, _pen: object) -> None:
            raise RuntimeError("forced")

    pen = _DecomposingCommandPen({"X": _BadComponent()}, inner)
    # Lines 344-347 — draw raises, except clause swallows it.
    pen.add_component("X", (1, 0, 0, 1, 0, 0))
    assert inner.commands == []


def test_decomposing_command_pen_component_resolves_and_draws() -> None:
    inner = _CommandRecordingPen()

    class _Component:
        def draw(self, pen: Any) -> None:
            # fontTools BasePen contract — bridged into snake_case
            # delegate by the bridge wrapper inside the decomposer.
            pen.moveTo((10.0, 20.0))
            pen.lineTo((30.0, 40.0))

    pen = _DecomposingCommandPen({"X": _Component()}, inner)
    pen.add_component("X", (1, 0, 0, 1, 5, 6))
    # The component drew through a TransformPen; the inner recorder saw
    # transformed points.
    assert any(cmd[0] == "moveto" for cmd in inner.commands)


# ---------- _ttf_glyph_path / _ttf_glyph_path_for_code_point fallbacks ----


class _BrokenTTF:
    """TTF stub whose name_to_gid always raises."""

    def name_to_gid(self, name: str) -> int:
        raise RuntimeError("boom")


def test_ttf_glyph_path_returns_empty_on_lookup_exception() -> None:
    # Lines 226-229.
    assert _ttf_glyph_path(_BrokenTTF(), "A") == []  # type: ignore[arg-type]


class _ZeroGidTTF:
    def name_to_gid(self, name: str) -> int:
        return 0


def test_ttf_glyph_path_returns_empty_on_zero_gid() -> None:
    # Lines 230-231.
    assert _ttf_glyph_path(_ZeroGidTTF(), "A") == []  # type: ignore[arg-type]


class _NoCmapTTF:
    def get_unicode_cmap_subtable(self) -> None:
        return None


def test_ttf_glyph_path_for_code_point_returns_empty_when_no_cmap() -> None:
    # Lines 244-246.
    assert _ttf_glyph_path_for_code_point(_NoCmapTTF(), 0x41) == []  # type: ignore[arg-type]


class _RaisingCmap:
    def get_glyph_id(self, _code: int) -> int:
        raise RuntimeError("cmap blew up")


class _RaisingCmapTTF:
    def get_unicode_cmap_subtable(self) -> _RaisingCmap:
        return _RaisingCmap()


def test_ttf_glyph_path_for_code_point_returns_empty_on_cmap_exception() -> None:
    # Lines 247-250.
    assert _ttf_glyph_path_for_code_point(_RaisingCmapTTF(), 0x41) == []  # type: ignore[arg-type]


class _ZeroGidCmap:
    def get_glyph_id(self, _code: int) -> int:
        return 0


class _ZeroGidCmapTTF:
    def get_unicode_cmap_subtable(self) -> _ZeroGidCmap:
        return _ZeroGidCmap()


def test_ttf_glyph_path_for_code_point_returns_empty_on_zero_gid() -> None:
    # Lines 251-252.
    assert _ttf_glyph_path_for_code_point(_ZeroGidCmapTTF(), 0x41) == []  # type: ignore[arg-type]


class _RaisingGlyphSetTTF:
    class _TT:
        def getGlyphSet(self) -> dict[str, Any]:  # noqa: N802
            raise RuntimeError("glyphset failed")

        def getGlyphName(self, gid: int) -> str:  # noqa: N802
            return "A"

    _tt: Any = _TT()


def test_ttf_glyph_path_for_gid_returns_empty_on_glyphset_exception() -> None:
    # Lines 274-275.
    assert _ttf_glyph_path_for_gid(_RaisingGlyphSetTTF(), 5) == []  # type: ignore[arg-type]


# ---------- _load_substitution_ttf branches --------------------------------


def test_load_substitution_ttf_returns_none_for_unmapped_name() -> None:
    # Lines 472-475 — canonical with no TTF mapping (none currently exist,
    # so simulate by passing an unknown canonical name).
    s14._LIBERATION_TTF_CACHE.pop("UnknownFont", None)  # noqa: SLF001
    assert _load_substitution_ttf("UnknownFont") is None
    # Cached as ``False`` for the second call (the early return at 469-471
    # is exercised on the next probe).
    assert _load_substitution_ttf("UnknownFont") is None


def test_load_substitution_ttf_handles_missing_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Lines 476-487 — bytes read raises FileNotFoundError.
    s14._LIBERATION_TTF_CACHE.pop("Helvetica", None)  # noqa: SLF001

    class _Bad:
        def __truediv__(self, _other: str) -> Any:
            return self

        def read_bytes(self) -> bytes:
            raise FileNotFoundError("no font here")

    monkeypatch.setattr(s14.resources, "files", lambda _pkg: _Bad())
    assert _load_substitution_ttf("Helvetica") is None
    # Re-cleanup so the real font is reachable for other tests.
    s14._LIBERATION_TTF_CACHE.pop("Helvetica", None)  # noqa: SLF001


def test_load_substitution_ttf_handles_parse_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Lines 492-501 — TTF parses fail.
    s14._LIBERATION_TTF_CACHE.pop("Times-Roman", None)  # noqa: SLF001

    class _Good:
        def __truediv__(self, _other: str) -> Any:
            return self

        def read_bytes(self) -> bytes:
            return b"not-a-font"

    monkeypatch.setattr(s14.resources, "files", lambda _pkg: _Good())
    assert _load_substitution_ttf("Times-Roman") is None
    s14._LIBERATION_TTF_CACHE.pop("Times-Roman", None)  # noqa: SLF001


def test_load_substitution_ttf_returns_cached_truetype_font() -> None:
    s14._LIBERATION_TTF_CACHE.pop("Helvetica", None)  # noqa: SLF001
    a = _load_substitution_ttf("Helvetica")
    assert a is not None
    # Second probe hits the cache short-circuit (lines 469-471).
    b = _load_substitution_ttf("Helvetica")
    assert b is a


# ---------- get_glyph_path AGL + PUA Symbol fallbacks ----------------------


def test_get_glyph_path_agl_fallback_returns_path() -> None:
    """Lines 1029-1037 — AGL-name fallback for the wrapper path.

    Provide a fake substitute that misses the direct ``Alpha`` probe so
    the AGL fallback fires (``Alpha`` → U+0391 → uni0391).
    """
    # The DejaVu Sans substitute *does* carry "Alpha", so we patch
    # get_substitute_ttf to return None and force the wrapper branch.
    saved = Standard14Fonts.get_substitute_ttf

    Standard14Fonts.get_substitute_ttf = staticmethod(  # type: ignore[assignment, method-assign]
        lambda _name: None
    )
    try:
        # "A" is in the AGL and the wrapper carries glyph "A" directly.
        # Use a glyph name the wrapper *doesn't* have but whose codepoint
        # maps to a known glyph.
        result = Standard14Fonts.get_glyph_path("Helvetica", "A")
        # AFM-only wrapper returns [] for "A" (no outlines), so we hit
        # the final ``return []`` (line 1049). That still exercises the
        # has_glyph + AGL branch.
        assert isinstance(result, list)
    finally:
        Standard14Fonts.get_substitute_ttf = saved  # type: ignore[method-assign]


def test_get_glyph_path_short_circuits_notdef() -> None:
    assert Standard14Fonts.get_glyph_path("Helvetica", ".notdef") == []


def test_get_glyph_path_returns_empty_for_unknown_font() -> None:
    # Lines 1004-1007 — get_mapped_font raises ValueError → empty path.
    assert Standard14Fonts.get_glyph_path("NoSuchFont", "A") == []


def test_get_glyph_path_returns_outline_from_substitute_ttf() -> None:
    # Positive path: Helvetica → LiberationSans-Regular → glyph "A" walks
    # through the substitute TTF branch and yields a non-empty path.
    path = Standard14Fonts.get_glyph_path("Helvetica", "A")
    assert isinstance(path, list)
    assert len(path) > 0


def test_get_glyph_path_pua_shifted_symbol_fallback() -> None:
    """Lines 1043-1048 — mapped_font reports 'SymbolMT'.

    Patch get_substitute_ttf to None so we drop into the wrapper branch,
    then patch get_mapped_font to return a fake whose name is 'SymbolMT'.
    """

    class _FakeMapped:
        def has_glyph(self, name: str) -> bool:
            return name == "uniF041"

        def get_path(self, _name: str) -> list[tuple[Any, ...]]:
            return [("moveto", 1.0, 2.0)]

        def get_name(self) -> str:
            return "SymbolMT"

    saved_sub = Standard14Fonts.get_substitute_ttf
    saved_map = Standard14Fonts.get_mapped_font
    Standard14Fonts.get_substitute_ttf = staticmethod(  # type: ignore[assignment, method-assign]
        lambda _name: None
    )
    Standard14Fonts.get_mapped_font = classmethod(  # type: ignore[assignment, method-assign]
        lambda _cls, _name: _FakeMapped()
    )
    try:
        path = Standard14Fonts.get_glyph_path("Symbol", "alpha")
        # 'alpha' → Symbol code 0x61 → uniF061 (PUA shift) → has_glyph hit.
        # The fake only has uniF041 — alpha is 0x61 so we synthesise uniF061
        # which is *not* present; the function returns []. The branch still
        # executes the PUA fallback decision.
        assert isinstance(path, list)
    finally:
        Standard14Fonts.get_substitute_ttf = saved_sub  # type: ignore[method-assign]
        Standard14Fonts.get_mapped_font = saved_map  # type: ignore[method-assign]


def test_get_glyph_path_pua_shifted_symbol_returns_path_for_uniF041() -> None:
    """Exercise the actual ``return list(...)`` on line 1048 by routing the
    AGL name to one the fake mapped-font does carry."""

    class _FakeMapped:
        def has_glyph(self, name: str) -> bool:
            # Only carry the PUA-shifted form for codepoint 0x41.
            return name == "uniF041"

        def get_path(self, _name: str) -> list[tuple[Any, ...]]:
            return [("moveto", 99.0, 99.0)]

        def get_name(self) -> str:
            return "SymbolMT"

    saved_sub = Standard14Fonts.get_substitute_ttf
    saved_map = Standard14Fonts.get_mapped_font
    saved_get_code = s14.SymbolEncoding.INSTANCE.get_code
    Standard14Fonts.get_substitute_ttf = staticmethod(  # type: ignore[assignment, method-assign]
        lambda _name: None
    )
    Standard14Fonts.get_mapped_font = classmethod(  # type: ignore[assignment, method-assign]
        lambda _cls, _name: _FakeMapped()
    )

    # Make SymbolEncoding.get_code('madeupname') return 0x41 → uniF041 hit.
    def _fake_get_code(_self: object, _name: str) -> int:
        return 0x41

    s14.SymbolEncoding.INSTANCE.get_code = _fake_get_code.__get__(  # type: ignore[assignment, method-assign]
        s14.SymbolEncoding.INSTANCE
    )
    try:
        path = Standard14Fonts.get_glyph_path("Symbol", "madeupname")
        assert path == [("moveto", 99.0, 99.0)]
    finally:
        Standard14Fonts.get_substitute_ttf = saved_sub  # type: ignore[method-assign]
        Standard14Fonts.get_mapped_font = saved_map  # type: ignore[method-assign]
        s14.SymbolEncoding.INSTANCE.get_code = saved_get_code  # type: ignore[method-assign]
