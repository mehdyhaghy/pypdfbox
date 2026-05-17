"""Coverage-boost tests for ``Type1CharString`` (wave 1323).

Targets the residual missing branches in
``pypdfbox.fontbox.cff.type1_char_string``:

* ``_command_name`` fallback for an object exposing no ``.name`` string;
* ``_translate_path_cmd`` for moveto / curveto / closepath branches;
* every ``handle_type1_command`` operator dispatch arm (including the
  warn-and-recover ``rline_to`` /  ``rrcurve_to`` paths when the path has
  no current point yet);
* ``call_other_subr`` flex begin (``num==1``) and complete flex sequence
  (``num==0`` with seven points);
* ``set_current_point`` direct setter;
* ``seac()`` accent composite for both base + accent path append, plus
  the PDFBOX-5339 self-recursion guard;
* ``render()`` happy path through fontTools.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.cff.type1_char_string import (
    Type1CharString,
    _command_name,
    _has_current_point,
    _RenderContext,
    _translate_path_cmd,
)

# ---------------------------------------------------------------------------
# module-level helpers
# ---------------------------------------------------------------------------


def test_command_name_object_without_string_name_returns_empty() -> None:
    """An object with no ``name`` attribute (or a non-string one) must
    return the empty-string sentinel — never crash."""

    class _Token:  # no `name` attribute at all
        pass

    class _NumericName:
        name = 42  # not a str

    assert _command_name(_Token()) == ""
    assert _command_name(_NumericName()) == ""


def test_command_name_object_with_string_name() -> None:
    """An object exposing ``name: str`` returns it verbatim — mirrors
    fontTools' ``CharStringCommand.name`` shape."""

    class _NamedToken:
        name = "hsbw"

    assert _command_name(_NamedToken()) == "hsbw"


def test_command_name_plain_string_passthrough() -> None:
    assert _command_name("rmoveto") == "rmoveto"


def test_translate_path_cmd_moveto_lineto_curveto_closepath() -> None:
    """All four tag shapes round-trip through the translation helper —
    the closepath case is the implicit ``return cmd`` fallback."""
    assert _translate_path_cmd(("moveto", 1.0, 2.0), 10, 20) == ("moveto", 11.0, 22.0)
    assert _translate_path_cmd(("lineto", 3.0, 4.0), 5, 7) == ("lineto", 8.0, 11.0)
    assert _translate_path_cmd(
        ("curveto", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0), 10, 20
    ) == ("curveto", 11.0, 22.0, 13.0, 24.0, 15.0, 26.0)
    assert _translate_path_cmd(("closepath",), 10, 20) == ("closepath",)


def test_has_current_point_tracks_path() -> None:
    ctx = _RenderContext()
    assert _has_current_point(ctx) is False
    ctx.path.append(("moveto", 1.0, 2.0))
    assert _has_current_point(ctx) is True


# ---------------------------------------------------------------------------
# handle_type1_command — exercise every dispatch arm
# ---------------------------------------------------------------------------


def _bare_cs() -> Type1CharString:
    return Type1CharString(None, "F", "A", None)


def test_handle_rmoveto_appends_moveto_and_updates_current() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [10, 20], "rmoveto")
    assert ctx.path == [("moveto", 10.0, 20.0)]
    assert ctx.current == (10.0, 20.0)


def test_handle_rmoveto_flex_records_flex_point() -> None:
    """When ``is_flex`` is set, ``rmoveto`` queues a flex point instead
    of emitting a moveto."""
    cs = _bare_cs()
    ctx = _RenderContext()
    ctx.is_flex = True
    cs.handle_type1_command(ctx, [3, 4], "rmoveto")
    assert ctx.flex_points == [(3.0, 4.0)]
    assert ctx.path == []


def test_handle_vmoveto_and_flex() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [5], "vmoveto")
    assert ctx.path == [("moveto", 0.0, 5.0)]
    ctx2 = _RenderContext()
    ctx2.is_flex = True
    cs.handle_type1_command(ctx2, [5], "vmoveto")
    assert ctx2.flex_points == [(0.0, 5.0)]


def test_handle_hmoveto_and_flex() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [7], "hmoveto")
    assert ctx.path == [("moveto", 7.0, 0.0)]
    ctx2 = _RenderContext()
    ctx2.is_flex = True
    cs.handle_type1_command(ctx2, [7], "hmoveto")
    assert ctx2.flex_points == [(7.0, 0.0)]


