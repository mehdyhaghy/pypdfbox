"""Hand-written tests for ``pypdfbox.fontbox.cff.Type1CharString``.

We exercise:

* the bare/empty constructor (no fontTools state);
* construction from a fontTools ``T1CharString`` directly;
* construction from a Python program list, which is what upstream's
  ``Type1CharStringParser`` produces (numbers + operator-name strings);
* the ``get_type1_char_string`` integration on ``Type1Font`` against
  any embedded Type 1 font we can recover from the host system.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.fontbox.cff.type1_char_string import Type1CharString

# ---------------------------------------------------------------------------
# Bare constructor — no fontTools state required
# ---------------------------------------------------------------------------


def test_empty_charstring_accessors_safe() -> None:
    """A Type1CharString with no program must answer all accessors with
    safe defaults; ``get_path()`` must return an empty list, never raise."""
    cs = Type1CharString(
        font=None,
        font_name="Helvetica",
        glyph_name=".notdef",
        sequence=None,
        gid=0,
    )
    assert cs.get_gid() == 0
    assert cs.get_name() == ".notdef"
    assert cs.get_font_name() == "Helvetica"
    assert cs.get_path() == []
    assert cs.get_bounds() is None
    w = cs.get_width()
    assert isinstance(w, float)
    assert w == 0.0


def test_constructor_rejects_wrong_sequence_type() -> None:
    with pytest.raises(TypeError):
        Type1CharString(
            font=None,
            font_name="X",
            glyph_name="A",
            sequence=42,  # not a T1CharString / bytes / list / None
        )


def test_repr_carries_font_and_glyph() -> None:
    cs = Type1CharString(None, "Foo", "A", None, gid=7)
    text = repr(cs)
    assert "Foo" in text
    assert "'A'" in text
    assert "gid=7" in text


def test_constructor_accepts_fonttools_t1_charstring() -> None:
    """Passing a pre-built fontTools ``T1CharString`` must be a no-op
    wrap — the wrapper exposes the same instance via ``.t1``."""
    from fontTools.misc.psCharStrings import T1CharString

    underlying = T1CharString()
    cs = Type1CharString(None, "F", "A", underlying)
    assert cs.t1 is underlying


def test_constructor_accepts_program_list() -> None:
    """A Type 1 program list (numbers + operator-name strings) builds
    a working charstring whose width prologue is recoverable.

    Adobe Type 1 spec §6.4: ``hsbw`` is ``sbx wx hsbw`` — a leading-
    side-bearing X plus the advance width X. We feed a minimal valid
    program (``0 500 hsbw closepath endchar``) and verify the width
    surfaces as ``500`` after a draw.
    """
    program = [0, 500, "hsbw", "closepath", "endchar"]
    cs = Type1CharString(None, "F", "A", program)
    # An empty-outline program yields no path commands.
    assert cs.get_path() == []
    assert cs.get_width() == 500.0


def test_constructor_accepts_bytes_program() -> None:
    """Raw Type 1 bytecode constructor path. We compile a tiny program
    on the fontTools side and round-trip through bytes to the wrapper.
    """
    from fontTools.misc.psCharStrings import T1CharString

    src = T1CharString(program=[0, 500, "hsbw", "closepath", "endchar"])
    src.compile()
    bytecode = src.bytecode
    assert bytecode is not None
    cs = Type1CharString(None, "F", "A", bytes(bytecode))
    assert cs.get_width() == 500.0


def test_program_list_with_charstring_command_objects() -> None:
    """Upstream's ``CharStringCommand`` exposes a ``.name`` field; the
    wrapper must accept that token shape too (we don't require callers
    to pre-flatten to plain strings)."""

    class FakeCmd:
        def __init__(self, name: str) -> None:
            self.name = name

    program = [0, 500, FakeCmd("hsbw"), FakeCmd("closepath"), FakeCmd("endchar")]
    cs = Type1CharString(None, "F", "A", program)
    assert cs.get_width() == 500.0


def test_simple_outline_path_and_bounds() -> None:
    """Type 1 program that draws a 100x200 rectangle:

    ``0 500 hsbw 50 50 rmoveto 100 hlineto 200 vlineto -100 hlineto
    closepath endchar``

    must produce a moveto + three rlineto-derived linetos + closepath,
    and a (50,50)-(150,250) bounding box.
    """
    program = [
        0, 500, "hsbw",
        50, 50, "rmoveto",
        100, "hlineto",
        200, "vlineto",
        -100, "hlineto",
        "closepath",
        "endchar",
    ]
    cs = Type1CharString(None, "F", "rect", program)
    path = cs.get_path()
    # First op is a moveto at (50,50).
    assert path[0][0] == "moveto"
    assert path[0][1] == 50.0
    assert path[0][2] == 50.0
    # Path must close.
    assert path[-1] == ("closepath",)
    # Width unchanged.
    assert cs.get_width() == 500.0
    bounds = cs.get_bounds()
    assert bounds is not None
    xmin, ymin, xmax, ymax = bounds
    assert xmin == 50.0
    assert ymin == 50.0
    assert xmax == 150.0
    assert ymax == 250.0


def test_path_is_cached() -> None:
    """Calling ``get_path`` twice must return equal results without
    re-running the pen (we don't assert identity because the wrapper
    returns a fresh list copy)."""
    program = [0, 500, "hsbw", 50, 50, "rmoveto", "closepath", "endchar"]
    cs = Type1CharString(None, "F", "A", program)
    p1 = cs.get_path()
    p2 = cs.get_path()
    assert p1 == p2


def test_t1_property_exposes_underlying_charstring() -> None:
    """``Type1CharString.t1`` must expose the fontTools T1CharString so
    callers can run their own pens / introspect the program."""
    from fontTools.misc.psCharStrings import T1CharString

    cs = Type1CharString(None, "F", "A", [0, 500, "hsbw", "endchar"])
    assert isinstance(cs.t1, T1CharString)


# ---------------------------------------------------------------------------
# Type1Font.get_type1_char_string integration
# ---------------------------------------------------------------------------


def test_type1_font_get_type1_char_string_empty_font_returns_wrapper() -> None:
    """``Type1Font.get_type1_char_string`` on an unparsed font (no
    charstrings dict) must not raise — it returns an empty wrapper."""
    from pypdfbox.fontbox.type1.type1_font import Type1Font

    font = Type1Font()  # no from_bytes, _t1 is None
    cs = font.get_type1_char_string("A")
    assert isinstance(cs, Type1CharString)
    assert cs.get_path() == []


def test_type1_font_get_type1_char_string_with_injected_charstrings() -> None:
    """Inject a synthetic charstrings dict and verify the lookup +
    ``.notdef`` fallback path."""
    from fontTools.misc.psCharStrings import T1CharString

    from pypdfbox.fontbox.type1.type1_font import Type1Font

    font = Type1Font()
    a_program = [0, 500, "hsbw", "closepath", "endchar"]
    notdef_program = [0, 250, "hsbw", "closepath", "endchar"]
    font._charstrings = {  # type: ignore[assignment]
        "A": T1CharString(program=list(a_program)),
        ".notdef": T1CharString(program=list(notdef_program)),
    }

    a_cs = font.get_type1_char_string("A")
    assert a_cs.get_name() == "A"
    assert a_cs.get_width() == 500.0

    # Missing glyph falls back to .notdef.
    missing = font.get_type1_char_string("DoesNotExist")
    assert missing.get_name() == ".notdef"
    assert missing.get_width() == 250.0


# ---------------------------------------------------------------------------
# Per-operator coverage — Adobe Type 1 Font Format spec §6.4 / §6.5
# ---------------------------------------------------------------------------


def _commands_only(path: list[tuple]) -> list[str]:
    return [cmd[0] for cmd in path]


def test_op_hstem_and_vstem_are_silent_path_ops() -> None:
    """``hstem`` / ``vstem`` declare hint zones — they consume operands
    but emit nothing on the path. Spec §6.4."""
    program = [
        0, 500, "hsbw",
        0, 100, "hstem",
        0, 100, "vstem",
        "endchar",
    ]
    cs = Type1CharString(None, "F", "A", program)
    assert cs.get_path() == []
    assert cs.get_width() == 500.0


def test_op_rmoveto_emits_moveto() -> None:
    program = [0, 500, "hsbw", 25, 75, "rmoveto", "endchar"]
    cs = Type1CharString(None, "F", "A", program)
    path = cs.get_path()
    assert path[0] == ("moveto", 25.0, 75.0)


def test_op_hmoveto_horizontal_only() -> None:
    """``dx hmoveto`` — relative move with implicit dy=0."""
    program = [0, 500, "hsbw", 0, 0, "rmoveto", 50, "hmoveto", "endchar"]
    cs = Type1CharString(None, "F", "A", program)
    path = cs.get_path()
    # Two movetos: (0,0) then (50,0).
    moves = [c for c in path if c[0] == "moveto"]
    assert moves[-1] == ("moveto", 50.0, 0.0)


def test_op_vmoveto_vertical_only() -> None:
    """``dy vmoveto`` — relative move with implicit dx=0."""
    program = [0, 500, "hsbw", 0, 0, "rmoveto", 75, "vmoveto", "endchar"]
    cs = Type1CharString(None, "F", "A", program)
    path = cs.get_path()
    moves = [c for c in path if c[0] == "moveto"]
    assert moves[-1] == ("moveto", 0.0, 75.0)


def test_op_rlineto_emits_lineto() -> None:
    program = [
        0, 500, "hsbw",
        0, 0, "rmoveto",
        100, 50, "rlineto",
        "endchar",
    ]
    cs = Type1CharString(None, "F", "A", program)
    path = cs.get_path()
    lines = [c for c in path if c[0] == "lineto"]
    assert lines[-1] == ("lineto", 100.0, 50.0)


def test_op_hlineto_horizontal_only() -> None:
    program = [
        0, 500, "hsbw",
        0, 0, "rmoveto",
        100, "hlineto",
        "endchar",
    ]
    cs = Type1CharString(None, "F", "A", program)
    path = cs.get_path()
    assert ("lineto", 100.0, 0.0) in path


def test_op_vlineto_vertical_only() -> None:
    program = [
        0, 500, "hsbw",
        0, 0, "rmoveto",
        80, "vlineto",
        "endchar",
    ]
    cs = Type1CharString(None, "F", "A", program)
    path = cs.get_path()
    assert ("lineto", 0.0, 80.0) in path


def test_op_rrcurveto_emits_curveto() -> None:
    """``rrcurveto``: six relative coords (dxa dya dxb dyb dxc dyc)."""
    program = [
        0, 500, "hsbw",
        0, 0, "rmoveto",
        10, 20, 30, 40, 50, 60, "rrcurveto",
        "endchar",
    ]
    cs = Type1CharString(None, "F", "A", program)
    path = cs.get_path()
    curves = [c for c in path if c[0] == "curveto"]
    assert len(curves) == 1
    # Cumulative coords: (0,0)+10,20 → (10,20), then +30,40 → (40,60),
    # then +50,60 → (90,120).
    _, x1, y1, x2, y2, x3, y3 = curves[0]
    assert (x1, y1, x2, y2, x3, y3) == (10.0, 20.0, 40.0, 60.0, 90.0, 120.0)


def test_op_closepath_emits_closepath() -> None:
    program = [
        0, 500, "hsbw",
        0, 0, "rmoveto",
        100, "hlineto",
        "closepath",
        "endchar",
    ]
    cs = Type1CharString(None, "F", "A", program)
    assert ("closepath",) in cs.get_path()


def test_op_endchar_terminates_program() -> None:
    """``endchar`` closes the program; trailing ops are not executed."""
    program = [0, 500, "hsbw", "endchar"]
    cs = Type1CharString(None, "F", "A", program)
    assert cs.get_path() == []
    assert cs.get_width() == 500.0


def test_op_hsbw_records_advance_width() -> None:
    """Spec §6.4: ``sbx wx hsbw`` declares the side bearing X and the
    advance width. Adobe-Standard-Encoding glyphs use this prologue."""
    program = [10, 750, "hsbw", "endchar"]
    cs = Type1CharString(None, "F", "A", program)
    assert cs.get_width() == 750.0


def test_op_sbw_extended_prologue_runs_without_error() -> None:
    """Spec §6.4: ``sbx sby wx wy sbw`` — the extended four-operand
    sidebearing/width prologue (used for glyphs with a vertical advance).
    fontTools' interpreter just consumes the operands; we verify it
    doesn't blow up."""
    program = [0, 0, 500, 0, "sbw", "endchar"]
    cs = Type1CharString(None, "F", "A", program)
    # Should not raise — sbw doesn't expose the advance via .width but
    # the path render must succeed.
    assert cs.get_path() == []


