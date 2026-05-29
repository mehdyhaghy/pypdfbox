"""Deterministic generator for synthetic CFF (Type 1C) fixtures that
exercise the Top/Private DICT operator *defaults* surfaced by Apache
FontBox ``CFFParser`` — ``/FontMatrix``, ``/FontBBox``,
``/CharstringType`` (Top DICT) and ``/defaultWidthX`` /
``/nominalWidthX`` / ``/BlueValues`` / ``/StdHW`` / ``/StdVW`` (Private
DICT).

Per Adobe Technote #5176 Tables 9 & 23 several DICT operators carry an
implicit default applied when the operator is absent. Apache FontBox's
``CFFParser.parseFont`` materialises those defaults into the maps it
later exposes via ``CFFFont.getTopDict()`` and
``CFFType1Font.getPrivateDict()`` — i.e. even when the byte stream
omits ``/FontMatrix``, the resolved Top DICT map carries
``[0.001 0 0 0.001 0 0]``; an omitted ``/defaultWidthX`` comes back as
``0``. ``/BlueValues`` / ``/StdHW`` / ``/StdVW`` have *no* default, so an
omission stays absent (``null`` / ``None``). That default-materialisation
boundary is the differential target.

* ``dict_defaults_absent.cff`` — omits every defaulted operator; the
  resolved maps must come back stamped with the canonical defaults.
* ``dict_defaults_present.cff`` — sets every operator to a non-default
  value (incl. ``/BlueValues`` / ``/StdHW`` / ``/StdVW``); the resolved
  maps must carry the explicit values, never the defaults.

The bytes are produced by fontTools' ``CFFFontSet.compile``
(MIT-licensed); re-running this module regenerates them byte-for-byte.

Run from the repo root::

    .venv/bin/python tests/fixtures/fontbox/cff/make_dict_defaults_fixtures.py
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


def _common(font_name: str) -> tuple[CFFFontSet, TopDict, PrivateDict]:
    cff = CFFFontSet()
    cff.major, cff.minor = 1, 0
    cff.hdrSize = 4
    cff.offSize = 2
    cff.fontNames = [font_name]
    cff.strings = IndexedStrings()
    cff.GlobalSubrs = GlobalSubrsIndex()

    top = TopDict(strings=cff.strings)
    top.cff = cff
    top.GlobalSubrs = cff.GlobalSubrs
    top.Encoding = "StandardEncoding"

    priv = PrivateDict()
    top.Private = priv
    return cff, top, priv


def _finish(cff: CFFFontSet, top: TopDict, priv: PrivateDict) -> bytes:
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


def build_absent_fixture() -> bytes:
    """Omit every defaulted operator. fontTools writes only the operators
    we set, so /FontMatrix, /FontBBox, /CharstringType, /defaultWidthX,
    /nominalWidthX, /BlueValues, /StdHW, /StdVW are all physically absent
    in the resulting bytes — the parser must materialise the defaults."""
    cff, top, _priv = _common("DictDefaultsAbsent")
    return _finish(cff, top, _priv)


def build_present_fixture() -> bytes:
    """Set every operator to a non-default value so the resolved maps must
    carry the explicit value, never the parser-stamped default."""
    cff, top, priv = _common("DictDefaultsPresent")
    top.FontMatrix = [0.0005, 0, 0, 0.0005, 0, 0]
    top.FontBBox = [-50, -200, 1000, 900]
    top.CharstringType = 2
    priv.defaultWidthX = 480
    priv.nominalWidthX = 120
    priv.BlueValues = [-20, 0, 700, 720]
    priv.StdHW = 80
    priv.StdVW = 95
    return _finish(cff, top, priv)


def main() -> None:
    (_HERE / "dict_defaults_absent.cff").write_bytes(build_absent_fixture())
    (_HERE / "dict_defaults_present.cff").write_bytes(build_present_fixture())


if __name__ == "__main__":
    main()