def test_handle_rlineto_emits_moveto_when_no_current_point() -> None:
    """Warn-and-recover: without a current point the rline_to falls
    back to a moveto at the final coordinate."""
    cs = _bare_cs()
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [3, 4], "rlineto")
    assert ctx.path == [("moveto", 3.0, 4.0)]


def test_handle_rlineto_emits_lineto_when_current_point_set() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    ctx.path.append(("moveto", 0.0, 0.0))
    cs.handle_type1_command(ctx, [3, 4], "rlineto")
    assert ctx.path[-1] == ("lineto", 3.0, 4.0)


def test_handle_hlineto_vlineto_dispatch_through_rline_to() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    ctx.path.append(("moveto", 0.0, 0.0))
    cs.handle_type1_command(ctx, [5], "hlineto")
    assert ctx.path[-1] == ("lineto", 5.0, 0.0)
    cs.handle_type1_command(ctx, [3], "vlineto")
    assert ctx.path[-1] == ("lineto", 5.0, 3.0)


def test_handle_rrcurveto_emits_curveto_when_current_point_set() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    ctx.path.append(("moveto", 0.0, 0.0))
    cs.handle_type1_command(ctx, [1, 2, 3, 4, 5, 6], "rrcurveto")
    assert ctx.path[-1] == ("curveto", 1.0, 2.0, 4.0, 6.0, 9.0, 12.0)


def test_handle_rrcurveto_falls_back_to_moveto_without_current_point() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [1, 2, 3, 4, 5, 6], "rrcurveto")
    assert ctx.path == [("moveto", 9.0, 12.0)]


def test_handle_closepath_emits_closepath_and_following_moveto() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    ctx.path.append(("moveto", 5.0, 5.0))
    ctx.current = (5.0, 5.0)
    cs.handle_type1_command(ctx, [], "closepath")
    assert ctx.path == [
        ("moveto", 5.0, 5.0),
        ("closepath",),
        ("moveto", 5.0, 5.0),
    ]


def test_handle_closepath_without_current_point_still_emits_moveto() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [], "closepath")
    assert ctx.path == [("moveto", 0.0, 0.0)]


def test_handle_sbw_sets_lsb_width_and_current() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [10, 20, 600, 0], "sbw")
    assert ctx.left_side_bearing == (10.0, 20.0)
    assert ctx.width == 600
    assert ctx.current == (10.0, 20.0)


def test_handle_hsbw_sets_lsb_width_and_current() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [50, 500], "hsbw")
    assert ctx.left_side_bearing == (50.0, 0.0)
    assert ctx.width == 500
    assert ctx.current == (50.0, 0.0)


def test_handle_vhcurveto_dispatches_through_rrcurve_to() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    ctx.path.append(("moveto", 0.0, 0.0))
    cs.handle_type1_command(ctx, [1, 2, 3, 4], "vhcurveto")
    assert ctx.path[-1][0] == "curveto"


def test_handle_hvcurveto_dispatches_through_rrcurve_to() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    ctx.path.append(("moveto", 0.0, 0.0))
    cs.handle_type1_command(ctx, [1, 2, 3, 4], "hvcurveto")
    assert ctx.path[-1][0] == "curveto"


def test_handle_setcurrentpoint_updates_current_without_moveto() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [100, 200], "setcurrentpoint")
    assert ctx.current == (100.0, 200.0)
    assert ctx.path == []


def test_handle_callothersubr_dispatches_flex_begin_and_end() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    # begin flex
    cs.handle_type1_command(ctx, [1], "callothersubr")
    assert ctx.is_flex is True
    # end flex with fewer than 7 points clears state
    ctx.flex_points = [(1.0, 1.0)]
    cs.handle_type1_command(ctx, [0], "callothersubr")
    assert ctx.is_flex is False
    assert ctx.flex_points == []


def test_handle_div_performs_arithmetic_and_skips_clear() -> None:
    """``div`` consumes the top two operands and pushes ``a/b`` —
    importantly, it returns *before* the trailing ``n.clear()`` so the
    quotient survives for the next operator."""
    cs = _bare_cs()
    ctx = _RenderContext()
    nums: list[Any] = [10, 4]
    cs.handle_type1_command(ctx, nums, "div")
    assert nums == [2.5]