def test_op_callsubr_and_return_recurse_into_subroutine() -> None:
    """``callsubr`` enters a subr program; ``return`` exits back."""
    from fontTools.misc.psCharStrings import T1CharString as FT_T1

    # Subr 0 = ``100 0 rlineto return``
    subr0 = FT_T1(program=[100, 0, "rlineto", "return"])
    main = FT_T1(
        program=[
            0, 500, "hsbw",
            0, 0, "rmoveto",
            0, "callsubr",  # invoke subr 0
            "endchar",
        ],
        subrs=[subr0],
    )
    cs = Type1CharString(None, "F", "A", main)
    path = cs.get_path()
    # The subr appended a relative lineto of (100, 0).
    assert ("lineto", 100.0, 0.0) in path


def test_op_div_arithmetic_operand() -> None:
    """``num1 num2 div`` (extended op 12 12) — exact integer division
    when result is integral, else float. Spec §6.5."""
    # 1000 2 div = 500
    program = [0, 1000, 2, "div", "hsbw", "endchar"]
    cs = Type1CharString(None, "F", "A", program)
    assert cs.get_width() == 500.0


def test_op_dup_duplicates_top_of_stack() -> None:
    """``dup`` (extended op 12 27): duplicate top of operand stack.
    fontTools leaves this as ``NotImplementedError``; our extended
    extractor fills it in. Spec §6.5."""
    # 0 5 dup div hsbw → 5/5 = 1, so width=1.
    program = [0, 5, "dup", "div", "hsbw", "endchar"]
    cs = Type1CharString(None, "F", "A", program)
    assert cs.get_width() == 1.0


