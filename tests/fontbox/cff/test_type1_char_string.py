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