def test_handle_hint_operators_are_silent_no_ops() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    for op in ("hstem", "vstem", "hstem3", "vstem3", "dotsection"):
        nums: list[Any] = [0, 10]
        cs.handle_type1_command(ctx, nums, op)
        assert nums == []  # clear() always runs for these
        assert ctx.path == []


def test_handle_endchar_return_callsubr_silent() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    for op in ("endchar", "return", "callsubr"):
        nums: list[Any] = []
        cs.handle_type1_command(ctx, nums, op)
        assert nums == []
        assert ctx.path == []


def test_handle_unknown_operator_falls_through_and_clears_operands() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    nums: list[Any] = [1, 2, 3]
    cs.handle_type1_command(ctx, nums, "totally-unknown-op")
    assert nums == []  # always-clear trailing semantics


# ---------------------------------------------------------------------------
# call_other_subr — full flex sequence
# ---------------------------------------------------------------------------


def test_call_other_subr_complete_flex_emits_two_curveto_segments() -> None:
    """A seven-point flex sequence ends with two ``rrcurveto`` segments —
    exercises the ``num == 0`` path with ``len(flex_points) >= 7``."""
    cs = _bare_cs()
    ctx = _RenderContext()
    ctx.path.append(("moveto", 0.0, 0.0))
    ctx.current = (0.0, 0.0)
    ctx.is_flex = True
    ctx.flex_points = [
        (0.0, 0.0),   # ref
        (5.0, 0.0),   # first control
        (3.0, 4.0),   # second control
        (6.0, 8.0),   # end of first curve
        (2.0, 0.0),   # second curve c1
        (3.0, 2.0),   # second curve c2
        (4.0, 4.0),   # second curve endpoint
    ]
    cs.call_other_subr(ctx, 0)
    assert ctx.is_flex is False
    assert ctx.flex_points == []
    # Two new curveto commands appended after the moveto.
    curveto_cmds = [cmd for cmd in ctx.path if cmd[0] == "curveto"]
    assert len(curveto_cmds) == 2


def test_call_other_subr_unknown_number_is_silent_no_op() -> None:
    cs = _bare_cs()
    ctx = _RenderContext()
    cs.call_other_subr(ctx, 99)  # unrecognised — upstream just warns
    assert ctx.is_flex is False


# ---------------------------------------------------------------------------
# seac — Standard-Encoding Accented Character composite
# ---------------------------------------------------------------------------


class _FakeReader:
    """Minimal ``Type1CharStringReader`` shim — returns canned charstrings
    keyed by glyph name. Exercises ``seac()``'s lookup, base append, and
    translated-accent append branches."""

    def __init__(self, glyph_paths: dict[str, list[tuple[Any, ...]]]) -> None:
        self._glyphs = glyph_paths

    def get_type1_char_string(self, name: str) -> Type1CharString:
        cs = Type1CharString(self, "F", name, None)
        cs._cached_path = list(self._glyphs.get(name, []))
        cs._cached_width = 0.0
        return cs


def test_seac_appends_base_and_translated_accent_paths() -> None:
    """Standard Encoding indices 65 → ``A``, 194 → ``acute``. The accent
    path is translated by ``(lsb.x + adx - asb, lsb.y + ady)``."""
    reader = _FakeReader({
        "A": [("moveto", 0.0, 0.0), ("lineto", 100.0, 0.0)],
        "acute": [("moveto", 0.0, 600.0), ("lineto", 30.0, 700.0)],
    })
    cs = Type1CharString(reader, "F", "Aacute", None)
    ctx = _RenderContext()
    ctx.left_side_bearing = (10.0, 20.0)
    cs.seac(ctx, 5, 50, 100, 65, 194)
    # Base appended verbatim.
    assert ctx.path[0] == ("moveto", 0.0, 0.0)
    assert ctx.path[1] == ("lineto", 100.0, 0.0)
    # Accent translated by (10 + 50 - 5, 20 + 100) = (55, 120).
    assert ctx.path[2] == ("moveto", 55.0, 720.0)
    assert ctx.path[3] == ("lineto", 85.0, 820.0)


