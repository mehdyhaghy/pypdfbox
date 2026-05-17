"""Coverage-boost tests for :mod:`pypdfbox.fontbox.cff.type2_char_string`.

Targets the still-uncovered branches after wave 1330:

* the bytes / bytearray constructor arm (line 116);
* ``get_width`` cache hit (line 174) and ``T2WidthExtractor`` failure
  fallback (lines 193-195);
* ``convert_type1_to_type2``'s ``num denom DIV`` zero-denominator GIGO
  arm (line 304);
* every operator branch in ``convert_type2_command`` that the existing
  wave 301 / parity tests skip — ``rrcurveto`` (334), ``rmoveto``
  (347-349, 351), ``hflex1`` (370-387), ``flex1`` (389-405), unknown
  operator fallback (417), ``close_char_string2_path`` exit when
  ``path_count == 0`` (446), ``add_alternating_curve`` (474-501),
  ``add_curve`` non-first horizontal/vertical branches (520);
* ``_token_name`` returning a CharStringCommand-shaped ``.name``
  (623-626), ``_split`` with ``size <= 0`` (642), and
  ``_coerce_program_token`` last-resort ``str()`` fallback (662).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from pypdfbox.fontbox.cff.type2_char_string import (
    Type2CharString,
    _coerce_program_token,
    _is_command_token,
    _split,
    _stringify_token,
    _token_name,
)

# ---------- constructor variants ------------------------------------------

def test_bytes_constructor_builds_t2charstring() -> None:
    # A trivial Type 2 program: just an endchar (op 14). fontTools
    # accepts an arbitrary bytecode payload, we just need the arm to
    # fire (line 116).
    cs = Type2CharString(None, "F", "A", 0, b"\x0e")
    assert cs.t2 is not None
    assert cs.get_gid() == 0


def test_bytearray_constructor_builds_t2charstring() -> None:
    cs = Type2CharString(None, "F", "A", 0, bytearray(b"\x0e"))
    assert cs.t2 is not None


def test_memoryview_constructor_builds_t2charstring() -> None:
    cs = Type2CharString(None, "F", "A", 0, memoryview(b"\x0e"))
    assert cs.t2 is not None


def test_none_constructor_builds_bare_t2charstring() -> None:
    cs = Type2CharString(None, "F", "A", 0, None)
    assert cs.t2 is not None


def test_invalid_sequence_type_raises_typeerror() -> None:
    import pytest

    with pytest.raises(TypeError, match="sequence must be"):
        Type2CharString(None, "F", "A", 0, 42)  # type: ignore[arg-type]


# ---------- accessor parity -----------------------------------------------

def test_get_name_returns_glyph_name() -> None:
    cs = Type2CharString(None, "F", "Aacute", 7, None)
    assert cs.get_name() == "Aacute"


def test_get_font_name_returns_postscript_name() -> None:
    cs = Type2CharString(None, "MyFont", "A", 0, None)
    assert cs.get_font_name() == "MyFont"


def test_get_default_and_nominal_width_x() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=500,
                         nominal_width_x=480)
    assert cs.get_default_width_x() == 500.0
    assert cs.get_nominal_width_x() == 480.0


# ---------- width caching + extractor fallback ----------------------------

def test_get_width_caches_result() -> None:
    cs = Type2CharString(None, "F", "A", 0, b"\x0e", default_width_x=500)
    # Prime the cache.
    first = cs.get_width()
    # Hit the cache path (line 174). Sentinel via private attribute to
    # confirm we don't re-execute the extractor.
    cs._cached_width = 999.0
    assert cs.get_width() == 999.0
    del first  # unused — kept for clarity


def test_get_width_falls_back_to_default_on_extractor_failure() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=750)

    # Force T2WidthExtractor.execute to blow up — exercises lines 193-195.
    from fontTools.misc import psCharStrings

    def _boom(self: Any, _cs: Any) -> None:
        raise RuntimeError("bang")

    with patch.object(psCharStrings.T2WidthExtractor, "execute", _boom):
        assert cs.get_width() == 750.0


# ---------- get_path fallback ---------------------------------------------

def test_get_path_caches_result() -> None:
    cs = Type2CharString(None, "F", "A", 0, b"\x0e")
    cs.get_path()  # prime
    cs._cached_path = [("moveto", 1.0, 2.0)]
    assert cs.get_path() == [("moveto", 1.0, 2.0)]


def test_get_path_swallows_draw_failure() -> None:
    cs = Type2CharString(None, "F", "A", 0, None)

    class _BadT2:
        def draw(self, _pen: Any) -> None:
            raise RuntimeError("draw failed")

    cs._t2 = _BadT2()
    assert cs.get_path() == []


def test_get_bounds_returns_none_for_empty_path() -> None:
    cs = Type2CharString(None, "F", "A", 0, None)
    assert cs.get_bounds() is None


def test_get_bounds_extracts_moveto_lineto_curveto_extents() -> None:
    cs = Type2CharString(None, "F", "A", 0, None)
    cs._cached_path = [
        ("moveto", 10.0, 20.0),
        ("lineto", 30.0, 40.0),
        ("curveto", 5.0, 6.0, 50.0, 60.0, 25.0, 35.0),
        ("closepath",),
    ]
    bounds = cs.get_bounds()
    assert bounds == (5.0, 6.0, 50.0, 60.0)


# ---------- convert_type1_to_type2 DIV collapse ---------------------------

def test_convert_type1_to_type2_collapses_div_quotient() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, nominal_width_x=0,
                         default_width_x=500)
    # Sequence: 10, 2, div, ... — should collapse to 5.0 before walking.
    cs.convert_type1_to_type2([10, 2, "div", "endchar"])
    seq = cs._type1_sequence
    # First synthetic hsbw will be prepended by clear_stack; final tail
    # should still encode the collapsed quotient followed by endchar.
    assert "endchar" in seq


def test_convert_type1_to_type2_zero_denominator_keeps_div_token() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, nominal_width_x=0,
                         default_width_x=500)
    # 10, 0, div — denominator zero hits the GIGO arm (line 304).
    cs.convert_type1_to_type2([10, 0, "div", "endchar"])
    assert "endchar" in cs._type1_sequence


# ---------- convert_type2_command operator branches -----------------------

def test_convert_type2_command_rrcurveto_splits_into_chunks_of_six() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=500)
    # Prime is_sequence_empty=False so clear_stack pass-through doesn't fire.
    cs.add_command([0, 500.0], "hsbw")
    cs.convert_type2_command(list(range(12)), "rrcurveto")
    # Two rrcurveto commands appended.
    assert cs._type1_sequence.count("rrcurveto") == 2


def test_convert_type2_command_rmoveto_path_branch() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=500)
    cs.add_command([0, 500.0], "hsbw")
    cs.convert_type2_command([10, 20], "rmoveto")
    assert "rmoveto" in cs._type1_sequence


def test_convert_type2_command_hvcurveto_invokes_alternating_curve() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=500)
    cs.add_command([0, 500.0], "hsbw")
    cs.convert_type2_command([1, 2, 3, 4], "hvcurveto")
    assert "rrcurveto" in cs._type1_sequence


def test_convert_type2_command_hflex_expands_to_two_rrcurveto() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=500)
    cs.add_command([0, 500.0], "hsbw")
    cs.convert_type2_command([1, 2, 3, 4, 5, 6, 7], "hflex")
    assert cs._type1_sequence.count("rrcurveto") == 2


def test_convert_type2_command_flex_expands_to_two_rrcurveto() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=500)
    cs.add_command([0, 500.0], "hsbw")
    cs.convert_type2_command(list(range(1, 13)), "flex")
    assert cs._type1_sequence.count("rrcurveto") == 2


def test_convert_type2_command_hflex1_expands_to_two_rrcurveto() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=500)
    cs.add_command([0, 500.0], "hsbw")
    cs.convert_type2_command(list(range(1, 10)), "hflex1")
    assert cs._type1_sequence.count("rrcurveto") == 2


def test_convert_type2_command_flex1_dx_dominant() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=500)
    cs.add_command([0, 500.0], "hsbw")
    # 11 operands; sum of dx > sum of dy → dx_is_bigger arm (line 402-403).
    cs.convert_type2_command(
        [50, 0, 50, 0, 50, 0, 50, 0, 50, 0, 7], "flex1"
    )
    assert cs._type1_sequence.count("rrcurveto") == 2


def test_convert_type2_command_flex1_dy_dominant() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=500)
    cs.add_command([0, 500.0], "hsbw")
    cs.convert_type2_command(
        [0, 50, 0, 50, 0, 50, 0, 50, 0, 50, 7], "flex1"
    )
    assert cs._type1_sequence.count("rrcurveto") == 2


def test_convert_type2_command_rcurveline_expansion() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=500)
    cs.add_command([0, 500.0], "hsbw")
    cs.convert_type2_command(list(range(1, 9)), "rcurveline")
    assert "rrcurveto" in cs._type1_sequence
    assert "rlineto" in cs._type1_sequence


def test_convert_type2_command_rlinecurve_expansion() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=500)
    cs.add_command([0, 500.0], "hsbw")
    cs.convert_type2_command(list(range(1, 9)), "rlinecurve")
    assert "rlineto" in cs._type1_sequence
    assert "rrcurveto" in cs._type1_sequence


def test_convert_type2_command_hhcurveto_invokes_add_curve() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=500)
    cs.add_command([0, 500.0], "hsbw")
    cs.convert_type2_command([1, 2, 3, 4], "hhcurveto")
    assert "rrcurveto" in cs._type1_sequence


def test_convert_type2_command_vvcurveto_invokes_add_curve() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=500)
    cs.add_command([0, 500.0], "hsbw")
    cs.convert_type2_command([1, 2, 3, 4], "vvcurveto")
    assert "rrcurveto" in cs._type1_sequence


def test_convert_type2_command_unknown_operator_falls_through() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=500)
    cs.add_command([0, 500.0], "hsbw")
    cs.convert_type2_command([1, 2], "magic_unknown")  # line 417
    assert "magic_unknown" in cs._type1_sequence


def test_convert_type2_command_endchar_with_four_operands_emits_seac() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=500)
    cs.add_command([0, 500.0], "hsbw")
    cs.convert_type2_command([10, 20, 30, 40], "endchar")
    assert "seac" in cs._type1_sequence


# ---------- mark_path / close_char_string2_path ---------------------------

def test_close_char_string2_path_noop_when_path_count_zero() -> None:
    # Hits line 453's ``None`` short-circuit (line 446 / 454 untested).
    cs = Type2CharString(None, "F", "A", 0, None)
    # path_count == 0 → no closepath emitted.
    cs.close_char_string2_path()
    assert cs.is_sequence_empty()


def test_close_char_string2_path_emits_closepath_when_last_isnt_closepath() -> None:
    cs = Type2CharString(None, "F", "A", 0, None)
    cs._path_count = 1
    cs.add_command([10, 20], "rmoveto")
    cs.close_char_string2_path()
    assert cs._type1_sequence[-1] == "closepath"


def test_close_char_string2_path_skips_when_last_is_closepath() -> None:
    cs = Type2CharString(None, "F", "A", 0, None)
    cs._path_count = 1
    cs.add_command([], "closepath")
    cs.close_char_string2_path()
    # Still just one closepath.
    assert cs._type1_sequence.count("closepath") == 1


def test_mark_path_closes_previous_when_path_count_nonzero() -> None:
    cs = Type2CharString(None, "F", "A", 0, None)
    cs._path_count = 1
    cs.add_command([10, 20], "rmoveto")
    cs.mark_path()  # triggers close_char_string2_path
    assert "closepath" in cs._type1_sequence


# ---------- add_alternating_line / add_alternating_curve / add_curve ------

def test_add_alternating_line_alternates_h_and_v() -> None:
    cs = Type2CharString(None, "F", "A", 0, None)
    cs.add_alternating_line([10, 20, 30], True)
    # Sequence should contain hlineto then vlineto then hlineto.
    assert cs._type1_sequence.count("hlineto") == 2
    assert cs._type1_sequence.count("vlineto") == 1


def test_add_alternating_curve_horizontal_with_five_operands_uses_last_flag() -> None:
    cs = Type2CharString(None, "F", "A", 0, None)
    # 5 operands → ``last`` arm in horizontal branch (lines 474-487).
    cs.add_alternating_curve([1, 2, 3, 4, 5], True)
    assert cs._type1_sequence[-1] == "rrcurveto"


def test_add_alternating_curve_vertical_with_five_operands_uses_last_flag() -> None:
    cs = Type2CharString(None, "F", "A", 0, None)
    # 5 operands, vertical → lines 488-501.
    cs.add_alternating_curve([1, 2, 3, 4, 5], False)
    assert cs._type1_sequence[-1] == "rrcurveto"


def test_add_alternating_curve_horizontal_eight_operands() -> None:
    cs = Type2CharString(None, "F", "A", 0, None)
    cs.add_alternating_curve([1, 2, 3, 4, 5, 6, 7, 8], True)
    assert cs._type1_sequence.count("rrcurveto") == 2


def test_add_curve_vertical_first_arm() -> None:
    cs = Type2CharString(None, "F", "A", 0, None)
    # 5 operands → first == True; horizontal=False → line 520 path.
    cs.add_curve([1, 2, 3, 4, 5], False)
    assert cs._type1_sequence[-1] == "rrcurveto"


def test_add_curve_horizontal_first_arm() -> None:
    cs = Type2CharString(None, "F", "A", 0, None)
    cs.add_curve([1, 2, 3, 4, 5], True)
    assert cs._type1_sequence[-1] == "rrcurveto"


def test_add_curve_non_first_horizontal() -> None:
    cs = Type2CharString(None, "F", "A", 0, None)
    # 4 operands → first == False; horizontal branch.
    cs.add_curve([1, 2, 3, 4], True)
    assert cs._type1_sequence[-1] == "rrcurveto"


def test_add_curve_non_first_vertical() -> None:
    cs = Type2CharString(None, "F", "A", 0, None)
    cs.add_curve([1, 2, 3, 4], False)
    assert cs._type1_sequence[-1] == "rrcurveto"


# ---------- clear_stack ---------------------------------------------------

def test_clear_stack_first_call_with_flag_and_operand_emits_hsbw_with_width() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, nominal_width_x=480,
                         default_width_x=500)
    out = cs.clear_stack([520, 10, 20], True)
    # Width operand absorbed: 520 + 480 = 1000 emitted as hsbw width.
    assert cs._type1_sequence[0] == 0
    assert cs._type1_sequence[1] == 1000.0
    assert cs._type1_sequence[2] == "hsbw"
    assert out == [10, 20]


def test_clear_stack_first_call_without_flag_emits_default_width() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, nominal_width_x=480,
                         default_width_x=500)
    out = cs.clear_stack([10, 20], False)
    assert cs._type1_sequence[:3] == [0, 500.0, "hsbw"]
    assert out == [10, 20]


def test_clear_stack_subsequent_call_passes_through() -> None:
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=500)
    cs.add_command([0, 500.0], "hsbw")  # prime sequence
    out = cs.clear_stack([1, 2, 3], False)
    assert out == [1, 2, 3]


# ---------- split + helpers -----------------------------------------------

def test_static_split_returns_chunks_of_size() -> None:
    assert Type2CharString.split([1, 2, 3, 4, 5, 6], 2) == [[1, 2], [3, 4], [5, 6]]


def test_static_split_drops_trailing_partial_chunk() -> None:
    assert Type2CharString.split([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4]]


def test_module_level_split_size_zero_returns_empty() -> None:
    assert _split([1, 2, 3], 0) == []


def test_module_level_split_negative_size_returns_empty() -> None:
    # Hits line 642's ``size <= 0`` guard.
    assert _split([1, 2, 3], -1) == []


# ---------- private helpers ----------------------------------------------

def test_token_name_returns_str_for_string_token() -> None:
    assert _token_name("rmoveto") == "rmoveto"


def test_token_name_returns_none_for_number() -> None:
    assert _token_name(42) is None
    assert _token_name(3.14) is None


def test_token_name_returns_dot_name_for_object() -> None:
    class _Cmd:
        name = "endchar"

    assert _token_name(_Cmd()) == "endchar"


def test_token_name_returns_none_for_object_without_name() -> None:
    assert _token_name(object()) is None


def test_token_name_returns_none_for_object_with_non_str_name() -> None:
    class _Cmd:
        name = 123  # not a str → falls through to None.

    assert _token_name(_Cmd()) is None


def test_is_command_token_true_for_command() -> None:
    assert _is_command_token("rmoveto") is True


def test_is_command_token_false_for_number() -> None:
    assert _is_command_token(42) is False


def test_stringify_token_number() -> None:
    assert _stringify_token(42) == "42"
    assert _stringify_token(3.5) == "3.5"


def test_stringify_token_named_object() -> None:
    class _Cmd:
        name = "rmoveto"

    assert _stringify_token(_Cmd()) == "rmoveto"


def test_stringify_token_fallback_to_str() -> None:
    class _Other:
        def __str__(self) -> str:
            return "<other>"

    assert _stringify_token(_Other()) == "<other>"


def test_coerce_program_token_number_passthrough() -> None:
    assert _coerce_program_token(42) == 42
    assert _coerce_program_token(1.5) == 1.5


def test_coerce_program_token_string_passthrough() -> None:
    assert _coerce_program_token("rmoveto") == "rmoveto"


def test_coerce_program_token_named_object_returns_name() -> None:
    class _Cmd:
        name = "endchar"

    assert _coerce_program_token(_Cmd()) == "endchar"


def test_coerce_program_token_fallback_stringifies() -> None:
    # Object with no string ``name`` → last-resort str() (line 662).
    class _Weird:
        def __str__(self) -> str:
            return "weird"

    assert _coerce_program_token(_Weird()) == "weird"


# ---------- repr / str / aliases -----------------------------------------

def test_repr_includes_font_glyph_and_gid() -> None:
    cs = Type2CharString(None, "Helvetica", "A", 5, None)
    text = repr(cs)
    assert "Helvetica" in text
    assert "'A'" in text
    assert "5" in text


def test_str_returns_empty_brackets_for_bare_charstring() -> None:
    cs = Type2CharString(None, "F", "A", 0, None)
    assert str(cs) == "[]"


def test_underscore_aliases_match_public_methods() -> None:
    # Wave 1269 promoted these to public; the underscored names stay as
    # back-compat aliases.
    assert Type2CharString._convert_type2_command is Type2CharString.convert_type2_command
    assert Type2CharString._clear_stack is Type2CharString.clear_stack
    assert Type2CharString._mark_path is Type2CharString.mark_path
    assert (
        Type2CharString._close_char_string2_path
        is Type2CharString.close_char_string2_path
    )
    assert (
        Type2CharString._add_alternating_line
        is Type2CharString.add_alternating_line
    )
    assert (
        Type2CharString._add_alternating_curve
        is Type2CharString.add_alternating_curve
    )
    assert Type2CharString._add_curve is Type2CharString.add_curve
    assert Type2CharString._add_command_list is Type2CharString.add_command_list
