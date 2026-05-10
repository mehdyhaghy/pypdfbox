"""Hand-written tests for ``pypdfbox.fontbox.cff.Type2CharString``.

We exercise both the bare/empty constructor (no fontTools state) and a
real-glyph path: pull an OTF off the host's font directories, hand the
CFF bytes to :class:`CFFFont`, and walk every glyph via
``get_type2_char_string``.

When no OTF is available the module skips — same convention as
``test_cff_font_parity``.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.fontbox.cff.type2_char_string import Type2CharString

_OTF_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/STIXGeneral.otf",
    "/System/Library/Fonts/Supplemental/STIXGeneralItalic.otf",
    "/usr/share/fonts/opentype/stix/STIXGeneral.otf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def _load_cff_bytes() -> bytes | None:
    try:
        from fontTools.ttLib import TTFont  # noqa: PLC0415
    except ImportError:
        return None
    for candidate in _OTF_CANDIDATES:
        path = Path(candidate)
        if not path.exists():
            continue
        try:
            ttf = TTFont(str(path))
            if "CFF " not in ttf:
                continue
            buf = io.BytesIO()
            ttf["CFF "].cff.compile(buf, ttf, isCFF2=False)
            return buf.getvalue()
        except Exception:  # noqa: BLE001
            continue
    return None


_CFF_BYTES = _load_cff_bytes()
_SKIP_REASON = "no CFF/OTF fixture available on this host"


# ---------------------------------------------------------------------------
# Bare constructor — no fontTools state required
# ---------------------------------------------------------------------------


def test_empty_charstring_accessors_safe() -> None:
    """A Type2CharString with no program must answer all accessors with
    safe defaults; ``get_path()`` must return an empty list, never raise."""
    cs = Type2CharString(
        font=None,
        font_name="Helvetica",
        glyph_name=".notdef",
        gid=0,
        sequence=None,
        default_width_x=500,
        nominal_width_x=0,
    )
    assert cs.get_gid() == 0
    assert cs.get_name() == ".notdef"
    assert cs.get_font_name() == "Helvetica"
    assert cs.get_default_width_x() == 500.0
    assert cs.get_nominal_width_x() == 0.0
    # No program → empty path, no crash.
    assert cs.get_path() == []
    # Bounds of empty path is None.
    assert cs.get_bounds() is None
    # Width for an empty charstring: the T2WidthExtractor sees no
    # operands at all, so .width stays 0 — matches upstream's
    # Type1CharString.getWidth() returning the unset 0 field. The
    # accessor must return a float, not raise.
    w = cs.get_width()
    assert isinstance(w, float)
    assert w == 0.0


def test_constructor_rejects_wrong_sequence_type() -> None:
    with pytest.raises(TypeError):
        Type2CharString(
            font=None,
            font_name="X",
            glyph_name="A",
            gid=1,
            sequence=42,  # not a T2CharString / bytes / list / None
        )


def test_repr_carries_font_and_gid() -> None:
    cs = Type2CharString(None, "Foo", "A", 7, None)
    text = repr(cs)
    assert "Foo" in text
    assert "'A'" in text
    assert "gid=7" in text


# ---------------------------------------------------------------------------
# Sequence accessors (parity with upstream Type1CharString protected API)
# ---------------------------------------------------------------------------


def test_sequence_accessors_empty_by_default() -> None:
    """A freshly-constructed Type2CharString has an empty Type 1 sequence
    buffer. Mirrors upstream ``isSequenceEmpty()`` /
    ``getLastSequenceEntry()`` (inherited from ``Type1CharString``)."""
    cs = Type2CharString(None, "F", "A", 0, None)
    assert cs.is_sequence_empty() is True
    assert cs.get_last_sequence_entry() is None


def test_add_command_populates_sequence() -> None:
    """``add_command`` appends operands then the command token — matches
    upstream ``Type1CharString.addCommand(numbers, command)``, used by
    upstream's ``Type2CharString.convertType1ToType2``."""
    cs = Type2CharString(None, "F", "A", 0, None)
    cs.add_command([0, 500], "hsbw")
    assert cs.is_sequence_empty() is False
    assert cs.get_last_sequence_entry() == "hsbw"
    cs.add_command([100, 0], "rlineto")
    assert cs.get_last_sequence_entry() == "rlineto"


def test_str_renders_after_add_command() -> None:
    """``__str__`` mirrors upstream ``toString()`` once the conversion
    buffer has been populated."""
    cs = Type2CharString(None, "F", "A", 0, None)
    cs.add_command([0, 500], "hsbw")
    text = str(cs)
    assert text.startswith("[")
    assert text.endswith("]")
    assert "," not in text
    assert "hsbw" in text


