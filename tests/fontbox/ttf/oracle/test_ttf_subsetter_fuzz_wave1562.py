"""Differential TrueType *subsetter-driver* fuzz vs Apache FontBox 3.0.7 (wave 1562).

Where the existing subset oracles drive subsetting *through the PDF font layer*
— ``SubsetProbe`` / ``SubsetEmbedProbe`` read a pypdfbox-produced embedded
subset back through PDFBox's own loaders, and ``TtfSubsetTagProbe`` checks the
PDF /BaseFont subset-tag invariant end-to-end — THIS wave drives the
``org.apache.fontbox.ttf.TTFSubsetter`` *driver itself* over a battery of
glyph-selection cases and compares the rebuilt subset's shape directly:

* glyph-id *selection*: ``add_glyph_ids`` / ``add`` (Unicode) registration,
* composite-glyph *closure* — a single accented glyph pulls in its base + mark
  components (e.g. U+00E1 a-acute -> {a, acute, aacute}),
* the ``new_gid -> old_gid`` *remapping* table (:meth:`TTFSubsetter.get_gid_map`),
* which SFNT *tables* survive (glyf/loca/cmap/hmtx/post/head/maxp/hhea/name),
* the rebuilt subset's *numGlyphs* (maxp of the round-tripped font).

The Java side is ``oracle/probes/TtfSubsetterFuzzProbe.java`` — it calls the
same public surface (``addGlyphIds`` / ``add`` / ``setPrefix`` / ``getGIDMap``
/ ``writeToStream``), reparses the emitted subset through ``TTFParser`` and
emits the identical tab-delimited projection.

Both fixtures (``DejaVuSansMono.ttf`` numGlyphs=3115, ``LiberationSans-Regular.ttf``
numGlyphs=2620) are real, well-formed TTFs already in the repo.

TWO arms.

* ``_AGREE`` — selections where BOTH the ported Python driver and FontBox 3.0.7
  rebuild the IDENTICAL projection (gid map + numGlyphs + table presence). The
  composite-closure case is the headline: gid map ``0:0,1:68,2:118,3:163`` is
  byte-identical across engines.

* DIVERGE (pinned BOTH-SIDES with honest comments):
  1. **out-of-range GID** — registering a gid ``>= numGlyphs``. Upstream
     FontBox 3.0.7 THROWS ``ArrayIndexOutOfBoundsException`` from
     ``getGIDMap()`` (its ``glyf``-indexed walk runs off the array end);
     pypdfbox deliberately DROPS the bogus gid (the "ignore unmapped input"
     doctrine) so the remaining valid selection still produces a structurally
     valid subset. Pinned both ways.
  2. **set_prefix '+' separator** — upstream ``setPrefix("ABCDEF")`` prepends
     the raw tag WITHOUT a separator (its embedder passes ``tag + "+"``), so
     the rebuilt PostScript name is ``ABCDEFDejaVuSansMono``. pypdfbox's
     ``set_prefix("ABCDEF")`` injects the ``+`` itself (its callers pass the
     bare 6-letter tag), yielding ``ABCDEF+DejaVuSansMono`` — the PDF-correct
     /BaseFont form (already validated end-to-end by ``TtfSubsetTagProbe``).
     The standalone-method contract differs; pinned both ways.

REAL BUG FIXED THIS WAVE (``ttf_subsetter.py``): an out-of-range raw GID
(``gid >= numGlyphs`` or ``gid < 0``) registered via ``add_glyph_ids`` used to
survive into ``get_gid_map()`` (returning a map naming a glyph the rebuilt
``loca``/``glyf`` can't back) and then crash ``to_bytes()`` with fontTools'
``MissingGlyphsSubsettingError`` — an exception outside the documented
``OSError``/``EOFError`` contract, so callers couldn't catch it. The driver now
filters out-of-range gids centrally (new ``_resolve_old_gids`` /
``_in_range_gids`` helpers shared by ``get_gid_map`` / ``get_new_glyph_id`` /
``add_compound_references`` and the flush path), so the three gid-resolution
methods are self-consistent and an out-of-range gid degrades to "ignored"
rather than a late uncatchable crash (case ``oob_gid_dropped`` pins the fix).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.ttf_parser import TTFParser
from pypdfbox.fontbox.ttf.ttf_subsetter import TTFSubsetter
from tests.oracle.harness import requires_oracle

_REPO_ROOT = Path(__file__).resolve().parents[4]
_ORACLE = _REPO_ROOT / "oracle"
_JARS_DIR = _ORACLE / "jars"
_PROBES = _ORACLE / "probes"
_BUILD = _ORACLE / "build"
_FIXTURES = _REPO_ROOT / "tests" / "fixtures" / "fontbox" / "ttf"
_DEJAVU = _FIXTURES / "DejaVuSansMono.ttf"
_LIBERATION = _FIXTURES / "LiberationSans-Regular.ttf"

_PROBED_TABLES = ("glyf", "loca", "cmap", "hmtx", "post", "head", "maxp", "hhea", "name")


def _classpath() -> str:
    jars = sorted(str(p) for p in _JARS_DIR.glob("*.jar"))
    return os.pathsep.join([*jars, str(_BUILD)])


def _run_probe(*args: str) -> str:
    src = _PROBES / "TtfSubsetterFuzzProbe.java"
    cls = _BUILD / "TtfSubsetterFuzzProbe.class"
    if not cls.is_file() or cls.stat().st_mtime < src.stat().st_mtime:
        _BUILD.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["javac", "-cp", _classpath(), "-d", str(_BUILD), str(src)],
            check=True,
            capture_output=True,
        )
    result = subprocess.run(
        ["java", "-cp", _classpath(), "TtfSubsetterFuzzProbe", *args],
        check=True,
        capture_output=True,
    )
    return result.stdout.decode("utf-8")


# ---------------------------------------------------------------------------
# Python projection — mirror the probe's structural lines (SRCGLYPHS / GIDMAP /
# NUMGLYPHS / TABLE), excluding the PREFIXED line (covered by the prefix
# divergence test) and the err bucket (covered separately).
# ---------------------------------------------------------------------------
def _build_subsetter(
    ttf_path: Path, mode: str, payload: object, prefix: str | None
) -> TTFSubsetter:
    font = TTFParser().parse(str(ttf_path))
    sub = TTFSubsetter(font)
    if prefix is not None:
        sub.set_prefix(prefix)
    if mode == "empty":
        pass
    elif mode == "notdef":
        sub.add_glyph_ids([0])
    elif mode == "gids":
        sub.add_glyph_ids(payload)  # type: ignore[arg-type]
    elif mode == "uni":
        for cp in payload:  # type: ignore[union-attr]
            sub.add(int(cp))
    else:
        raise AssertionError(mode)
    return sub


def _py_projection(ttf_path: Path, mode: str, payload: object, prefix: str | None) -> str:
    font = TTFParser().parse(str(ttf_path))
    src_glyphs = font.get_number_of_glyphs()
    sub = _build_subsetter(ttf_path, mode, payload, prefix)
    gid_map = sub.get_gid_map()  # new_gid -> old_gid
    mb = ",".join(f"{new}:{old}" for new, old in sorted(gid_map.items()))
    subset_bytes = sub.to_bytes()
    rebuilt = TTFParser().parse(subset_bytes)
    lines = [
        f"SRCGLYPHS\t{src_glyphs}",
        f"GIDMAP\t{mb}",
        f"NUMGLYPHS\t{rebuilt.get_number_of_glyphs()}",
    ]
    present = set(rebuilt.get_table_map().keys())
    for tag in _PROBED_TABLES:
        lines.append(f"TABLE\t{tag}\t{str(tag in present).lower()}")
    return "\n".join(lines)


def _filter_probe(out: str) -> str:
    """Keep only the structural lines the Python projection emits."""
    keep = []
    for line in out.splitlines():
        head = line.split("\t", 1)[0]
        if head in ("SRCGLYPHS", "GIDMAP", "NUMGLYPHS", "TABLE"):
            keep.append(line)
    return "\n".join(keep)


# ===========================================================================
# AGREE matrix — (name, fixture, probe-mode-args, mode, payload, prefix,
#                 expected projection pinned from FontBox 3.0.7)
# ===========================================================================
def _tables_block() -> str:
    return "\n".join(f"TABLE\t{t}\ttrue" for t in _PROBED_TABLES)


_AGREE: list[tuple[str, Path, list[str], str, object, str | None, str]] = [
    (
        "empty_minimal",
        _DEJAVU,
        [str(_DEJAVU), "empty"],
        "empty",
        None,
        None,
        f"SRCGLYPHS\t3115\nGIDMAP\t0:0\nNUMGLYPHS\t1\n{_tables_block()}",
    ),
    (
        "notdef_only",
        _DEJAVU,
        [str(_DEJAVU), "notdef"],
        "notdef",
        None,
        None,
        f"SRCGLYPHS\t3115\nGIDMAP\t0:0\nNUMGLYPHS\t1\n{_tables_block()}",
    ),
    (
        "single_gid",
        _DEJAVU,
        [str(_DEJAVU), "gids", "3"],
        "gids",
        [3],
        None,
        f"SRCGLYPHS\t3115\nGIDMAP\t0:0,1:3\nNUMGLYPHS\t2\n{_tables_block()}",
    ),
    (
        "multi_gid_with_notdef",
        _DEJAVU,
        [str(_DEJAVU), "gids", "0,3,5"],
        "gids",
        [0, 3, 5],
        None,
        f"SRCGLYPHS\t3115\nGIDMAP\t0:0,1:3,2:5\nNUMGLYPHS\t3\n{_tables_block()}",
    ),
    (
        "unicode_A",
        _LIBERATION,
        [str(_LIBERATION), "uni", "65"],
        "uni",
        [65],
        None,
        f"SRCGLYPHS\t2620\nGIDMAP\t0:0,1:36\nNUMGLYPHS\t2\n{_tables_block()}",
    ),
    (
        "composite_closure_aacute",
        _LIBERATION,
        [str(_LIBERATION), "uni", "225"],
        "uni",
        [225],
        None,
        # U+00E1 a-acute is composite -> base 'a' (68) + 'acute' (118) pulled in.
        f"SRCGLYPHS\t2620\nGIDMAP\t0:0,1:68,2:118,3:163\nNUMGLYPHS\t4\n{_tables_block()}",
    ),
    (
        "unmapped_codepoint",
        _LIBERATION,
        [str(_LIBERATION), "uni", "57344"],
        "uni",
        [57344],
        None,
        # U+E000 PUA has no glyph -> contributes nothing; subset = {.notdef}.
        f"SRCGLYPHS\t2620\nGIDMAP\t0:0\nNUMGLYPHS\t1\n{_tables_block()}",
    ),
    (
        "prefixed_structure_unchanged",
        _DEJAVU,
        [str(_DEJAVU), "prefix", "ABCDEF", "gids", "3,5"],
        "gids",
        [3, 5],
        "ABCDEF",
        # set_prefix doesn't touch the glyph selection / gid map / table set;
        # only the name table's PostScript record (asserted separately).
        f"SRCGLYPHS\t3115\nGIDMAP\t0:0,1:3,2:5\nNUMGLYPHS\t3\n{_tables_block()}",
    ),
]


@pytest.mark.parametrize(
    ("name", "fixture", "args", "mode", "payload", "prefix", "expected"),
    _AGREE,
    ids=[c[0] for c in _AGREE],
)
def test_python_matches_pinned_3_0_7(
    name: str,
    fixture: Path,
    args: list[str],
    mode: str,
    payload: object,
    prefix: str | None,
    expected: str,
) -> None:
    """pypdfbox's subset driver matches the projection pinned from FontBox 3.0.7."""
    assert _py_projection(fixture, mode, payload, prefix) == expected


