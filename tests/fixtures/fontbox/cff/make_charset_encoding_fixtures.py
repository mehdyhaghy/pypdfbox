"""Deterministic generator for synthetic name-keyed CFF fixtures that carry
a **custom charset AND a custom embedded /Encoding** in the same font.

The sibling generators isolate the two surfaces:

* ``make_charset_fixtures.py`` builds custom-charset fonts that all keep
  the *default* (StandardEncoding) /Encoding.
* ``make_encoding_fixtures.py`` builds custom-/Encoding fonts (the two
  *predefined* IDs Standard / Expert) whose charset stays standard.

Neither exercises the cross-product: a non-CID CFF whose charset maps
GIDs to *custom* SIDs (>= 391, names in the local STRING INDEX) **and**
whose /Encoding is an *embedded* table mapping codes to those same
custom glyphs. That cross-product is the surface where the
charset<->encoding<->name-to-GID resolution all has to agree:

* ``custom_charset_fmt0_enc.cff`` — a sparse code->glyph assignment that
  fontTools compiles as an embedded **Format0** encoding (flat
  ``(code, sid)`` array). Upstream PDFBox surfaces this as
  ``CFFParser$Format0Encoding``.
* ``custom_charset_fmt1_enc.cff`` — a *contiguous* code->glyph run that
  fontTools compiles as the more compact embedded **Format1** encoding
  (range table). Upstream PDFBox surfaces this as
  ``CFFParser$Format1Encoding``. fontTools decompiles *both* formats
  into an identical 256-name list and discards the on-disk format byte,
  so the only way to recover the Format0-vs-Format1 class identity is to
  re-read the format byte at the raw Encoding offset — the divergence
  this fixture pins down.

Both round-trip identically through Apache PDFBox 3.0.7's fontbox
``CFFParser`` and pypdfbox's fontTools-backed parser. The bytes are
produced by fontTools' ``CFFFontSet.compile`` (MIT-licensed); re-running
this module regenerates the bytes byte-for-byte.

Run from the repo root::

    .venv/bin/python tests/fixtures/fontbox/cff/make_charset_encoding_fixtures.py
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
    glyph_names: list[str],
    encoding_assign: list[tuple[int, str]],
) -> bytes:
    """Compile a name-keyed CFF whose charset is ``glyph_names`` (GID
    order, ``.notdef`` at GID 0) and whose Top DICT ``/Encoding`` is an
    embedded table assigning ``encoding_assign`` ``(code, glyph_name)``
    pairs. fontTools picks the on-disk encoding format (Format0 sparse
    vs Format1 range) from the assignment layout."""
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

    encoding = [".notdef"] * 256
    for code, name in encoding_assign:
        encoding[code] = name
    top.Encoding = encoding

    top_index = TopDictIndex()
    top_index.items = [top]
    cff.topDictIndex = top_index

    buf = BytesIO()
    cff.compile(buf, _StubFont())
    return buf.getvalue()


def build_format0_fixture() -> bytes:
    """Custom charset + sparse embedded encoding -> on-disk Format0."""
    names = [".notdef", "alpha", "beta", "gamma"]
    # Sparse, non-contiguous codes -> fontTools picks Format0.
    encoding = [(65, "alpha"), (66, "beta"), (200, "gamma")]
    return _build("CustChFmt0Enc", names, encoding)


def build_format1_fixture() -> bytes:
    """Custom charset + contiguous embedded encoding -> on-disk Format1."""
    names = [".notdef", *[f"g{i:02d}" for i in range(20)]]
    # A single contiguous code run mapping to contiguous glyphs is the
    # layout fontTools compresses into a Format1 range table.
    encoding = [(50 + i, f"g{i:02d}") for i in range(20)]
    return _build("CustChFmt1Enc", names, encoding)


def main() -> None:
    (_HERE / "custom_charset_fmt0_enc.cff").write_bytes(
        build_format0_fixture()
    )
    (_HERE / "custom_charset_fmt1_enc.cff").write_bytes(
        build_format1_fixture()
    )


if __name__ == "__main__":
    main()
