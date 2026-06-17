"""Live PDFBox differential parity for the TrueType ``post`` table glyph-name
surface (``oracle/probes/PostTableProbe.java``).

The ``post`` table maps glyph ids to PostScript glyph names; it drives
non-symbolic TrueType encoding (code -> name -> gid) and glyph-name-based text
extraction. Three accessors are exercised against Apache PDFBox 3.0.7:

* :meth:`PostScriptTable.get_format_type` — the on-disk post format. Both
  bundled fonts carry format 2.0 (a glyph-name *index* array, where indices
  ``< 258`` reference the built-in Macintosh standard names and indices
  ``>= 258`` reference custom Pascal-string names stored in the table).
* :meth:`PostScriptTable.get_name` — the glyph name for a gid. The high-value
  case is the **format-2.0 custom-name index decode**: indices ``>= 258`` point
  into the table's Pascal-string array, so a gid like 258/1000/6000 must decode
  the right custom name (``ldot``, ``uni0453``, ``uni06B5.medi`` ...), not a
  Mac-standard name. Out-of-range gids return ``None`` (``NULL`` on the probe).
* :meth:`TrueTypeFont.name_to_gid` — the reverse lookup PDFBox performs when
  resolving an /Encoding glyph name to a glyph (PDFBox ``nameToGID``). Covers
  Mac-standard names, custom names beyond index 258, ``uniXXXX`` cmap fallback,
  the PDFBOX-5604 literal ``g<digits>`` form, and the unknown-name -> 0 case.

Fonts used (both verified format 2.0 via fontTools ``font['post'].formatType``):
  * ``LiberationSans-Regular`` — 2620 glyphs; custom names start at gid 258
    (``ldot``), include ``uniXXXX`` forms and ligatures (``S_BE``).
  * ``DejaVuSans`` — 6253 glyphs; richer custom-name array incl. dotted
    suffixes (``uni06B5.medi``, ``uni2A1C.display``).

pypdfbox delegates the font-program byte parse to fontTools but exposes the
FontBox-compatible ``PostScriptTable`` projection and ``name_to_gid``; this test
verifies the glyph-name resolution matches PDFBox exactly. A divergence shows up
as a single differing line.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import TrueTypeFont
from tests.oracle.harness import requires_oracle, run_probe_text

_TTF_DIR = Path(__file__).resolve().parents[4] / "pypdfbox" / "resources" / "ttf"

# Mirror the probe's separator: gids before "--", names after.
_LIBERATION_GIDS = [
    0, 1, 2, 3, 4, 36, 68, 100,
    258, 259, 500, 1000, 2000, 2619,  # custom Pascal-string names (>= 258)
    2620, -1,                          # out of range -> NULL
]
_LIBERATION_NAMES = [
    "A", "a", "space", ".notdef", "zero", "quotesingle",
    "Euro",                  # cmap-resolved name not in post array
    "ldot", "uni0437", "S_BE",  # reverse of custom names beyond index 258
    "nonexistentglyph123",   # unknown -> 0
    "g50",                   # PDFBOX-5604 literal-gid form
]

_DEJAVU_GIDS = [
    0, 3, 4, 36, 68,
    258, 300, 1000, 3000, 6000, 6252,  # custom Pascal-string names
    6253, -5,                          # out of range -> NULL
]
_DEJAVU_NAMES = [
    "A", "a", "space", ".notdef",
    "periodcentered", "bullet",
    "Euro", "uni20AC",       # both resolve via cmap fallback
    "nonexistentXYZ",        # unknown -> 0
]


def _pypdfbox_lines(path: Path, gids: list[int], names: list[str]) -> list[str]:
    """Reproduce the probe's canonical output from pypdfbox.

    Closes the font program in a ``finally`` so the source file handle never
    leaks (Windows would otherwise lock the bundled resource).
    """
    ttf = TrueTypeFont.from_bytes(path.read_bytes())
    try:
        post = ttf.get_post_script()
        assert post is not None
        lines = [
            f"FORMAT\t{_fmt(post.get_format_type())}",
            f"NUMGLYPHS\t{ttf.get_number_of_glyphs()}",
        ]
        for gid in gids:
            name = post.get_name(gid)
            lines.append(f"NAME\t{gid}\t{'NULL' if name is None else name}")
        for name in names:
            lines.append(f"GID\t{name}\t{ttf.name_to_gid(name)}")
        return lines
    finally:
        ttf.close()


def _fmt(value: float) -> str:
    """Render a post format the way the Java probe's ``Float.toString`` does.

    PDFBox stores the 16.16 fixed-point format as a float; ``2.0`` / ``1.0`` /
    ``3.0`` render with a single trailing zero, matching Python's ``str(2.0)``.
    """
    return str(value)


def _probe_args(path: Path, gids: list[int], names: list[str]) -> list[str]:
    return [str(path), *[str(g) for g in gids], "--", *names]


@requires_oracle
@pytest.mark.parametrize(
    ("font", "gids", "names"),
    [
        ("LiberationSans-Regular.ttf", _LIBERATION_GIDS, _LIBERATION_NAMES),
        ("DejaVuSans.ttf", _DEJAVU_GIDS, _DEJAVU_NAMES),
    ],
    ids=["liberation_sans", "dejavu_sans"],
)
def test_post_table_glyph_names_match_pdfbox(
    font: str, gids: list[int], names: list[str]
) -> None:
    path = _TTF_DIR / font
    java = run_probe_text("PostTableProbe", *_probe_args(path, gids, names)).splitlines()
    py = _pypdfbox_lines(path, gids, names)
    assert py == java


@requires_oracle
def test_post_format_is_2_0() -> None:
    """Both bundled fonts must report format 2.0 (the index + custom-name case).

    Anchors the parametrised test: if a font were swapped for a format-3.0
    program the custom-name decode path would never be exercised, so assert the
    format both sides see is 2.0.
    """
    for font in ("LiberationSans-Regular.ttf", "DejaVuSans.ttf"):
        path = _TTF_DIR / font
        java = run_probe_text("PostTableProbe", str(path), "--").splitlines()
        assert java[0] == "FORMAT\t2.0"
        ttf = TrueTypeFont.from_bytes(path.read_bytes())
        try:
            assert ttf.get_post_script().get_format_type() == 2.0  # noqa: PLR2004
        finally:
            ttf.close()