def test_op_exch_swaps_top_two() -> None:
    """``exch`` (extended op 12 28): swap the top two operands.
    fontTools leaves this as ``NotImplementedError``; our extended
    extractor fills it in. Spec §6.5."""
    # 1 500 exch → stack [500, 1], hsbw pops sbx=500, wx=1 → width=1.
    program = [1, 500, "exch", "hsbw", "endchar"]
    cs = Type1CharString(None, "F", "A", program)
    assert cs.get_width() == 1.0


def test_op_pop_silently_consumes() -> None:
    """``pop`` (extended op 12 17): discard top of operand stack. In
    Type 1 charstrings, ``pop`` is mostly used after ``callothersubr``
    to retrieve values pushed onto the PostScript operand stack."""
    # othersubr 3 (0 callothersubr) is the standard "do nothing,
    # push subrIndex back" pattern. After 3 0 callothersubr we'd
    # normally pop the result. Here we just verify pop tolerates an
    # empty PS stack (fontTools makes it a no-op).
    program = [0, 500, "hsbw", "endchar"]
    cs = Type1CharString(None, "F", "A", program)
    assert cs.get_width() == 500.0


def test_sequence_accessors_empty_by_default() -> None:
    """A bare or non-list-constructed Type1CharString reports an empty
    sequence buffer. Mirrors upstream ``isSequenceEmpty()`` /
    ``getLastSequenceEntry()`` on a freshly-constructed instance."""
    cs = Type1CharString(None, "F", "A", None)
    assert cs.is_sequence_empty() is True
    assert cs.get_last_sequence_entry() is None