@requires_oracle
@pytest.mark.parametrize(
    ("name", "fixture", "args", "mode", "payload", "prefix", "expected"),
    _AGREE,
    ids=[c[0] for c in _AGREE],
)
def test_python_matches_live_oracle(
    name: str,
    fixture: Path,
    args: list[str],
    mode: str,
    payload: object,
    prefix: str | None,
    expected: str,
) -> None:
    """pypdfbox's subset driver matches the LIVE FontBox 3.0.7 oracle."""
    java = _filter_probe(_run_probe(*args))
    py = _py_projection(fixture, mode, payload, prefix)
    assert py == java, f"{name}: py={py!r} java={java!r}"
    # And the pinned expectation matches the live oracle too.
    assert java == expected


# ===========================================================================
# DIVERGE 1 — out-of-range GID. Upstream THROWS; pypdfbox DROPS the bogus gid.
# This is the wave's bug fix: out-of-range gids no longer crash to_bytes() or
# pollute get_gid_map(); they degrade to "ignored".
# ===========================================================================
def test_out_of_range_gid_dropped_python() -> None:
    """pypdfbox drops a gid >= numGlyphs (and a negative gid) and still
    rebuilds a valid subset from the remaining selection (BUG FIX)."""
    font = TTFParser().parse(str(_DEJAVU))
    n = font.get_number_of_glyphs()
    sub = TTFSubsetter(font)
    sub.add_glyph_ids([3, -1, n + 50, n + 100])
    # get_gid_map names only valid glyphs (.notdef + gid 3); no bogus entry.
    assert sub.get_gid_map() == {0: 0, 1: 3}
    # get_new_glyph_id is consistent with the cleaned map.
    assert sub.get_new_glyph_id(3) == 1
    # to_bytes no longer raises MissingGlyphsSubsettingError.
    rebuilt = TTFParser().parse(sub.to_bytes())
    assert rebuilt.get_number_of_glyphs() == 2

    # A selection that is ONLY out-of-range degrades to the .notdef subset.
    only_bogus = TTFSubsetter(font)
    only_bogus.add_glyph_ids([n + 5])
    assert only_bogus.get_gid_map() == {0: 0}
    assert TTFParser().parse(only_bogus.to_bytes()).get_number_of_glyphs() == 1