def test_seac_self_recursion_short_circuits_at_accent() -> None:
    """PDFBOX-5339: if the accent lookup returns ``self``, ``seac()`` must
    bail before the translation loop to avoid infinite recursion."""

    class _SelfReader:
        def __init__(self, recursive: Type1CharString) -> None:
            self._self = recursive

        def get_type1_char_string(self, name: str) -> Type1CharString:
            # Base lookup returns an empty charstring with a tiny path;
            # accent lookup returns the same instance triggering the
            # self-recursion guard.
            return self._self

    reader_holder: dict[str, Type1CharString] = {}
    cs = Type1CharString(None, "F", "Self", None)
    reader_holder["cs"] = cs
    cs._font = _SelfReader(cs)
    ctx = _RenderContext()
    # Base append no-ops because get_path() on ``cs`` returns []; accent
    # append hits the self-recursion guard and returns.
    cs.seac(ctx, 0, 0, 0, 65, 194)
    # No exception, no path mutation beyond what get_path() already
    # cached for the (empty) base charstring.
    assert ctx.path == []


def test_seac_missing_font_lookup_is_silent() -> None:
    """When the parent font exposes no ``get_type1_char_string``, ``seac()``
    must bail without raising — matches upstream's warn-and-skip path."""

    class _NoLookupReader:
        pass

    cs = Type1CharString(_NoLookupReader(), "F", "X", None)
    ctx = _RenderContext()
    cs.seac(ctx, 0, 0, 0, 65, 194)
    assert ctx.path == []


def test_seac_non_numeric_indices_silently_ignored() -> None:
    reader = _FakeReader({})
    cs = Type1CharString(reader, "F", "X", None)
    ctx = _RenderContext()
    # bchar / achar that don't coerce to int → resolved name is None →
    # no append to ctx.path.
    cs.seac(ctx, 0, 0, 0, "not-a-number", "also-bad")
    assert ctx.path == []


def test_handle_seac_dispatch_calls_seac() -> None:
    """``handle_type1_command`` with ``seac`` keyword reaches
    ``seac(ctx, asb, adx, ady, bchar, achar)``."""
    reader = _FakeReader({
        "A": [("moveto", 0.0, 0.0)],
        "acute": [("moveto", 0.0, 600.0)],
    })
    cs = Type1CharString(reader, "F", "Aacute", None)
    ctx = _RenderContext()
    ctx.left_side_bearing = (0.0, 0.0)
    cs.handle_type1_command(ctx, [0, 0, 0, 65, 194], "seac")
    assert ctx.path  # at least base appended


# ---------------------------------------------------------------------------
# render() — happy path through fontTools T1OutlineExtractor
# ---------------------------------------------------------------------------


def test_render_returns_cached_path_on_repeat_call() -> None:
    """A second ``render()`` returns the cached list without re-running
    the extractor."""
    cs = Type1CharString(
        None, "F", "A", [0, 500, "hsbw", "closepath", "endchar"]
    )
    first = cs.render()
    second = cs.render()
    assert first == second


def test_render_emits_path_for_simple_program() -> None:
    """A minimal Type 1 program with a single ``moveto`` produces a
    non-empty path through fontTools."""
    cs = Type1CharString(
        None,
        "F",
        "A",
        [0, 500, "hsbw", 100, 200, "rmoveto", "closepath", "endchar"],
    )
    path = cs.render()
    assert any(cmd[0] == "moveto" for cmd in path)


# ---------------------------------------------------------------------------
# get_width / get_path / get_bounds / render — exception + cached-branch
# ---------------------------------------------------------------------------


class _ExplodingCharString:
    """Stand-in for ``T1CharString`` whose ``program`` access raises —
    used to force the ``except Exception`` arms in get_width / get_path /
    render to fire."""

    width = 0.0
    subrs = None
    program: list[Any] = []

    def __init__(self) -> None:
        # No bytecode and an empty program means fontTools' extractor
        # has nothing to do; pair with a pen whose draw raises by
        # monkey-patching ``_draw_with_extended_extractor``.
        pass


def test_get_width_returns_zero_when_extractor_raises(monkeypatch) -> None:  # noqa: ANN001
    """The ``except Exception`` arm at line 297 maps an extractor crash
    to a width of 0.0 — never propagates."""
    cs = Type1CharString(None, "F", "A", None)
    import pypdfbox.fontbox.cff.type1_char_string as mod

    def _boom(_t1: Any, _pen: Any) -> float:
        raise RuntimeError("extractor blew up")

    monkeypatch.setattr(mod, "_draw_with_extended_extractor", _boom)
    assert cs.get_width() == 0.0