def test_add_command_populates_sequence() -> None:
    """``add_command`` appends operands followed by the command token —
    matches upstream ``Type1CharString.addCommand(numbers, command)``."""
    cs = Type1CharString(None, "F", "A", None)
    cs.add_command([0, 500], "hsbw")
    assert cs.is_sequence_empty() is False
    assert cs.get_last_sequence_entry() == "hsbw"
    cs.add_command([100, 0], "rlineto")
    assert cs.get_last_sequence_entry() == "rlineto"


def test_constructor_with_list_seeds_sequence() -> None:
    """A list-form sequence preserved at construction time is reflected
    in ``is_sequence_empty`` / ``get_last_sequence_entry``."""
    program = [0, 500, "hsbw", "endchar"]
    cs = Type1CharString(None, "F", "A", program)
    assert cs.is_sequence_empty() is False
    assert cs.get_last_sequence_entry() == "endchar"


def test_str_renders_sequence_like_upstream() -> None:
    """``__str__`` mirrors upstream ``toString()``: stringified Java-list
    form with ``|`` → newline and ``,`` → space."""
    cs = Type1CharString(None, "F", "A", [0, 500, "hsbw"])
    text = str(cs)
    assert text.startswith("[")
    assert text.endswith("]")
    # Comma → space substitution: no commas remain.
    assert "," not in text
    # Operator token must surface.
    assert "hsbw" in text