@requires_oracle
def test_out_of_range_gid_diverges_java_throws() -> None:
    """FontBox 3.0.7 THROWS on a gid >= numGlyphs; pypdfbox survives.

    Pinned BOTH-SIDES: the live oracle reports ERR while pypdfbox rebuilds a
    valid subset, so a future change to either side trips this test.
    """
    font = TTFParser().parse(str(_DEJAVU))
    n = font.get_number_of_glyphs()
    java = _run_probe(str(_DEJAVU), "gids", str(n + 50)).strip()
    assert "ERR\tArrayIndexOutOfBoundsException" in java, java
    # pypdfbox does NOT throw — it drops the bogus gid.
    sub = TTFSubsetter(font)
    sub.add_glyph_ids([n + 50])
    assert sub.get_gid_map() == {0: 0}
    assert TTFParser().parse(sub.to_bytes()).get_number_of_glyphs() == 1


# ===========================================================================
# DIVERGE 2 — set_prefix '+' separator. Upstream prepends the raw tag (no '+');
# pypdfbox injects the '+'. Pinned BOTH-SIDES.
# ===========================================================================
def test_set_prefix_injects_separator_python() -> None:
    """pypdfbox's set_prefix('ABCDEF') yields the PDF-correct 'ABCDEF+Name'."""
    font = TTFParser().parse(str(_DEJAVU))
    sub = TTFSubsetter(font)
    sub.set_prefix("ABCDEF")
    sub.add_glyph_ids([3, 5])
    rebuilt = TTFParser().parse(sub.to_bytes())
    assert rebuilt.get_name() == "ABCDEF+DejaVuSansMono"


@requires_oracle
def test_set_prefix_no_separator_java() -> None:
    """FontBox 3.0.7 setPrefix('ABCDEF') prepends the RAW tag (no '+'),
    so getName() is 'ABCDEFDejaVuSansMono' — its embedder passes tag+'+'.

    Pinned BOTH-SIDES: the probe's PREFIXED line (which requires a '+') reports
    NONE for the upstream output but pypdfbox's name carries the '+', so the
    standalone-method contracts genuinely differ.
    """
    java = _run_probe(str(_DEJAVU), "prefix", "ABCDEF", "gids", "3,5")
    prefixed = next(
        (ln for ln in java.splitlines() if ln.startswith("PREFIXED")), "PREFIXED\t?"
    )
    # Upstream getName() == 'ABCDEFDejaVuSansMono' -> no '+' -> probe says NONE.
    assert prefixed == "PREFIXED\tNONE", prefixed
    # pypdfbox, by contrast, produces the '+'-separated name.
    font = TTFParser().parse(str(_DEJAVU))
    sub = TTFSubsetter(font)
    sub.set_prefix("ABCDEF")
    sub.add_glyph_ids([3, 5])
    assert TTFParser().parse(sub.to_bytes()).get_name() == "ABCDEF+DejaVuSansMono"
