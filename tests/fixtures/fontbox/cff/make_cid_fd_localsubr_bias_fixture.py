"""Deterministic generator for a CID-keyed CFF (CIDFontType0C) whose two
font-dicts carry local /Subrs INDEXes of **different sizes**, so each FD has a
*different subr bias* (Adobe Technote #5176 §16: 107 for <1240 entries, 1131 for
1240..32699).

This is an *original* fixture (not ported from Apache PDFBox); it exists to pin
the per-FD local-subroutine resolution surface more sharply than
``cid_multifd_subr.cff`` does. That sibling fixture gives each FD a single-entry
/Subrs INDEX, so both FDs share bias 107 and a ``callsubr`` operand of -107
reaches subr 0 in either FD. A wrong-FD lookup would still land on *a* valid
subr. This fixture instead makes the two biases disagree:

* ``FD0`` — a 1-entry local /Subrs INDEX, bias **107**. Subr 0 draws a
  horizontal ``rlineto 25 0``. CIDs 0,1 select FD0 and call ``callsubr`` with
  operand ``-107`` (= subr index 0 under bias 107).
* ``FD1`` — a 1300-entry local /Subrs INDEX, bias **1131**. Subrs 0..1298 are
  no-op ``return``; subr 1299 draws a vertical ``rlineto 0 40``. CIDs 2,3 select
  FD1 and call ``callsubr`` with operand ``168`` (= 1299 - 1131).

So the *same* ``callsubr`` opcode resolves to a horizontal line under FD0 and a
vertical line under FD1, and the FD1 case only produces a drawing at all if the
interpreter computed the **1131 bias from FD1's own large /Subrs count** and
indexed FD1's INDEX (not FD0's, and not a hard-coded 107 bias). A bug that used
the wrong FD's subr index, or a fixed bias, yields an empty outline for CIDs
2,3 (the no-op ``return`` subrs) — a sharp, unambiguous divergence.

fontTools' ``CFFFontSet.compile`` (MIT) lays out the bytes deterministically;
re-running regenerates byte-for-byte. Run from the repo root::

    .venv/bin/python tests/fixtures/fontbox/cff/make_cid_fd_localsubr_bias_fixture.py
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fontTools.cffLib import (
    CFFFontSet,
    CharStrings,
    FDArrayIndex,
    FDSelect,
    FontDict,
    GlobalSubrsIndex,
    IndexedStrings,
    PrivateDict,
    SubrsIndex,
    TopDict,
    TopDictIndex,
)
from fontTools.misc.psCharStrings import T2CharString

_HERE = Path(__file__).resolve().parent

# FD1 carries this many local subrs so its bias is 1131. Adobe Technote #5176
# §16: count < 1240 -> bias 107; 1240 <= count < 33900 -> bias 1131. 1300 is
# comfortably inside the 1131 band.
_FD1_SUBR_COUNT = 1300
_FD1_DRAW_SUBR = _FD1_SUBR_COUNT - 1  # the one subr that actually draws
_FD1_BIAS = 1131  # 1240..32699 entries -> bias 1131
_FD0_BIAS = 107  # < 1240 entries -> bias 107


class _StubFont:
    """Minimal stand-in for the ``otFont`` argument ``CFFFontSet.compile``
    reads two flags off."""

    recalcBBoxes = False
    recalcTimestamp = False


def build() -> bytes:
    """2-FD CID CFF whose FDs have different-size local /Subrs (107 vs 1131)."""
    cff = CFFFontSet()
    cff.major, cff.minor = 1, 0
    cff.hdrSize = 4
    cff.offSize = 2
    cff.fontNames = ["SynthCIDBias"]
    cff.strings = IndexedStrings()
    cff.GlobalSubrs = GlobalSubrsIndex()

    top = TopDict(strings=cff.strings)
    top.cff = cff
    top.ROS = ("Adobe", "Identity", 0)
    top.CIDCount = 4
    top.FontMatrix = [0.001, 0, 0, 0.001, 0, 0]
    top.GlobalSubrs = cff.GlobalSubrs

    privs: list[PrivateDict] = []
    fd_array = FDArrayIndex()

    # FD0: single-entry local /Subrs -> bias 107. Subr 0 draws horizontal.
    p0 = PrivateDict()
    p0.defaultWidthX = 100
    p0.nominalWidthX = 50
    s0 = SubrsIndex()
    s0.append(T2CharString(program=[25, 0, "rlineto", "return"]))
    p0.Subrs = s0
    privs.append(p0)
    fd0 = FontDict(strings=cff.strings)
    fd0.Private = p0
    fd0.FontName = "FD-Small-Bias107"
    fd_array.append(fd0)

    # FD1: 1300-entry local /Subrs -> bias 1131. Last subr draws vertical.
    p1 = PrivateDict()
    p1.defaultWidthX = 200
    p1.nominalWidthX = 80
    s1 = SubrsIndex()
    for _ in range(_FD1_SUBR_COUNT - 1):
        s1.append(T2CharString(program=["return"]))
    s1.append(T2CharString(program=[0, 40, "rlineto", "return"]))
    p1.Subrs = s1
    privs.append(p1)
    fd1 = FontDict(strings=cff.strings)
    fd1.Private = p1
    fd1.FontName = "FD-Large-Bias1131"
    fd_array.append(fd1)

    top.FDArray = fd_array

    fd_select_map = [0, 0, 1, 1]
    fdselect = FDSelect()
    for s in fd_select_map:
        fdselect.append(s)
    top.FDSelect = fdselect

    fd0_operand = 0 - _FD0_BIAS  # subr 0 under bias 107
    fd1_operand = _FD1_DRAW_SUBR - _FD1_BIAS  # last subr under bias 1131

    names = [".notdef"] + [f"cid{g:05d}" for g in range(1, 4)]
    # width-operand = actual_width - nominalWidthX(selected FD)
    glyph_programs = [
        [120 - 50, 10, 5, "rmoveto", fd0_operand, "callsubr", "endchar"],
        [160 - 50, 20, 10, "rmoveto", fd0_operand, "callsubr", "endchar"],
        [260 - 80, 30, 15, "rmoveto", fd1_operand, "callsubr", "endchar"],
        [300 - 80, 40, 20, "rmoveto", fd1_operand, "callsubr", "endchar"],
    ]
    char_strings = CharStrings(None, None, cff.GlobalSubrs, None, fdselect, fd_array)
    for gid, program in enumerate(glyph_programs):
        cs = T2CharString(program=program)
        cs.private = privs[fd_select_map[gid]]
        cs.globalSubrs = cff.GlobalSubrs
        char_strings.charStrings[names[gid]] = cs
    top.CharStrings = char_strings
    top.charset = names

    top_index = TopDictIndex()
    top_index.items = [top]
    cff.topDictIndex = top_index

    buf = BytesIO()
    cff.compile(buf, _StubFont())
    return buf.getvalue()


def main() -> None:
    (_HERE / "cid_multifd_localsubr_bias.cff").write_bytes(build())


if __name__ == "__main__":
    main()