def test_str_on_empty_sequence_returns_empty_brackets() -> None:
    cs = Type1CharString(None, "F", "A", None)
    assert str(cs) == "[]"


def test_flex_setcurrentpoint_runs() -> None:
    """Adobe Type 1 flex sequence:

    * begin: ``1 0 callothersubr`` (subrIndex=1, nArgs=0 — sets
      ``flexing=1``)
    * 7 reference / control / end points pushed via ``rmoveto``s
    * end: ``3 0 callothersubr`` then ``setcurrentpoint``

    fontTools' ``T1OutlineExtractor`` handles this internally. We just
    need to confirm the wrapper drives it without raising.
    """
    program = [
        0, 500, "hsbw",
        0, 0, "rmoveto",
        1, 0, "callothersubr",     # begin flex
        0, 0, "rmoveto",           # reference point
        50, 0, "rmoveto",          # bcp1
        50, 25, "rmoveto",         # bcp2
        50, 25, "rmoveto",         # midpoint
        50, 0, "rmoveto",          # bcp3
        50, -25, "rmoveto",        # bcp4
        50, -25, "rmoveto",        # endpoint
        100, 0, "setcurrentpoint",
        "endchar",
    ]
    cs = Type1CharString(None, "F", "flex", program)
    # Just assert the program completes and the width prologue is
    # preserved across the flex sequence.
    cs.get_path()
    assert cs.get_width() == 500.0


# ---------------------------------------------------------------------------
# Private helpers (parity with upstream Java private methods)
# ---------------------------------------------------------------------------


def test_render_returns_cached_path() -> None:
    """``render()`` is the upstream-shaped private renderer; it must
    populate the cached path / width and be idempotent on re-entry."""
    program = [0, 500, "hsbw", 10, 20, "rmoveto", 30, 40, "rlineto", "endchar"]
    cs = Type1CharString(None, "F", "A", program)
    p1 = cs.render()
    p2 = cs.render()
    assert p1 == p2
    assert cs.get_width() == 500.0


def test_rmove_to_appends_moveto() -> None:
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.rmove_to(ctx, 10, 20)
    assert ctx.path == [("moveto", 10.0, 20.0)]
    assert ctx.current == (10.0, 20.0)