def test_str_on_empty_sequence_returns_empty_brackets() -> None:
    cs = Type2CharString(None, "F", "A", 0, None)
    assert str(cs) == "[]"


# ---------------------------------------------------------------------------
# Real-font integration — needs a host OTF
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cff_font() -> CFFFont:
    if _CFF_BYTES is None:
        pytest.skip(_SKIP_REASON)
    return CFFFont.from_bytes(_CFF_BYTES)


def test_get_type2_char_string_returns_wrapper(cff_font: CFFFont) -> None:
    cs = cff_font.get_type2_char_string(0)
    assert isinstance(cs, Type2CharString)
    assert cs.get_gid() == 0
    # GID 0 is .notdef in well-formed CFF.
    assert cs.get_name() == ".notdef"


def test_get_type2_char_string_path_is_drawable(cff_font: CFFFont) -> None:
    """Pull a non-trivial glyph and verify the recording pen captures
    at least one moveto + a non-empty command list."""
    n = cff_font.get_num_char_strings()
    assert n > 1
    # Sample a handful of GIDs across the charset; at least one must
    # have a non-empty path. We don't lock in a specific GID because
    # the host font isn't fixed.
    indices = [1, n // 4, n // 2, max(1, n - 1)]
    found_path = False
    for gid in indices:
        cs = cff_font.get_type2_char_string(gid)
        path = cs.get_path()
        assert isinstance(path, list)
        if path:
            found_path = True
            # First command must be a moveto.
            assert path[0][0] == "moveto"
            # Bounds must be a 4-tuple of floats with xmin<=xmax, ymin<=ymax.
            bounds = cs.get_bounds()
            assert bounds is not None
            xmin, ymin, xmax, ymax = bounds
            assert xmin <= xmax
            assert ymin <= ymax
            break
    assert found_path, "no probed GID produced a non-empty path"


def test_get_type2_char_string_width_matches_cff_font_width(cff_font: CFFFont) -> None:
    """``Type2CharString.get_width`` must match ``CFFFont.get_width(name)``
    for the same glyph — both delegate to fontTools' T2WidthExtractor."""
    n = cff_font.get_num_char_strings()
    charset = cff_font.get_charset()
    # Skip .notdef (GID 0) which often has 0 width in extracted CFFs;
    # pick a glyph that has a real advance.
    sample_gid = 1 if n > 1 else 0
    cs = cff_font.get_type2_char_string(sample_gid)
    name = charset[sample_gid]
    assert cs.get_width() == cff_font.get_width(name)


def test_get_type2_char_string_out_of_range_returns_empty_wrapper(
    cff_font: CFFFont,
) -> None:
    """Out-of-range GIDs must not raise; they return an empty wrapper
    whose path is ``[]`` — see CHANGES.md (deviation from upstream
    which throws IOException)."""
    n = cff_font.get_num_char_strings()
    cs = cff_font.get_type2_char_string(n + 999)
    assert isinstance(cs, Type2CharString)
    assert cs.get_path() == []


def test_path_is_cached(cff_font: CFFFont) -> None:
    """Calling ``get_path`` twice must return equal results without
    re-running the pen (we don't assert identity because the wrapper
    returns a fresh list copy)."""
    cs = cff_font.get_type2_char_string(1)
    p1 = cs.get_path()
    p2 = cs.get_path()
    assert p1 == p2


def test_t2_property_exposes_underlying_charstring(cff_font: CFFFont) -> None:
    """``Type2CharString.t2`` must expose the fontTools T2CharString so
    callers can run their own pens / introspect the program."""
    from fontTools.misc.psCharStrings import T2CharString

    cs = cff_font.get_type2_char_string(1)
    assert isinstance(cs.t2, T2CharString)


# ---------------------------------------------------------------------------
# Type 2 → Type 1 conversion (parity with upstream private convertType2Command)
# ---------------------------------------------------------------------------


def _fresh() -> Type2CharString:
    return Type2CharString(None, "F", "A", 0, None, default_width_x=500, nominal_width_x=0)


def test_convert_emits_hsbw_prologue_when_no_width_operand() -> None:
    """First operator with even-arg count → synthetic ``hsbw 0 defaultWidthX``.
    Mirrors upstream ``clearStack`` (Type2CharString.java:264, ``flag=false``)."""
    cs = _fresh()
    # 4 operands → vstem (even arg count); width omitted → defaultWidthX path.
    cs.convert_type1_to_type2([10, 20, 30, 40, "vstem"])
    seq = cs._type1_sequence
    # Expect hsbw command emitted before any other operator.
    assert seq[:3] == [0, 500.0, "hsbw"]


def test_convert_emits_hsbw_with_width_when_odd_arg_count() -> None:
    """First operator with odd-arg count → leading operand is the
    width-delta. ``hsbw 0 (width + nominalWidthX)``."""
    cs = Type2CharString(None, "F", "A", 0, None, default_width_x=500, nominal_width_x=100)
    # 5 operands for vstem → leading 1234 is width-delta.
    cs.convert_type1_to_type2([1234, 10, 20, 30, 40, "vstem"])
    # The first 3 entries are the synthetic hsbw with the width.
    assert cs._type1_sequence[:3] == [0, 1334.0, "hsbw"]


def test_convert_rlineto_splits_into_pairs() -> None:
    """rlineto with 6 operands → 3 separate rlineto commands of 2
    operands each. Mirrors ``addCommandList(split(numbers, 2),
    command)``."""
    cs = _fresh()
    cs.convert_type1_to_type2([100, 0, 0, 100, -50, 50, "rlineto"])
    rlineto_commands = [
        i for i, t in enumerate(cs._type1_sequence) if t == "rlineto"
    ]
    # 3 split rlinetos → 3 rlineto tokens.
    assert len(rlineto_commands) == 3


def test_convert_hlineto_alternates() -> None:
    """``addAlternatingLine`` peels off one operand per command,
    flipping horizontal/vertical. Upstream's switch for hlineto/vlineto
    does NOT pass through ``clearStack`` (Type2CharString.java:157),
    so no synthetic hsbw is emitted by this op alone."""
    cs = _fresh()
    cs.convert_type1_to_type2([10, 20, 30, "hlineto"])
    ops = [t for t in cs._type1_sequence if isinstance(t, str)]
    assert ops == ["hlineto", "vlineto", "hlineto"]


def test_convert_div_collapses_quotient() -> None:
    """PDFBOX-5987: ``num denom div`` is collapsed to its quotient
    *before* the conversion walk. With nominal_width_x=0 and
    default_width_x=500, the leading ``10`` becomes the width-delta
    consumed by clearStack(flag=True), and 2.0 stays as vmoveto's arg."""
    cs = _fresh()
    # 100 50 div → 2.0; rewritten program is [10, 2.0, vmoveto].
    # vmoveto sees size=2 > 1 → flag=True → strips 10 as width-delta,
    # leaving [2.0] for the actual vmoveto.
    cs.convert_type1_to_type2([10, 100, 50, "div", "vmoveto"])
    seq = cs._type1_sequence
    vmoveto_idx = seq.index("vmoveto")
    # Synthetic hsbw with width = 10 + nominal(0) = 10.0.
    assert seq[:3] == [0, 10.0, "hsbw"]
    # Operand directly before vmoveto is the collapsed quotient 2.0.
    assert seq[vmoveto_idx - 1] == 2.0


def test_convert_endchar_closes_path() -> None:
    """endchar after a moveto must emit closepath before endchar."""
    cs = _fresh()
    cs.convert_type1_to_type2([0, 100, "vmoveto", "endchar"])
    seq = cs._type1_sequence
    # closepath emitted before endchar.
    closepath_idx = seq.index("closepath")
    endchar_idx = seq.index("endchar")
    assert closepath_idx < endchar_idx


def test_convert_endchar_seac_form() -> None:
    """endchar with 4 operands → deprecated seac (Type2CharString.java:166)."""
    cs = _fresh()
    cs.convert_type1_to_type2([10, 20, 30, 65, 66, "endchar"])
    # 5 args; clearStack flag triggers (size==5) → drains the leading
    # width operand, leaving 4 args → seac.
    assert "seac" in cs._type1_sequence


def test_convert_flex_expands_to_two_rrcurves() -> None:
    """flex consumes 12 operands and emits two rrcurveto commands."""
    cs = _fresh()
    cs.convert_type1_to_type2(
        [0, 100, "vmoveto", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 50, "flex"]
    )
    rrcurve_count = sum(
        1 for t in cs._type1_sequence if t == "rrcurveto"
    )
    assert rrcurve_count == 2


def test_convert_hflex_expands_to_two_rrcurves() -> None:
    """hflex (7 operands) expands to two rrcurveto commands."""
    cs = _fresh()
    cs.convert_type1_to_type2(
        [0, 100, "vmoveto", 1, 2, 3, 4, 5, 6, 7, "hflex"]
    )
    rrcurve_count = sum(
        1 for t in cs._type1_sequence if t == "rrcurveto"
    )
    assert rrcurve_count == 2


def test_convert_rcurveline_emits_curve_then_line() -> None:
    """rcurveline emits N-2-grouped curves followed by a final line."""
    cs = _fresh()
    cs.convert_type1_to_type2(
        [0, 100, "vmoveto", 1, 2, 3, 4, 5, 6, 7, 8, "rcurveline"]
    )
    seq = cs._type1_sequence
    # Last two operators must be rrcurveto then rlineto.
    str_ops = [t for t in seq if isinstance(t, str)]
    assert str_ops[-2:] == ["rrcurveto", "rlineto"]


def test_convert_rlinecurve_emits_lines_then_curve() -> None:
    """rlinecurve emits 2-grouped lines followed by a final curve."""
    cs = _fresh()
    cs.convert_type1_to_type2(
        [
            0,
            100,
            "vmoveto",
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            "rlinecurve",
        ]
    )
    str_ops = [t for t in cs._type1_sequence if isinstance(t, str)]
    # vmoveto + 2 rlinetos + final rrcurveto preceded by hsbw prologue.
    assert str_ops[-2:] == ["rlineto", "rrcurveto"]


def test_convert_hhcurveto_via_addcurve() -> None:
    """hhcurveto routes through ``_add_curve`` which emits rrcurveto."""
    cs = _fresh()
    cs.convert_type1_to_type2(
        [0, 100, "vmoveto", 10, 20, 30, 40, "hhcurveto"]
    )
    assert "rrcurveto" in cs._type1_sequence


def test_get_gid_returns_constructor_value() -> None:
    """getGID parity (Type2CharString.java:66)."""
    cs = Type2CharString(None, "F", "A", 42, None)
    assert cs.get_gid() == 42


# ---------------------------------------------------------------------------
# Wave 1269 — public charstring conversion helpers (parity with upstream
# private methods on Type2CharString)
# ---------------------------------------------------------------------------


def test_public_helpers_match_underscored_aliases() -> None:
    """Wave 1269 promoted the wave-397 ``_foo`` helpers to public ``foo``
    names (matching upstream Java methods). The old underscored names
    remain as back-compat aliases — verify both are bound to the same
    callable."""
    cs = _fresh()
    pairs = [
        ("clear_stack", "_clear_stack"),
        ("close_char_string2_path", "_close_char_string2_path"),
        ("mark_path", "_mark_path"),
        ("expand_stem_hints", "_expand_stem_hints"),
        ("add_alternating_line", "_add_alternating_line"),
        ("add_alternating_curve", "_add_alternating_curve"),
        ("add_curve", "_add_curve"),
        ("add_command_list", "_add_command_list"),
        ("convert_type2_command", "_convert_type2_command"),
    ]
    for public, private in pairs:
        assert getattr(cs, public).__func__ is getattr(cs, private).__func__


def test_public_clear_stack_emits_default_width_hsbw() -> None:
    """``clear_stack`` (public) drains an even-arg-count first operator
    into a synthetic ``hsbw 0 defaultWidthX``. Upstream Type2CharString.java:264."""
    cs = _fresh()
    out = cs.clear_stack([10, 20, 30, 40], False)
    assert out == [10, 20, 30, 40]
    assert cs._type1_sequence[:3] == [0, 500.0, "hsbw"]


def test_public_split_chunks_list() -> None:
    """``split`` (public, static) carves a flat list into N-sized chunks,
    dropping any trailing partial chunk. Type2CharString.java:375."""
    assert Type2CharString.split([1, 2, 3, 4, 5, 6], 2) == [[1, 2], [3, 4], [5, 6]]
    # Trailing partial chunk dropped.
    assert Type2CharString.split([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4]]


def test_public_add_alternating_line_via_public_helper() -> None:
    """Drive ``add_alternating_line`` directly with the public name."""
    cs = _fresh()
    cs.add_alternating_line([10, 20, 30], True)
    ops = [t for t in cs._type1_sequence if isinstance(t, str)]
    assert ops == ["hlineto", "vlineto", "hlineto"]


def test_public_close_char_string2_path_no_op_without_path() -> None:
    """When ``path_count`` is 0, ``close_char_string2_path`` must not
    emit anything. Type2CharString.java:300."""
    cs = _fresh()
    cs.close_char_string2_path()
    assert cs.is_sequence_empty()
