"""Deterministic generator for synthetic CFF (Type 1C) fixtures whose Top DICT
declares a **predefined /Encoding** — Standard (ID 0) or Expert (ID 1).

These fixtures exist because PDFBox's own test corpus has no small Type1C
program with a *predefined* encoding (the embedded /Type1C subsets PDFBox
ships all carry an embedded Format0/Format1 encoding). A predefined
encoding is the high-value differential case for the CFF parser: the
Top DICT carries the literal integer 0 or 1 (not an offset), and the
parser must resolve to the StandardEncoding / ExpertEncoding singleton
rather than mis-reading the integer as an offset into a Format0 table.

* ``std_enc.cff`` — Top DICT ``/Encoding 0`` (StandardEncoding).
* ``expert_enc.cff`` — Top DICT ``/Encoding 1`` (ExpertEncoding).

Both files round-trip identically through Apache PDFBox 3.0.7's fontbox
``CFFParser`` and pypdfbox's fontTools-backed parser. The bytes are
produced by fontTools' ``CFFFontSet.compile`` (MIT-licensed); re-running
this module regenerates the bytes byte-for-byte.

Run from the repo root::

    .venv/bin/python tests/fixtures/fontbox/cff/make_encoding_fixtures.py
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


def _build(font_name: str, encoding: str, glyph_names: list[str]) -> bytes:
    """Compile a name-keyed CFF whose Top DICT ``/Encoding`` is ``encoding``
    (either ``"StandardEncoding"`` or ``"ExpertEncoding"`` — fontTools
    encodes these as the predefined IDs 0 / 1 in the Top DICT)."""
    cff = CFFFontSet()
    cff.major, cff.minor = 1, 0
    cff.hdrSize = 4
    cff.offSize = 2
    cff.fontNames = [font_name]
    cff.strings = IndexedStrings()
    cff.GlobalSubrs = GlobalSubrsIndex()

    top = TopDict(strings=cff.strings)
    top.cff = cff
    top.FontMatrix = [0.001, 0, 0, 0.001, 0, 0]
    top.GlobalSubrs = cff.GlobalSubrs
    top.Encoding = encoding

    priv = PrivateDict()
    priv.defaultWidthX = 500
    priv.nominalWidthX = 0
    top.Private = priv

    char_strings = CharStrings(None, None, cff.GlobalSubrs, None, None, None)
    for name in glyph_names:
        cs = T2CharString(program=[100, "endchar"])
        cs.private = priv
        cs.globalSubrs = cff.GlobalSubrs
        char_strings.charStrings[name] = cs
    top.CharStrings = char_strings
    top.charset = glyph_names

    top_index = TopDictIndex()
    top_index.items = [top]
    cff.topDictIndex = top_index

    buf = BytesIO()
    cff.compile(buf, _StubFont())
    return buf.getvalue()


def build_standard_encoding_fixture() -> bytes:
    return _build("StdEncFont", "StandardEncoding", [".notdef", "A", "B", "space"])


def build_expert_encoding_fixture() -> bytes:
    return _build(
        "ExpEncFont",
        "ExpertEncoding",
        [".notdef", "exclamsmall", "Hungarumlautsmall", "space"],
    )


def main() -> None:
    (_HERE / "std_enc.cff").write_bytes(build_standard_encoding_fixture())
    (_HERE / "expert_enc.cff").write_bytes(build_expert_encoding_fixture())


if __name__ == "__main__":
    main()
