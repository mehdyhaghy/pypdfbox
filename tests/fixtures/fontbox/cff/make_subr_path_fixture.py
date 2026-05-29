"""Deterministic generator for the synthetic *name-keyed* CFF (Type1C) fixture
used by the CFF subroutine *glyph-path* differential oracle
(``CffSubrPathProbe`` / ``test_cff_subr_path_oracle``).

This is an *original* test fixture (not ported from Apache PDFBox). It is
distinct from ``type2_parse.cff`` (which pins the parser's intermediate token
stream): this font's glyphs are hand-designed so the *assembled glyph path*
(``getType2CharString(gid).getPath()`` -> ``GeneralPath``) is produced only by
correctly resolving **local** (``callsubr``) and **global** (``callgsubr``)
subroutines through the CFF *bias*. The relevant drawing operators
(``rmoveto`` / ``rlineto`` / ``rrcurveto`` / ``endchar``) live *inside* the
subroutines, never inline in the glyph charstring — so a wrong bias or broken
subr-nesting resolution yields a wrong (or empty) outline, which the path
fingerprint catches.

CFF bias (Adobe Technote #5176 §16, "Local/Global Subrs INDEXes"):

* charstring type 2 biases the subr number by 107 when the INDEX has fewer
  than 1240 entries, 1131 for < 33900, else 32768.

To force a non-trivial bias the local /Subrs INDEX is padded to **>= 1240**
entries (so the bias is **1131**, not 107) and the global subrs INDEX is kept
small (bias **107**). A glyph that draws via ``callsubr`` therefore exercises
the 1131-bias path and a glyph that draws via ``callgsubr`` exercises the
107-bias path; a third glyph *nests* (``callsubr`` -> ``callgsubr``) so the
recursive resolution is pinned too.

Both engines parse the *same* CFF bytes; any divergence in the assembled path
is a real subr-resolution / bias bug, not a layout artifact. The bytes are
produced by fontTools' ``CFFFontSet.compile`` (MIT) and are fully
deterministic; re-running this module regenerates them byte-for-byte.

Run from the repo root::

    .venv/bin/python tests/fixtures/fontbox/cff/make_subr_path_fixture.py
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


# Pad the local /Subrs INDEX past 1240 so its bias is 1131 (not 107). The
# "real" drawing subrs occupy fixed indexes; the rest are inert ``return``
# stubs whose only purpose is to push the count over the 1240 threshold.
_LOCAL_COUNT = 1300  # >= 1240 -> bias 1131
_LOCAL_BIAS = 1131

# A few global subrs (bias 107). The glyph charstrings reference these via
# callgsubr; the local subrs reference them too (nested resolution).
_GLOBAL_BIAS = 107


def _local_subrs() -> SubrsIndex:
    subrs = SubrsIndex()
    # index 0: draw a box body relative to the current point and return.
    # rlineto pairs trace a 100x100 box; the caller has already done rmoveto.
    subrs.append(
        T2CharString(program=[100, 0, "rlineto", 0, 100, "rlineto",
                              -100, 0, "rlineto", "return"])
    )
    # index 1: a curve fragment + return.
    subrs.append(
        T2CharString(program=[0, 50, 50, 0, 50, -50, "rrcurveto", "return"])
    )
    # index 2: nested -- call global subr 0 (which draws), then return.
    # global subr 0 sits at gsubr index 0 -> biased number 0 - 107 = -107.
    subrs.append(
        T2CharString(program=[-107, "callgsubr", "return"])
    )
    # Pad with inert return-only subrs up to _LOCAL_COUNT.
    while len(subrs) < _LOCAL_COUNT:
        subrs.append(T2CharString(program=["return"]))
    return subrs


def _global_subrs() -> GlobalSubrsIndex:
    gsubrs = GlobalSubrsIndex()
    # gsubr index 0: draw a small box and return (called both directly by a
    # glyph and indirectly via local subr 2).
    gsubrs.append(
        T2CharString(program=[40, 0, "rlineto", 0, 40, "rlineto",
                              -40, 0, "rlineto", "return"])
    )
    # gsubr index 1: a single line + return.
    gsubrs.append(
        T2CharString(program=[0, 60, "rlineto", "return"])
    )
    return gsubrs


# One program per glyph. The drawing operators live in the subrs; the glyph
# only positions the pen and calls subrs. Subr numbers are biased:
#   local:  index i -> i - 1131
#   global: index j -> j - 107
_GLYPHS_DRAW = {
    ".notdef": [0, "endchar"],
    # Draws via LOCAL subr 0 (box). biased number 0 - 1131 = -1131.
    "Aloc": [10, 100, 200, "rmoveto", -1131, "callsubr", "endchar"],
    # Draws via GLOBAL subr 0 (box). biased number 0 - 107 = -107.
    "Bglob": [20, 50, 50, "rmoveto", -107, "callgsubr", "endchar"],
    # NESTED: local subr 2 -> callgsubr 0. biased local 2 - 1131 = -1129.
    "Cnest": [30, 300, 100, "rmoveto", -1129, "callsubr", "endchar"],
    # Mixed in one glyph: a curve via LOCAL subr 1, then a line via GLOBAL
    # subr 1, exercising both INDEX biases in a single assembled path.
    "Dmix": [
        40, 10, 10, "rmoveto",
        -1130, "callsubr",   # local 1 - 1131
        -106, "callgsubr",   # global 1 - 107
        "endchar",
    ],
}


def build_fixture() -> bytes:
    cff = CFFFontSet()
    cff.major, cff.minor = 1, 0
    cff.hdrSize = 4
    cff.offSize = 2
    cff.fontNames = ["SynthSubrPath"]
    cff.strings = IndexedStrings()
    cff.GlobalSubrs = _global_subrs()

    top = TopDict(strings=cff.strings)
    top.cff = cff
    top.FontMatrix = [0.001, 0, 0, 0.001, 0, 0]
    top.GlobalSubrs = cff.GlobalSubrs

    priv = PrivateDict()
    priv.defaultWidthX = 0
    priv.nominalWidthX = 0
    priv.Subrs = _local_subrs()
    top.Private = priv

    names = list(_GLYPHS_DRAW.keys())
    char_strings = CharStrings(None, None, cff.GlobalSubrs, priv, None, None)
    for name, program in _GLYPHS_DRAW.items():
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
    (_HERE / "subr_path.cff").write_bytes(build_fixture())


if __name__ == "__main__":
    main()
