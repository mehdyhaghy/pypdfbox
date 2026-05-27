"""Deterministic generator for the synthetic CID-keyed CFF (CIDFontType0C)
fixtures used by the FDSelect / FDArray differential oracle test.

The two ``.cff`` files this writes are *original* test fixtures (not ported
from Apache PDFBox); they exist because PDFBox's own test corpus has no small
**multi-FD** CID-keyed CFF where the /FDSelect actually discriminates between
several font-dicts (the real ``PDFBOX-3062-005717-p1.pdf`` subset is single-FD).
A discriminating multi-FD font is exactly the high-value case the oracle needs:

* ``cid_multifd_subr.cff`` — 2 font-dicts, FDSelect ``[0,0,1,1]``, each FD with
  its **own local /Subrs** (FD0's subr draws a horizontal line, FD1's a
  vertical one). A glyph's ``callsubr`` therefore resolves to a *different*
  subroutine depending on which FD its CID selects — so the glyph outline
  proves the local-subr index is resolved in the right font-dict.
* ``cid_multifd_3fd.cff`` — 3 font-dicts, FDSelect ``[0,0,0,1,1,2,2,2]``, no
  local subrs, distinct per-FD ``defaultWidthX`` / ``nominalWidthX`` so the
  per-CID width path proves the correct FD's Private DICT is read.

Both files round-trip identically through Apache PDFBox 3.0.7's fontbox
``CFFParser`` (verified by the ``CffCidFdProbe`` oracle) and pypdfbox's
fontTools-backed parser. The CFF byte layout is produced by fontTools'
``CFFFontSet.compile`` (MIT-licensed); re-running this module regenerates the
bytes byte-for-byte (no timestamps / nondeterminism).

Run from the repo root::

    .venv/bin/python tests/fixtures/fontbox/cff/make_cid_fd_fixtures.py
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


class _StubFont:
    """Minimal stand-in for the ``otFont`` argument ``CFFFontSet.compile``
    reads two flags off — fontTools never touches anything else when
    compiling a bare CFF FontSet."""

    recalcBBoxes = False
    recalcTimestamp = False


def _make_subrs(program: list[object]) -> SubrsIndex:
    si = SubrsIndex()
    si.append(T2CharString(program=program))
    return si


def _build(
    *,
    cid_count: int,
    fd_widths: list[tuple[int, int]],
    fd_subrs: list[list[object] | None],
    fd_names: list[str],
    fd_select: list[int],
    glyph_widths: list[int],
    glyph_programs: list[list[object]],
) -> bytes:
    """Compile a CID-keyed CFF from explicit per-FD + per-glyph parts."""
    cff = CFFFontSet()
    cff.major, cff.minor = 1, 0
    cff.hdrSize = 4
    cff.offSize = 2
    cff.fontNames = ["SynthCID"]
    cff.strings = IndexedStrings()
    cff.GlobalSubrs = GlobalSubrsIndex()

    top = TopDict(strings=cff.strings)
    top.cff = cff
    top.ROS = ("Adobe", "Identity", 0)
    top.CIDCount = cid_count
    top.FontMatrix = [0.001, 0, 0, 0.001, 0, 0]
    top.GlobalSubrs = cff.GlobalSubrs

    privs: list[PrivateDict] = []
    fd_array = FDArrayIndex()
    for i, (default_w, nominal_w) in enumerate(fd_widths):
        priv = PrivateDict()
        priv.defaultWidthX = default_w
        priv.nominalWidthX = nominal_w
        subr_prog = fd_subrs[i]
        if subr_prog is not None:
            priv.Subrs = _make_subrs(subr_prog)
        privs.append(priv)
        font_dict = FontDict(strings=cff.strings)
        font_dict.Private = priv
        font_dict.FontName = fd_names[i]
        fd_array.append(font_dict)
    top.FDArray = fd_array

    fdselect = FDSelect()
    for s in fd_select:
        fdselect.append(s)
    top.FDSelect = fdselect

    names = [".notdef"] + [f"cid{g:05d}" for g in range(1, cid_count)]
    char_strings = CharStrings(None, None, cff.GlobalSubrs, None, fdselect, fd_array)
    for gid, program in enumerate(glyph_programs):
        priv = privs[fd_select[gid]]
        cs = T2CharString(program=program)
        cs.private = priv
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


def build_subr_fixture() -> bytes:
    """2-FD CID CFF; each FD has its own local subr (callsubr discriminates)."""
    # FD0 subr 0: rlineto 20 0 (horizontal); FD1 subr 0: rlineto 0 30 (vertical).
    # callsubr index 0 with single-subr bias 107 -> operand -107.
    return _build(
        cid_count=4,
        fd_widths=[(100, 50), (200, 80)],
        fd_subrs=[[20, 0, "rlineto", "return"], [0, 30, "rlineto", "return"]],
        fd_names=["FD-Zero", "FD-One"],
        fd_select=[0, 0, 1, 1],
        glyph_widths=[120, 160, 260, 300],
        glyph_programs=[
            # width-operand = actual_width - nominalWidthX(of selected FD)
            [120 - 50, 10, 5, "rmoveto", -107, "callsubr", "endchar"],
            [160 - 50, 20, 10, "rmoveto", -107, "callsubr", "endchar"],
            [260 - 80, 30, 15, "rmoveto", -107, "callsubr", "endchar"],
            [300 - 80, 40, 20, "rmoveto", -107, "callsubr", "endchar"],
        ],
    )


def build_three_fd_fixture() -> bytes:
    """3-FD CID CFF; distinct per-FD width defaults, no local subrs."""
    return _build(
        cid_count=8,
        fd_widths=[(100, 50), (200, 80), (333, 111)],
        fd_subrs=[None, None, None],
        fd_names=["FD-0", "FD-1", "FD-2"],
        fd_select=[0, 0, 0, 1, 1, 2, 2, 2],
        glyph_widths=[120, 160, 140, 260, 300, 400, 420, 440],
        glyph_programs=[
            [120 - 50, 10, 5, "rmoveto", 20, 0, "rlineto", 0, 15, "rlineto", "endchar"],
            [160 - 50, 20, 10, "rmoveto", 20, 0, "rlineto", 0, 15, "rlineto", "endchar"],
            [140 - 50, 30, 15, "rmoveto", 20, 0, "rlineto", 0, 15, "rlineto", "endchar"],
            [260 - 80, 40, 20, "rmoveto", 20, 0, "rlineto", 0, 15, "rlineto", "endchar"],
            [300 - 80, 50, 25, "rmoveto", 20, 0, "rlineto", 0, 15, "rlineto", "endchar"],
            [400 - 111, 60, 30, "rmoveto", 20, 0, "rlineto", 0, 15, "rlineto", "endchar"],
            [420 - 111, 70, 35, "rmoveto", 20, 0, "rlineto", 0, 15, "rlineto", "endchar"],
            [440 - 111, 80, 40, "rmoveto", 20, 0, "rlineto", 0, 15, "rlineto", "endchar"],
        ],
    )


def main() -> None:
    (_HERE / "cid_multifd_subr.cff").write_bytes(build_subr_fixture())
    (_HERE / "cid_multifd_3fd.cff").write_bytes(build_three_fd_fixture())


if __name__ == "__main__":
    main()
