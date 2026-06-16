"""Differential fuzz of CFF *subset projection* against the live Apache PDFBox
3.0.7 oracle.

**Why a projection and not a real subset round-trip.** Apache PDFBox 3.0.7
ships no public CFF subset-embed builder: ``PDType0Font.subset()`` handles only
``/CIDFontType2`` (TrueType ``glyf``) and rejects a CFF descendant
(``/CIDFontType0``). pypdfbox mirrors that exactly — ``PDType0Font.subset()``
raises ``ValueError`` for a non-CIDFontType2 descendant (see
``pypdfbox/pdmodel/font/pd_type0_font.py``). So there is no PDFBox API that
emits subset CFF bytes to byte-diff against.

The honest differential target is therefore the set of *facts a CFF subsetter
must compute* from a parsed CFF — the primitives both engines expose
identically:

* the kept-glyph set after the canonical subset rule (.notdef/GID 0 always
  retained, out-of-range GIDs dropped, duplicates collapsed, sorted ascending);
* the resulting charstring count of the subset;
* the GID remapping old->new (kept GIDs renumbered 0..k-1 in ascending order —
  the canonical glyph-order subset);
* the charset glyph name at each new GID (for non-CID fonts);
* whether the source font is CID-keyed.

These come from ``CFFFont.getNumCharStrings()`` /
``CFFCharset.getNameForGID(gid)`` on the Java side and
``CFFFont.get_num_char_strings()`` / ``CFFFont.get_name_for_gid(gid)`` on the
Python side — the same primitives a real subsetter walks — so pypdfbox's
projection is diffed line-for-line against the probe
``CffSubsetterFuzzProbe`` on identical fixtures.

Honest divergence pinned here (both sides):

* **CID-keyed glyph names.** For a CID-keyed CFF, PDFBox's ``CFFCharsetCID``
  overrides ``getNameForGID`` to throw ``IllegalStateException`` (CID fonts
  carry CIDs, not glyph names). pypdfbox's ``get_name_for_gid`` instead
  synthesises ``"cidNNNNN"`` / ``".notdef"`` names (used by downstream metric
  lookups). The charstring count and GID remapping are identical across both
  engines for CID fonts; only the per-GID *name* projection diverges, so the
  oracle compares CASE/MAP lines for the CID fixture but pins the GNAME
  behaviour separately on each side.

When the live oracle is unavailable the value-based assertions still run
against expected values transcribed from PDFBox 3.0.7's verified probe output.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.fontbox.cff.cff_parser import CFFParser
from tests.oracle.harness import oracle_available, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "fontbox" / "cff"

# Mirror of CffSubsetterFuzzProbe.CASES (name -> requested raw GID set). The
# subset rule forces GID 0 in, drops GIDs >= numGlyphs, resolves small negative
# values "from the end" (-1 => last gid), and treats <= -100 as "full set".
_CASES: dict[str, list[int]] = {
    "empty": [],
    "notdef_only": [0],
    "single_g1": [1],
    "single_high": [2],
    "pair": [1, 2],
    "triple": [1, 2, 3],
    "with_dups": [1, 1, 2, 2, 2],
    "unsorted": [3, 1, 2],
    "zero_and_more": [0, 1, 2],
    "gid_past_count": [1, 999999],
    "all_oob": [500000, 600000],
    "negative_dropped": [-1, 1],
    "near_count_minus1": [-1],
    "near_count": [-2],
    "spread": [1, 5, 10, 20],
    "full_set": [-100],
}

# Fixtures fuzzed. cid_multifd_subr is CID-keyed (drives the GNAME divergence).
_FONT_FIXTURES = ["subr_path", "cid_multifd_subr", "charset_fmt1_name"]


def _project(requested: list[int], num_glyphs: int) -> list[int]:
    """Python mirror of CffSubsetterFuzzProbe.project — the canonical CFF
    subset rule applied to a raw requested GID set."""
    kept: set[int] = {0}  # .notdef always retained
    for g in requested:
        if g <= -100:
            kept.update(range(num_glyphs))
        elif g < 0:
            resolved = num_glyphs + g
            if 0 <= resolved < num_glyphs:
                kept.add(resolved)
        elif g < num_glyphs:
            kept.add(g)
        # g >= num_glyphs: dropped
    return sorted(kept)


def _load(fixture: str) -> object:
    data = (_FIXTURES / f"{fixture}.cff").read_bytes()
    return CFFParser().parse(data)[0]


def _py_lines(fixture: str) -> list[str]:
    """Build the same tab-delimited lines the probe emits, from pypdfbox.

    For CID-keyed fonts the GNAME lines are *omitted* (pypdfbox synthesises
    names where PDFBox throws — diffed separately), matching the probe which
    emits ERR for those cases.
    """
    font = _load(fixture)
    num_glyphs = int(font.get_num_char_strings())
    is_cid = bool(font.is_cid_font())
    lines = [f"FONT\t{num_glyphs}\t{str(is_cid).lower()}"]
    for name, requested in _CASES.items():
        kept = _project(requested, num_glyphs)
        lines.append(f"CASE\t{name}\t{len(kept)}")
        for new_gid, old_gid in enumerate(kept):
            lines.append(f"MAP\t{name}\t{old_gid}\t{new_gid}")
        if not is_cid:
            for new_gid in range(min(len(kept), 6)):
                old_gid = kept[new_gid]
                gname = font.get_name_for_gid(old_gid)
                lines.append(f"GNAME\t{name}\t{new_gid}\t{gname}")
    return lines


def _oracle_lines_filtered(fixture: str, is_cid: bool) -> list[str]:
    """Probe stdout, dropping ERR (CID GNAME failure) and GNAME lines for CID
    fonts so the comparison is on the engine-agnostic CASE/MAP/FONT facts."""
    raw = run_probe_text("CffSubsetterFuzzProbe", "project", str(_FIXTURES / f"{fixture}.cff"))
    out = []
    for line in raw.splitlines():
        if not line:
            continue
        if is_cid and (line.startswith("ERR\t") or line.startswith("GNAME\t")):
            continue
        out.append(line)
    return out


# ---------------------------------------------------------------------------
# Value-based assertions (always run) — transcribed from PDFBox 3.0.7 probe.
# ---------------------------------------------------------------------------


def test_projection_counts_subr_path() -> None:
    """subr_path: 5 glyphs, non-CID. Spot-check kept counts + remapping."""
    font = _load("subr_path")
    assert int(font.get_num_char_strings()) == 5
    assert not font.is_cid_font()
    assert _project(_CASES["empty"], 5) == [0]
    assert _project(_CASES["notdef_only"], 5) == [0]
    assert _project(_CASES["single_high"], 5) == [0, 2]
    # out-of-range positive GIDs dropped, .notdef kept
    assert _project(_CASES["gid_past_count"], 5) == [0, 1]
    assert _project(_CASES["all_oob"], 5) == [0]
    # -1 resolves to last gid (4); 1 kept
    assert _project(_CASES["negative_dropped"], 5) == [0, 1, 4]
    assert _project(_CASES["near_count_minus1"], 5) == [0, 4]
    assert _project(_CASES["near_count"], 5) == [0, 3]
    # spread {1,5,10,20}: only 1 in range
    assert _project(_CASES["spread"], 5) == [0, 1]
    # full_set sentinel selects every gid
    assert _project(_CASES["full_set"], 5) == [0, 1, 2, 3, 4]


def test_charset_names_subr_path() -> None:
    """Charset names at each GID match PDFBox getNameForGID exactly."""
    font = _load("subr_path")
    assert [font.get_name_for_gid(g) for g in range(5)] == [
        ".notdef",
        "Aloc",
        "Bglob",
        "Cnest",
        "Dmix",
    ]


def test_projection_charset_fmt1() -> None:
    """charset_fmt1_name: 9 glyphs, format-1 charset, non-CID."""
    font = _load("charset_fmt1_name")
    assert int(font.get_num_char_strings()) == 9
    assert not font.is_cid_font()
    assert [font.get_name_for_gid(g) for g in range(9)] == [
        ".notdef",
        "g000",
        "g001",
        "g002",
        "g003",
        "g004",
        "g005",
        "g006",
        "g007",
    ]
    # spread {1,5,10,20}: 1 and 5 in range
    assert _project(_CASES["spread"], 9) == [0, 1, 5]
    # full_set: all 9 gids
    assert _project(_CASES["full_set"], 9) == list(range(9))


def test_cid_keyed_count_and_remapping() -> None:
    """cid_multifd_subr: 4 glyphs, CID-keyed. Count + remapping match PDFBox;
    these are engine-agnostic (no glyph names involved)."""
    font = _load("cid_multifd_subr")
    assert int(font.get_num_char_strings()) == 4
    assert font.is_cid_font()
    assert _project(_CASES["full_set"], 4) == [0, 1, 2, 3]
    assert _project(_CASES["near_count_minus1"], 4) == [0, 3]
    # negative_dropped: -1 -> 3, plus 1
    assert _project(_CASES["negative_dropped"], 4) == [0, 1, 3]


def test_cid_keyed_name_divergence() -> None:
    """DIVERGENCE: PDFBox's CFFCharsetCID.getNameForGID throws
    IllegalStateException; pypdfbox synthesises cidNNNNN / .notdef names.

    pypdfbox side pinned here. The Java side throwing is asserted via the
    oracle test below when available, and documented in the probe (ERR lines).
    """
    font = _load("cid_multifd_subr")
    assert font.is_cid_font()
    assert font.get_name_for_gid(0) == ".notdef"
    assert font.get_name_for_gid(1) == "cid00001"
    assert font.get_name_for_gid(2) == "cid00002"
    assert font.get_name_for_gid(3) == "cid00003"


# ---------------------------------------------------------------------------
# Live differential oracle (skipped when the PDFBox jar / JDK is absent).
# ---------------------------------------------------------------------------


def test_oracle_projection_matches_pdfbox() -> None:
    if not oracle_available():
        import pytest

        pytest.skip("live PDFBox oracle unavailable")
    for fixture in _FONT_FIXTURES:
        font = _load(fixture)
        is_cid = bool(font.is_cid_font())
        py = _py_lines(fixture)
        java = _oracle_lines_filtered(fixture, is_cid)
        assert py == java, f"projection mismatch for {fixture}"


def test_oracle_cid_name_throws() -> None:
    """The Java oracle reports ERR (IllegalStateException) for every CID GNAME
    case — confirming the divergence pinned in test_cid_keyed_name_divergence."""
    if not oracle_available():
        import pytest

        pytest.skip("live PDFBox oracle unavailable")
    raw = run_probe_text(
        "CffSubsetterFuzzProbe", "project", str(_FIXTURES / "cid_multifd_subr.cff")
    )
    err_lines = [ln for ln in raw.splitlines() if ln.startswith("ERR\t")]
    # Every non-empty CASE attempts a GNAME and throws.
    assert err_lines, "expected ERR lines for CID-keyed getNameForGID"
    assert all(ln.endswith("IllegalStateException") for ln in err_lines)
    # No GNAME line should be emitted for the CID font.
    assert not any(ln.startswith("GNAME\t") for ln in raw.splitlines())
