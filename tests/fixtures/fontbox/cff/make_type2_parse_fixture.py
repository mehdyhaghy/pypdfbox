"""Deterministic generator for the synthetic *name-keyed* CFF (Type1C) fixture
used by the Type 2 char-string *parser* differential oracle
(``CffType2ParseProbe`` / ``test_cff_type2_parse_oracle``).

This is an *original* test fixture (not ported from Apache PDFBox). The
existing synthetic CFFs in this directory carry only trivial ``100 endchar``
glyphs — they never exercise the parser's interesting branches. This font's
glyphs are hand-designed so that, between them, the compiled Type 2 programs
cover every byte-level decoder path in
``org.apache.fontbox.cff.Type2CharStringParser``:

* every operand encoding fontTools emits — the 1-byte form (32-246), the
  2-byte forms (247-254 positive / 251-254 negative), the ``28`` short-int,
  and the ``255`` 16.16 fixed (via a fractional operand);
* hint operators ``hstemhm`` / ``vstemhm`` plus ``hintmask`` and ``cntrmask``
  so the stem-count -> ``getMaskLength`` -> mask-byte-skip path runs (and the
  implicit ``vstem`` count from operands left on the stack before a mask);
* a ``callsubr`` into a local /Subrs entry, so subroutine unrolling + bias
  (``calculateSubrNumber``) + trailing-``RET`` trimming all run;
* curve / flex operators (``rrcurveto``, ``flex``) for completeness.

Both engines parse the *same* CFF bytes, so any divergence in the emitted
operand/command token stream is a real decoder bug, not a layout artifact.
The bytes are produced by fontTools' ``CFFFontSet.compile`` (MIT) and are
fully deterministic; re-running this module regenerates them byte-for-byte.

Run from the repo root::

    .venv/bin/python tests/fixtures/fontbox/cff/make_type2_parse_fixture.py
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fontTools.cffLib import (
    CFFFontSet,
    CharStrings,
    GlobalSubrsIndex,
    IndexedStrings,
    PrivateDict,
    SubrsIndex,
    TopDict,
    TopDictIndex,
)
from fontTools.misc.psCharStrings import T2CharString

_HERE = Path(__file__).resolve().parent


class _StubFont:
    recalcBBoxes = False
    recalcTimestamp = False


# Local subr 0: a small curve fragment ending in ``return`` so the parser's
# trailing-RET trim and subr inlining both run when a glyph calls it.
_SUBR0 = [10, 0, 0, 20, 20, 0, "rrcurveto", "return"]


# One program per glyph. Designed so the union covers every decoder branch.
# Note: the leading number on each program is the advance-width operand
# (width - nominalWidthX); fontTools/PDFBox both treat it as a normal leading
# operand, so it simply appears as the first token of the parsed sequence.
_GLYPHS: dict[str, list[object]] = {
    ".notdef": [0, "endchar"],
    # hstemhm + vstemhm + hintmask: drives stem counting + mask-byte skip.
    # 2 hstem pairs (4 operands) -> hstemhm; 2 vstem pairs -> vstemhm; then
    # hintmask consumes ceil(4/8)=1 mask byte. rmoveto/rlineto draw a box.
    "A": [
        50, 100, 20, 80, "hstemhm",
        30, 60, 40, 70, "vstemhm",
        "hintmask", 0,
        100, 200, "rmoveto",
        50, 0, "rlineto",
        0, 50, "rlineto",
        "endchar",
    ],
    # implicit vstem before hintmask: operands left on the stack ahead of the
    # mask are counted as vstem pairs (the parser's countNumbers/2 path).
    "B": [
        10, 40, 20, 60, "hstem",
        30, 90, "hintmask", 0,
        70, 70, "rmoveto",
        -107, "callsubr",
        "endchar",
    ],
    # cntrmask + a curve + a flex; also a negative 2-byte operand (-200) and
    # a big positive 2-byte operand (1000) to hit the 247-254 / 251-254 forms.
    "C": [
        100, 50, "vstemhm",
        "cntrmask", 0,
        1000, -200, "rmoveto",
        20, 30, 40, 50, 60, 70, "rrcurveto",
        10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, "flex",
        "endchar",
    ],
    # short-int (28) + 16.16 fixed (255). fontTools emits 28 for values in
    # [-32768,32767] not representable in the 2-byte forms, and 255 for a
    # fractional operand. 8000 forces the 28 short-int; 1.5 forces the 255
    # fixed encoding.
    "D": [
        8000, "hmoveto",
        1.5, 0, "rlineto",
        -32000, 100, "rlineto",
        "endchar",
    ],
}


def build_fixture() -> bytes:
    cff = CFFFontSet()
    cff.major, cff.minor = 1, 0
    cff.hdrSize = 4
    cff.offSize = 2
    cff.fontNames = ["SynthType2Parse"]
    cff.strings = IndexedStrings()
    cff.GlobalSubrs = GlobalSubrsIndex()

    top = TopDict(strings=cff.strings)
    top.cff = cff
    top.FontMatrix = [0.001, 0, 0, 0.001, 0, 0]
    top.GlobalSubrs = cff.GlobalSubrs

    priv = PrivateDict()
    priv.defaultWidthX = 0
    priv.nominalWidthX = 0
    subrs = SubrsIndex()
    subrs.append(T2CharString(program=list(_SUBR0)))
    priv.Subrs = subrs
    top.Private = priv

    names = list(_GLYPHS.keys())
    char_strings = CharStrings(None, None, cff.GlobalSubrs, priv, None, None)
    for name, program in _GLYPHS.items():
        cs = T2CharString(program=list(program))
        cs.private = priv
        cs.globalSubrs = cff.GlobalSubrs
        char_strings.charStrings[name] = cs
    top.CharStrings = char_strings
    top.charset = names

    top_index = TopDictIndex()
    top_index.items = [top]
    cff.topDictIndex = top_index

    buf = BytesIO()
    cff.compile(buf, _StubFont())
    return buf.getvalue()


def main() -> None:
    (_HERE / "type2_parse.cff").write_bytes(build_fixture())


if __name__ == "__main__":
    main()
