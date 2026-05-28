"""Deterministic generator for synthetic CFF (Type 1C) fixtures whose Top
DICT carries metadata-string operators (``/version``, ``/Notice``,
``/Copyright``, ``/FullName``, ``/FamilyName``, ``/Weight``).

These fixtures exist because PDFBox's own test corpus has no small
Type1C program that *deliberately* mixes a Standard-Strings-resolved
metadata operand with String-INDEX-resolved ones. The mix is the
high-value differential case for the CFF Top DICT parser: each metadata
operator carries a SID, and SIDs in 0..390 must resolve to the
font-independent Standard Strings table (Adobe Technote #5176 Appendix
A), while SIDs >= 391 index into the per-font STRING INDEX.

* ``metadata_strindex.cff`` — every metadata string lives in the STRING
  INDEX (SIDs 391..395) except ``/Weight = "Bold"``, which resolves via
  the predefined Standard String SID 384.
* ``metadata_predef.cff`` — ``/version = "001.000"`` (SID 379, predefined)
  and ``/Weight = "Regular"`` (SID 388, predefined); the remaining three
  string fields go through the STRING INDEX.

Both files round-trip identically through Apache PDFBox 3.0.7's fontbox
``CFFParser`` and pypdfbox's fontTools-backed parser. The bytes are
produced by fontTools' ``CFFFontSet.compile`` (MIT-licensed); re-running
this module regenerates the bytes byte-for-byte.

Run from the repo root::

    .venv/bin/python tests/fixtures/fontbox/cff/make_metadata_fixtures.py
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


def _build(
    font_name: str,
    *,
    version: str,
    notice: str,
    copyright_: str,
    full_name: str,
    family_name: str,
    weight: str,
) -> bytes:
    """Compile a name-keyed CFF whose Top DICT carries the six metadata-
    string operators. fontTools chooses the predefined-SID encoding for
    any value matching the Standard Strings table, and falls through to
    the STRING INDEX for anything else — so picking ``"Bold"`` /
    ``"Regular"`` exercises the predefined path while a free-form
    ``"FullName"`` exercises the STRING INDEX path."""
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
    top.Encoding = "StandardEncoding"

    # Top DICT metadata-string operators (Adobe Technote #5176 Table 9).
    top.version = version
    top.Notice = notice
    top.Copyright = copyright_
    top.FullName = full_name
    top.FamilyName = family_name
    top.Weight = weight

    priv = PrivateDict()
    priv.defaultWidthX = 500
    priv.nominalWidthX = 0
    top.Private = priv

    glyph_names = [".notdef", "A", "B", "space"]
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


def build_string_index_fixture() -> bytes:
    """Most metadata strings go through the STRING INDEX (SIDs 391..395);
    ``/Weight = "Bold"`` (SID 384) is the one predefined-SID entry."""
    return _build(
        "MetaStrIndexFont",
        version="1.234",
        notice="Copyright (c) Pypdfbox Test 2026",
        copyright_="Public Domain - Pypdfbox Probe",
        full_name="Meta StrIndex Font Regular",
        family_name="Meta StrIndex",
        weight="Bold",
    )


def build_predefined_fixture() -> bytes:
    """``/version`` and ``/Weight`` both resolve via predefined SIDs
    (``"001.000"`` = SID 379, ``"Regular"`` = SID 388); the rest live in
    the STRING INDEX. This is the differential case that catches a
    parser that always reads SIDs as STRING-INDEX offsets — a wrong
    resolution here would surface as garbage names (or the wrong
    String-INDEX entry) rather than the canonical Adobe values."""
    return _build(
        "MetaPredefFont",
        version="001.000",
        notice="Pypdfbox predefined-SID coverage",
        copyright_="(c) Pypdfbox Test 2026",
        full_name="Meta Predef Font",
        family_name="Meta Predef",
        weight="Regular",
    )


def main() -> None:
    (_HERE / "metadata_strindex.cff").write_bytes(build_string_index_fixture())
    (_HERE / "metadata_predef.cff").write_bytes(build_predefined_fixture())


if __name__ == "__main__":
    main()