def test_get_width_uses_cached_path_branch(monkeypatch) -> None:  # noqa: ANN001
    """When the path is already cached but width is not, ``get_width``
    reads ``self._t1.width`` directly without re-running the extractor —
    covers line 288-289."""
    cs = Type1CharString(None, "F", "A", None)
    cs._cached_path = [("moveto", 0.0, 0.0)]
    cs._cached_width = None
    cs._t1.width = 777.0  # type: ignore[attr-defined]
    assert cs.get_width() == 777.0


def test_get_path_returns_empty_when_extractor_raises(monkeypatch) -> None:  # noqa: ANN001
    cs = Type1CharString(None, "F", "A", None)
    import pypdfbox.fontbox.cff.type1_char_string as mod

    def _boom(_t1: Any, _pen: Any) -> float:
        raise RuntimeError("extractor blew up")

    monkeypatch.setattr(mod, "_draw_with_extended_extractor", _boom)
    assert cs.get_path() == []


def test_get_bounds_includes_curveto_control_points() -> None:
    """``get_bounds`` walks every coord in a ``curveto`` (lines 343-345)
    so the bbox spans both control points and endpoints."""
    cs = Type1CharString(None, "F", "A", None)
    # Inject a path with a curve whose control-point Y exceeds endpoint Y.
    cs._cached_path = [
        ("moveto", 0.0, 0.0),
        ("curveto", 10.0, 200.0, 20.0, 300.0, 30.0, 50.0),
    ]
    bounds = cs.get_bounds()
    assert bounds is not None
    xmin, ymin, xmax, ymax = bounds
    assert ymax == 300.0  # picked from the curveto control point


def test_render_returns_empty_when_extractor_raises(monkeypatch) -> None:  # noqa: ANN001
    """``render()``'s ``except Exception`` arm caches ``[]`` so a
    follow-up call short-circuits — covers lines 425-428."""
    cs = Type1CharString(None, "F", "A", None)
    import pypdfbox.fontbox.cff.type1_char_string as mod

    def _boom(_t1: Any, _pen: Any) -> float:
        raise RuntimeError("nope")

    monkeypatch.setattr(mod, "_draw_with_extended_extractor", _boom)
    first = cs.render()
    assert first == []
    # Cached on the empty branch — second call returns the cached list
    # without re-raising even though the patch is still active.
    monkeypatch.setattr(
        mod, "_draw_with_extended_extractor",
        lambda _t1, _pen: (_ for _ in ()).throw(RuntimeError("still bad")),
    )
    assert cs.render() == []


# ---------------------------------------------------------------------------
# seac — exception arms
# ---------------------------------------------------------------------------


def test_seac_with_get_name_raising_falls_back_to_none(monkeypatch) -> None:  # noqa: ANN001
    """When ``StandardEncoding.get_name`` itself raises (simulated via
    monkey-patch), the inner ``_name`` helper swallows the exception and
    returns ``None`` — exercises the ``except Exception`` arm at lines
    651-653."""
    from pypdfbox.fontbox.encoding.standard_encoding import StandardEncoding

    def _boom(self: Any, code: Any) -> str:
        raise RuntimeError("simulated get_name failure")

    monkeypatch.setattr(
        StandardEncoding, "get_name", _boom, raising=True
    )

    class _Reader:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def get_type1_char_string(self, name: str) -> Type1CharString:
            self.calls.append(name)
            cs = Type1CharString(None, "F", name, None)
            cs._cached_path = []
            cs._cached_width = 0.0
            return cs

    reader = _Reader()
    cs = Type1CharString(reader, "F", "X", None)
    ctx = _RenderContext()
    cs.seac(ctx, 0, 0, 0, 65, 194)
    # Both lookups returned None, no reader calls.
    assert reader.calls == []


def test_seac_base_lookup_exception_is_swallowed() -> None:
    """If the reader's lookup raises mid-base-append, ``seac()`` swallows
    the exception and proceeds to the accent step."""

    class _Reader:
        def get_type1_char_string(self, name: str) -> Type1CharString:
            if name == "A":
                raise RuntimeError("base lookup blew up")
            cs = Type1CharString(self, "F", name, None)
            cs._cached_path = [("moveto", 0.0, 600.0)]
            cs._cached_width = 0.0
            return cs

    cs = Type1CharString(_Reader(), "F", "Aacute", None)
    ctx = _RenderContext()
    ctx.left_side_bearing = (0.0, 0.0)
    cs.seac(ctx, 0, 0, 0, 65, 194)
    # Base never appended, accent translated by (0, 0) and appended.
    assert ctx.path == [("moveto", 0.0, 600.0)]


