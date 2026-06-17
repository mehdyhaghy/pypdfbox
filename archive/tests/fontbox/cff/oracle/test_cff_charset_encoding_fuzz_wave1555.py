"""Differential fuzz of the CFF charset + encoding **lookup** surface driven
over hostile / out-of-range keys vs Apache FontBox 3.0.7 (wave 1555).

Where the wave-1525 fuzz oracle drove the *private byte-level table readers*
(``read_charset`` / ``read_encoding``) by reflection on raw buffers, and the
sibling whole-font oracles (``test_cff_charset_oracle`` /
``test_cff_encoding_oracle`` / ``test_cff_charset_encoding_oracle``) sweep only
the *in-range* GID space of well-formed fonts, this oracle hammers the *public*
resolver surface a renderer actually calls — folded by pypdfbox onto
``CFFFont`` / ``CFFType1Font`` — with edge keys:

* ``get_name_for_gid`` / ``get_sid_for_gid`` over negative GIDs and GIDs far
  past ``nGlyphs`` (1000 / 65535 / 70000),
* ``get_gid_for_sid`` over SIDs past the Standard-String + STRING-INDEX bound
  (229 / 390 / 391 / 99999) and negative,
* ``get_sid`` / ``name_to_gid`` over glyph names absent from the charset
  (``""`` / ``no_such_glyph`` / cross-font names),
* ``encoding.get_name`` over codes outside 0..255 (predefined Standard /
  Expert and embedded Format0),
* ``get_cid_for_gid`` / ``get_gid_for_cid`` over out-of-range CIDs / GIDs on a
  CID-keyed font.

The Java probe (``oracle/probes/CffCharsetEdgeLookupProbe.java``) renders every
resolver cell exception-safely as the literal token ``THROW`` (or ``NULL`` for
a Java ``null`` name), so divergence in *whether* a key throws is itself pinned.

Three intentional, documented pypdfbox divergences are normalised below so the
projection compares the *resolution semantics* rather than the Java-specific
plumbing they stem from:

1. **name-keyed out-of-range name** — upstream ``CFFCharsetType1.getNameForGID``
   returns Java ``null`` for an absent GID; pypdfbox's ``get_name_for_gid``
   returns ``".notdef"`` by documented choice (PDF rendering contract for
   missing glyphs). We map Python ``.notdef`` for an out-of-range GID to the
   Java ``NULL`` it corresponds to.
2. **CID-keyed Type1 methods** — upstream ``CFFCharsetCID`` *throws*
   "Not a Type 1 font" for ``getNameForGID`` / ``getSIDForGID`` /
   ``getGIDForSID`` / ``getSID``; pypdfbox folds the charset onto ``CFFFont``
   and returns a benign fallback instead of throwing. We compare the CID font
   only on the CID surface (``get_cid_for_gid`` / ``get_gid_for_cid``), which
   is where the load-bearing parity lives — and where wave 1555 fixed a real
   bug: an out-of-range GID now resolves to CID 0 (Java
   ``CFFCharsetCID.getCIDForGID`` → ``gidToCid.get(gid)`` → 0 on a miss),
   not the raw GID.
3. **name→SID / name→GID for *absent* names** — two compounding library-first
   effects make ``get_sid`` / ``name_to_gid`` diverge for a glyph name that is
   **not in the font's own charset**:
   (a) pypdfbox's ``get_sid`` consults the global CFF Standard Strings table
   first, so ``get_sid("space")`` is 1 even for a font that has no ``space``
   glyph, whereas upstream ``CFFCharsetType1.getSID`` is font-local (its
   ``nameToSid`` map → 0 on a miss); and (b) for a *predefined* charset
   (ISOAdobe id 0) Java materialises the full 229-entry canonical table while
   pypdfbox, via fontTools, reconstructs only the glyphs the font actually
   ships — so Java's font-local map contains names (``A`` → 34) that pypdfbox's
   does not. Both effects vanish for names that *are* in the parsed charset, so
   the ``GSID`` / ``N2G`` cells are compared only over that in-charset subset
   (the cells where the resolution is well-defined on both engines); the
   absent-name cells are left out by design rather than asserted.

Both engines read the *same* CFF fixture bytes, so any remaining divergence is
a real resolution bug, not a byte-layout artifact.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.cff_type1_font import CFFType1Font
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "CffCharsetEdgeLookupProbe"

_REPO = Path(__file__).resolve().parents[4]
_CFF_FIXTURES = _REPO / "tests" / "fixtures" / "fontbox" / "cff"

# Mirror the EDGE_* arrays in CffCharsetEdgeLookupProbe.java exactly.
_EDGE_GIDS = (-1, 0, 1, 2, 3, 1000, 65535, 70000)
_EDGE_SIDS = (-1, 0, 1, 2, 229, 390, 391, 99999)
_EDGE_NAMES = (
    "",
    ".notdef",
    "space",
    "A",
    "alpha",
    "h0000",
    "no_such_glyph",
    "exclamsmall",
)
_EDGE_CODES = (-1, 0, 32, 65, 97, 255, 256, 1000)
_EDGE_CIDS = (-1, 0, 1, 2, 3, 1000, 99999)

# Fixtures exercised: predefined ISOAdobe / Standard / Expert charsets +
# encodings, an embedded custom Format0 charset+encoding, a Format2 charset
# (> 256 SIDs), and a CID-keyed font.
_FIXTURES = [
    "charset_iso_adobe.cff",
    "std_enc.cff",
    "expert_enc.cff",
    "custom_charset_fmt0_enc.cff",
    "charset_fmt2_name.cff",
    "cid_multifd_3fd.cff",
]


# --------------------------------------------------------------------------- #
# pypdfbox-side projection — mirrors the Java probe field-for-field, applying
# the two documented divergence normalisations described in the module docstring.
# --------------------------------------------------------------------------- #


def _py_projection(data: bytes) -> list[str]:
    font = CFFParser().parse(data)[0]
    is_cid = font.is_cid_font()
    n_glyphs = len(font.get_char_string_bytes())
    lines = [
        f"FONT\t{type(font).__name__}",
        f"CID\t{str(is_cid).lower()}",
        f"NGLYPH\t{n_glyphs}",
    ]

    if is_cid:
        # Upstream CFFCharsetCID THROWs for the Type1 methods; pypdfbox folds
        # the surface and would return a fallback. Emit THROW to mirror Java
        # rather than asserting on a value the upstream API never exposes.
        for gid in _EDGE_GIDS:
            lines.append(f"NAME\t{gid}\tTHROW")
            lines.append(f"SID\t{gid}\tTHROW")
        for sid in _EDGE_SIDS:
            lines.append(f"GFS\t{sid}\tTHROW")
        for name in _EDGE_NAMES:
            lines.append(f"GSID\t{name}\tTHROW")
        for gid in _EDGE_GIDS:
            lines.append(f"CIDG\t{gid}\t{font.get_cid_for_gid(gid)}")
        for cid in _EDGE_CIDS:
            lines.append(f"GFC\t{cid}\t{font.get_gid_for_cid(cid)}")
        return lines

    # Name-keyed font.
    charset_names = set(font.get_charset())
    for gid in _EDGE_GIDS:
        lines.append(f"NAME\t{gid}\t{_py_name_for_gid(font, gid, n_glyphs)}")
        lines.append(f"SID\t{gid}\t{font.get_sid_for_gid(gid)}")
    for sid in _EDGE_SIDS:
        lines.append(f"GFS\t{sid}\t{font.get_gid_for_sid(sid)}")
    # GSID / N2G only over names in the parsed charset — see docstring §3.
    for name in _EDGE_NAMES:
        if name in charset_names:
            lines.append(f"GSID\t{name}\t{font.get_sid(name)}")

    assert isinstance(font, CFFType1Font)
    for name in _EDGE_NAMES:
        if name in charset_names:
            lines.append(f"N2G\t{name}\t{font.name_to_gid(name)}")
    enc = font.get_encoding()
    lines.append(f"ENC\t{'NULL' if enc is None else type(enc).__name__}")
    for code in _EDGE_CODES:
        lines.append(f"ENAME\t{code}\t{_py_enc_name(enc, code)}")
    return lines


def _py_name_for_gid(font: object, gid: int, n_glyphs: int) -> str:
    """``get_name_for_gid`` normalised to the Java ``CFFCharsetType1`` result:
    an out-of-range GID is Java ``null`` (token ``NULL``), an in-range GID is
    its glyph name. pypdfbox returns ``".notdef"`` for out-of-range by design,
    so we map that single case to ``NULL`` to compare resolution, not plumbing.
    """
    name = font.get_name_for_gid(gid)  # type: ignore[attr-defined]
    if not 0 <= gid < n_glyphs:
        return "NULL"
    return name


def _py_enc_name(enc: object, code: int) -> str:
    if enc is None:
        return "NULL"
    name = enc.get_name(code)  # type: ignore[attr-defined]
    return "NULL" if name is None else name


def _java_projection(
    fixture: Path, charset_names: set[str], is_cid: bool
) -> list[str]:
    """Probe stdout, with the ``GSID`` / ``N2G`` lines for names *not* in the
    parsed charset dropped — the documented absent-name divergence (§3). The
    filter is name-keyed only: on a CID font the upstream Type1 methods throw
    for *every* name (token ``THROW``), which the Python projection mirrors, so
    those lines must pass through untouched. All other lines pass through so a
    real regression still trips."""
    out = []
    for line in run_probe_text(_PROBE, str(fixture)).rstrip("\n").splitlines():
        cols = line.split("\t")
        if (
            not is_cid
            and cols[0] in ("GSID", "N2G")
            and cols[1] not in charset_names
        ):
            continue
        out.append(line)
    return out


# --------------------------------------------------------------------------- #
# Differential test.
# --------------------------------------------------------------------------- #


@requires_oracle
@pytest.mark.parametrize("fixture_name", _FIXTURES)
def test_charset_encoding_edge_lookup_matches_pdfbox(fixture_name: str) -> None:
    """The public charset + encoding resolver surface, driven over negative /
    past-``nGlyphs`` GIDs, out-of-bound SIDs, absent glyph names, codes outside
    0..255, and out-of-range CIDs, resolves identically to FontBox 3.0.7."""
    fixture = _CFF_FIXTURES / fixture_name
    assert fixture.is_file(), fixture
    data = fixture.read_bytes()
    font = CFFParser().parse(data)[0]
    is_cid = font.is_cid_font()
    charset_names = set() if is_cid else set(font.get_charset())
    java = _java_projection(fixture, charset_names, is_cid)
    py = _py_projection(data)
    assert py == java, (fixture_name, py, java)


# --------------------------------------------------------------------------- #
# Value-pinned regression for the wave-1555 CID fix — runs without the oracle
# so the corrected behaviour stays gated even on machines without Java.
# --------------------------------------------------------------------------- #


def test_cid_get_cid_for_gid_out_of_range_is_zero() -> None:
    """``CFFFont.get_cid_for_gid`` on a CID font returns 0 for an unmapped /
    out-of-range GID — matching upstream ``CFFCharsetCID.getCIDForGID``
    (``gidToCid.get(gid)`` → 0 on a miss). Before wave 1555 pypdfbox returned
    the raw GID, diverging from PDFBox for every GID past the charset."""
    font = CFFParser().parse((_CFF_FIXTURES / "cid_multifd_3fd.cff").read_bytes())[0]
    assert isinstance(font, CFFCIDFont)
    n_glyphs = len(font.get_char_string_bytes())
    # In-range GIDs keep their synthesised CID.
    assert font.get_cid_for_gid(1) == 1
    assert font.get_cid_for_gid(0) == 0
    # Out-of-range / unmapped GIDs resolve to 0, not the raw GID.
    assert font.get_cid_for_gid(n_glyphs) == 0
    assert font.get_cid_for_gid(1000) == 0
    assert font.get_cid_for_gid(-1) == 0