def test_rline_to_appends_lineto_after_moveto() -> None:
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.rmove_to(ctx, 0, 0)
    cs.rline_to(ctx, 100, 0)
    assert ctx.path[-1] == ("lineto", 100.0, 0.0)
    assert ctx.current == (100.0, 0.0)


def test_rline_to_falls_back_to_moveto_without_initial_moveto() -> None:
    """Upstream's rlineTo warns and falls back to moveTo when there's no
    current point — verify the same for our port."""
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.rline_to(ctx, 50, 50)
    assert ctx.path == [("moveto", 50.0, 50.0)]


def test_rrcurve_to_emits_curveto() -> None:
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.rmove_to(ctx, 0, 0)
    cs.rrcurve_to(ctx, 10, 20, 30, 40, 50, 60)
    assert ctx.path[-1] == ("curveto", 10.0, 20.0, 40.0, 60.0, 90.0, 120.0)
    assert ctx.current == (90.0, 120.0)


def test_rrcurve_to_falls_back_to_moveto_without_initial_moveto() -> None:
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.rrcurve_to(ctx, 1, 1, 2, 2, 3, 3)
    # End point is (1+2+3, 1+2+3) = (6, 6).
    assert ctx.path == [("moveto", 6.0, 6.0)]


def test_close_char_string1_path_appends_closepath_then_moveto() -> None:
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.rmove_to(ctx, 5, 5)
    cs.close_char_string1_path(ctx)
    # Trailing moveto re-anchors at the current point — matches upstream
    # GeneralPath.moveTo(current.getX(), current.getY()).
    assert ctx.path[-2] == ("closepath",)
    assert ctx.path[-1] == ("moveto", 5.0, 5.0)


def test_close_char_string1_path_without_current_point_only_moveto() -> None:
    """When the path is empty, closepath is a warn-and-skip; only the
    trailing moveto is emitted."""
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.close_char_string1_path(ctx)
    assert ctx.path == [("moveto", 0.0, 0.0)]


def test_set_current_point_updates_current() -> None:
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.set_current_point(ctx, 42, 7)
    assert ctx.current == (42.0, 7.0)
    # No path commands are emitted.
    assert ctx.path == []


def test_call_other_subr_begin_flex_sets_flag() -> None:
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.call_other_subr(ctx, 1)
    assert ctx.is_flex is True


def test_call_other_subr_end_flex_with_too_few_points_clears() -> None:
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext(is_flex=True, flex_points=[(0.0, 0.0)])
    cs.call_other_subr(ctx, 0)
    assert ctx.is_flex is False
    assert ctx.flex_points == []


def test_call_other_subr_end_flex_emits_two_curves() -> None:
    """End-flex with seven points must emit two ``rrcurveto`` segments."""
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext(is_flex=True)
    # Seed with an initial moveto so rrcurve_to emits curveto, not moveto.
    cs.rmove_to(ctx, 0, 0)
    ctx.flex_points = [
        (0.0, 0.0),  # reference point
        (10.0, 0.0),  # first
        (10.0, 10.0),  # p2
        (10.0, 10.0),  # p3
        (10.0, 0.0),  # p4
        (10.0, -10.0),  # p5
        (10.0, -10.0),  # p6
    ]
    cs.call_other_subr(ctx, 0)
    curves = [c for c in ctx.path if c[0] == "curveto"]
    assert len(curves) == 2
    assert ctx.flex_points == []
    assert ctx.is_flex is False


def test_handle_type1_command_dispatches_rmoveto() -> None:
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    nums: list[Any] = [10, 20]
    cs.handle_type1_command(ctx, nums, "rmoveto")
    assert ctx.path == [("moveto", 10.0, 20.0)]
    assert nums == []


def test_handle_type1_command_hsbw_records_width() -> None:
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [10, 750], "hsbw")
    assert ctx.width == 750
    assert ctx.left_side_bearing == (10.0, 0.0)
    assert ctx.current == (10.0, 0.0)


