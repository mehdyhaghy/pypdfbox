"""Deterministic generator for synthetic CFF fixtures that exercise every
CFF **/charset** on-disk encoding plus a predefined charset.

PDFBox's bundled test corpus only carries Format0 name-keyed and Format1
CID-keyed charsets; the high-value differential cases for the CFF charset
parser are the ones the corpus *lacks*:

* ``charset_fmt1_name.cff`` -- name-keyed font whose glyph SIDs are a
  contiguous run (custom STRING INDEX names appended in order land on
  consecutive SIDs >= 391), so fontTools emits a Format1 range table
  (1-byte nLeft) rather than a Format0 SID array.
* ``charset_fmt2_name.cff`` -- name-keyed font with > 256 contiguous SIDs
  in a single range, forcing fontTools to widen the range table to
  Format2 (2-byte nLeft). This is the only encoding that needs the
  2-byte nLeft read path.
* ``charset_iso_adobe.cff`` -- name-keyed font whose charset is an exact
  prefix of the ISOAdobe predefined charset, so fontTools writes the
  predefined charset id 0 in the Top DICT (no embedded charset table).
  This is the predefined-vs-embedded dichotomy for charsets, mirroring
  the predefined-/Encoding fixtures in ``make_encoding_fixtures.py``.

All three round-trip identically through Apache PDFBox 3.0.7's fontbox
``CFFParser`` and pypdfbox's fontTools-backed parser. The bytes are
produced by fontTools' ``CFFFontSet.compile`` (MIT-licensed); re-running
this module regenerates the bytes byte-for-byte.

Run from the repo root::

    .venv/bin/python tests/fixtures/fontbox/cff/make_charset_fixtures.py
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
    cffISOAdobeStrings,
)
from fontTools.misc.psCharStrings import T2CharString

_HERE = Path(__file__).resolve().parent


class _StubFont:
    """Minimal stand-in for the ``otFont`` argument ``CFFFontSet.compile``
    reads two flags off — fontTools never touches anything else when
    compiling a bare CFF FontSet."""

    recalcBBoxes = False
    recalcTimestamp = False


def _build(font_name: str, glyph_names: list[str]) -> bytes:
    """Compile a name-keyed CFF whose charset is ``glyph_names`` (GID order,
    ``.notdef`` at GID 0). fontTools chooses the charset encoding
    (Format0 / Format1 / Format2 / predefined) from the SID layout."""
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


def build_format1_name_fixture() -> bytes:
    """Name-keyed: a contiguous run of custom glyph names -> Format1 range."""
    names = [".notdef", *[f"g{i:03d}" for i in range(8)]]
    return _build("CharsetFmt1", names)


def build_format2_name_fixture() -> bytes:
    """Name-keyed: > 256 contiguous custom SIDs -> Format2 (2-byte nLeft)."""
    names = [".notdef", *[f"h{i:04d}" for i in range(400)]]
    return _build("CharsetFmt2", names)


def build_iso_adobe_fixture() -> bytes:
    """Name-keyed: charset is a prefix of ISOAdobe -> predefined id 0."""
    names = [".notdef", *list(cffISOAdobeStrings[1:30])]
    return _build("CharsetISOAdobe", names)


def main() -> None:
    (_HERE / "charset_fmt1_name.cff").write_bytes(build_format1_name_fixture())
    (_HERE / "charset_fmt2_name.cff").write_bytes(build_format2_name_fixture())
    (_HERE / "charset_iso_adobe.cff").write_bytes(build_iso_adobe_fixture())


if __name__ == "__main__":
    main()