def test_seac_accent_lookup_exception_is_swallowed() -> None:
    """If the reader raises mid-accent-append, ``seac()`` swallows the
    exception — base portion remains, accent omitted."""

    class _Reader:
        def get_type1_char_string(self, name: str) -> Type1CharString:
            if name == "acute":
                raise RuntimeError("accent lookup blew up")
            cs = Type1CharString(self, "F", name, None)
            cs._cached_path = [("moveto", 1.0, 2.0)]
            cs._cached_width = 0.0
            return cs

    cs = Type1CharString(_Reader(), "F", "Aacute", None)
    ctx = _RenderContext()
    cs.seac(ctx, 0, 0, 0, 65, 194)
    assert ctx.path == [("moveto", 1.0, 2.0)]


def test_seac_standard_encoding_import_failure_path(monkeypatch) -> None:  # noqa: ANN001
    """If ``StandardEncoding`` fails to import, ``std`` is ``None`` and
    every ``_name(idx)`` returns ``None`` — exercises line 640-641 and
    the ``std is None`` branch of ``_name``."""
    import sys

    saved = sys.modules.pop(
        "pypdfbox.fontbox.encoding.standard_encoding", None
    )
    # Force the import to raise by injecting a fake module that explodes
    # on attribute access.
    import types

    fake = types.ModuleType("pypdfbox.fontbox.encoding.standard_encoding")

    class _BoomStandard:
        @classmethod
        def __getattr__(cls, name: str) -> Any:
            raise RuntimeError("simulated import failure")

    fake.StandardEncoding = _BoomStandard()  # type: ignore[attr-defined]
    sys.modules["pypdfbox.fontbox.encoding.standard_encoding"] = fake
    try:

        class _Reader:
            def get_type1_char_string(self, name: str) -> Type1CharString:
                cs = Type1CharString(None, "F", name, None)
                cs._cached_path = [("moveto", 0.0, 0.0)]
                cs._cached_width = 0.0
                return cs

        cs = Type1CharString(_Reader(), "F", "X", None)
        ctx = _RenderContext()
        cs.seac(ctx, 0, 0, 0, 65, 194)
        # Both indices resolve to None when StandardEncoding is unavailable.
        assert ctx.path == []
    finally:
        if saved is not None:
            sys.modules["pypdfbox.fontbox.encoding.standard_encoding"] = saved
        else:
            sys.modules.pop(
                "pypdfbox.fontbox.encoding.standard_encoding", None
            )


# ---------------------------------------------------------------------------
# helpers — _stringify_token / _coerce_program_token fallback paths
# ---------------------------------------------------------------------------


def test_stringify_token_falls_back_to_str_for_unknown_shape() -> None:
    """A token that is neither number nor has a string ``.name`` falls
    through to ``str(tok)`` — covers line 731."""
    from pypdfbox.fontbox.cff.type1_char_string import _stringify_token

    class _Token:
        def __str__(self) -> str:
            return "<custom>"

    assert _stringify_token(_Token()) == "<custom>"


def test_stringify_token_prefers_named_command() -> None:
    """A token exposing a string ``.name`` returns it verbatim (line 730)."""
    from pypdfbox.fontbox.cff.type1_char_string import _stringify_token

    class _NamedCmd:
        name = "hsbw"

    assert _stringify_token(_NamedCmd()) == "hsbw"


def test_coerce_program_token_last_resort_str() -> None:
    """A token that is neither number, str, nor ``.name``-bearing falls
    through to ``str(tok)`` — covers line 749."""
    from pypdfbox.fontbox.cff.type1_char_string import _coerce_program_token

    class _Token:
        def __str__(self) -> str:
            return "<custom-op>"

    assert _coerce_program_token(_Token()) == "<custom-op>"


def test_coerce_program_token_passes_through_named_command() -> None:
    from pypdfbox.fontbox.cff.type1_char_string import _coerce_program_token

    class _Cmd:
        name = "hsbw"

    assert _coerce_program_token(_Cmd()) == "hsbw"