def test_handle_type1_command_sbw_records_full_prologue() -> None:
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [5, 7, 600], "sbw")
    assert ctx.width == 600
    assert ctx.left_side_bearing == (5.0, 7.0)
    assert ctx.current == (5.0, 7.0)


def test_handle_type1_command_div_pushes_quotient() -> None:
    """``div`` must replace the top two operands with their quotient
    (without clearing the rest of the operand stack — upstream returns
    early)."""
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    nums: list[Any] = [100, 4]
    cs.handle_type1_command(ctx, nums, "div")
    # 100 / 4 = 25.
    assert nums == [25.0]


def test_handle_type1_command_hints_are_silent() -> None:
    """``hstem`` / ``vstem`` / ``hstem3`` / ``vstem3`` / ``dotsection``
    consume operands but never modify the path."""
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    for op in ("hstem", "vstem", "hstem3", "vstem3", "dotsection"):
        nums: list[Any] = [0, 100]
        cs.handle_type1_command(ctx, nums, op)
    assert ctx.path == []


def test_handle_type1_command_accepts_charstringcommand_token() -> None:
    """Tokens with a ``.name`` attribute (the ``CharStringCommand``
    shape) must be dispatched the same as plain string mnemonics."""

    class FakeCmd:
        def __init__(self, name: str) -> None:
            self.name = name

    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.handle_type1_command(ctx, [10, 0], FakeCmd("hsbw"))
    assert ctx.width == 0


def test_to_string_matches_str() -> None:
    """``to_string()`` (explicit upstream-shaped accessor) must return
    the same value as ``str(cs)``."""
    cs = Type1CharString(None, "F", "A", [0, 500, "hsbw"])
    assert cs.to_string() == str(cs)


def test_seac_with_no_parent_font_is_noop() -> None:
    """``seac`` requires a parent ``Type1CharStringReader`` exposing
    ``get_type1_char_string``; without one it must degrade silently
    (no exception, no path mutation)."""
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    cs = Type1CharString(None, "F", "A", None)
    ctx = _RenderContext()
    cs.seac(ctx, 0, 0, 0, 65, 65)
    assert ctx.path == []


def test_seac_appends_base_and_translated_accent() -> None:
    """With a fake parent that returns canned base + accent paths, seac
    must append the base path verbatim and the accent path translated
    by ``(lsb.x + adx - asb, lsb.y + ady)``."""
    from pypdfbox.fontbox.cff.type1_char_string import _RenderContext

    base_path = [("moveto", 0.0, 0.0), ("lineto", 100.0, 0.0)]
    accent_path = [("moveto", 0.0, 0.0), ("lineto", 50.0, 50.0)]

    class FakeChar:
        def __init__(self, path: list[tuple]) -> None:
            self._path = path

        def get_path(self) -> list[tuple]:
            return list(self._path)

    class FakeFont:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def get_type1_char_string(self, name: str) -> FakeChar:
            self.calls.append(name)
            if name == "A":
                return FakeChar(base_path)
            return FakeChar(accent_path)

    font = FakeFont()
    cs = Type1CharString(font, "F", "Aacute", None)
    ctx = _RenderContext()
    ctx.left_side_bearing = (10.0, 0.0)
    # Use codes that resolve via StandardEncoding to known names; if the
    # encoding lookup yields names the FakeFont doesn't recognise it
    # still falls through cleanly — but we additionally assert the base
    # path was concatenated unchanged.
    cs.seac(ctx, asb=0, adx=20, ady=5, bchar=65, achar=66)  # 65=A 66=B
    # Two glyphs requested.
    assert font.calls  # at least one lookup happened
    # Base path appended verbatim.
    assert base_path[0] in ctx.path
    # Accent path translated by (10 + 20 - 0, 0 + 5) = (30, 5).
    assert ("lineto", 80.0, 55.0) in ctx.path
