"""Live PDFBox differential parity for the GPOS (Glyph Positioning) table parse
contract under malformed input (``oracle/probes/GposTableFuzzProbe.java``,
wave 1534).

The load-bearing fact: Apache FontBox 3.0.7 has **no** ``GlyphPositioningTable``
class. ``TTFParser.readTableDirectory`` only instantiates a typed table for
cmap / glyf / head / hhea / hmtx / loca / maxp / name / OS-2 / post / DSIG /
kern / vhea / vmtx / VORG / GSUB. The ``GPOS`` tag falls through to a generic,
never-decoded :class:`TTFTable` holding only tag / offset / length. FontBox is
therefore completely **insensitive** to GPOS-internal corruption — a wrong
version, an out-of-bounds ScriptList / FeatureList / LookupList offset, a
truncated header, a huge lookup count, a version-1.1 featureVariations field, or
zero lookups all parse without complaint and without ever throwing. The only way
GPOS leaves the table map is the table-directory "Skip table" path (entry
offset/length runs past the file).

pypdfbox delegates GPOS decoding to fontTools, which *does* lazily decompile the
table. Wave 1534's real fix: :class:`GlyphPositioningTable` previously let raw
fontTools decode exceptions (``struct.error`` / ``AssertionError`` / ...) escape
from ``populate_from_fonttools`` and the structural accessors when the GPOS body
was corrupt — i.e. pypdfbox *threw* where FontBox silently succeeds. The wrapper
now swallows those fontTools decode errors and degrades a present-but-corrupt
GPOS to an empty (but present) inventory, restoring the FontBox contract.

Each case splices a hostile GPOS body into a canonical SFNT (DejaVuSans
re-serialised through fontTools) and feeds the *same* file to both the Java probe
and the pypdfbox reproducer; any divergence surfaces as a single differing line.

DOCUMENTED LIBRARY-GAP (pinned elsewhere, not re-fixed here):
the table-directory "Skip table" cases (GPOS entry length 0 or offset past EOF)
are where FontBox drops GPOS from the map (``hasGPOS=false``) but pypdfbox/
fontTools keeps it. That divergence is the PDFBOX-5285 past-EOF directory guard
already documented in ``test_ttf_parse_fuzz_oracle.py`` (the TTFParser surface),
so those two cases are excluded from this GPOS-internal module.
"""

from __future__ import annotations

import io
import os
import struct
import tempfile
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.ttf_parser import TTFParser
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from tests.oracle.harness import requires_oracle, run_probe_text

_TTF_DIR = Path(__file__).resolve().parents[4] / "pypdfbox" / "resources" / "ttf"


# --------------------------------------------------------------------------- #
# SFNT helpers — locate + mutate the GPOS table body in a canonical font.
# --------------------------------------------------------------------------- #
def _base_font() -> bytes:
    """Re-serialise DejaVuSans through fontTools to get a canonical SFNT."""
    from fontTools.ttLib import TTFont  # noqa: PLC0415

    tt = TTFont(io.BytesIO((_TTF_DIR / "DejaVuSans.ttf").read_bytes()))
    try:
        buf = io.BytesIO()
        tt.save(buf)
        return buf.getvalue()
    finally:
        tt.close()


def _gpos_dir_entry(raw: bytes) -> tuple[int, int, int]:
    """Return ``(dir_entry_offset, table_offset, table_length)`` for GPOS."""
    num_tables = struct.unpack(">H", raw[4:6])[0]
    off = 12
    for _ in range(num_tables):
        tag = raw[off : off + 4]
        _csum, toff, tlen = struct.unpack(">III", raw[off + 4 : off + 16])
        if tag == b"GPOS":
            return off, toff, tlen
        off += 16
    raise AssertionError("base font has no GPOS table")


def _splice(mutator) -> bytes:
    raw = bytearray(_base_font())
    dir_off, tab_off, tab_len = _gpos_dir_entry(raw)
    mutator(raw, dir_off, tab_off, tab_len)
    return bytes(raw)


# --------------------------------------------------------------------------- #
# Hostile mutators — each corrupts the GPOS *body* (not the directory entry).
# --------------------------------------------------------------------------- #
def _m_baseline(b, d, p, length):  # noqa: ARG001
    pass


def _m_bad_major(b, d, p, length):  # noqa: ARG001
    b[p : p + 2] = struct.pack(">H", 0x0009)


def _m_version_1_1(b, d, p, length):  # noqa: ARG001
    b[p + 2 : p + 4] = struct.pack(">H", 1)


def _m_scriptlist_oob(b, d, p, length):  # noqa: ARG001
    b[p + 4 : p + 6] = struct.pack(">H", 0xFFFF)


def _m_featurelist_oob(b, d, p, length):  # noqa: ARG001
    b[p + 6 : p + 8] = struct.pack(">H", 0xFFFF)


def _m_lookuplist_oob(b, d, p, length):  # noqa: ARG001
    b[p + 8 : p + 10] = struct.pack(">H", 0xFFFF)


def _m_zero_header(b, d, p, length):  # noqa: ARG001
    for i in range(min(length, 10)):
        b[p + i] = 0


def _m_trunc_body(b, d, p, length):
    """Keep the directory entry in-bounds but shrink the readable body to 2
    bytes (the rest of the table file region is left intact so the directory
    offset/length stays valid; only the GPOS *content* is too short to decode).
    """
    b[d + 12 : d + 16] = struct.pack(">I", 2)


# CASES: short id -> mutator. IDs are short (no byte blobs) to stay under the
# Windows 32 KB test-id env-var cap.
_CASES = {
    "baseline": _m_baseline,
    "bad_major": _m_bad_major,
    "version_1_1": _m_version_1_1,
    "scriptlist_oob": _m_scriptlist_oob,
    "featurelist_oob": _m_featurelist_oob,
    "lookuplist_oob": _m_lookuplist_oob,
    "zero_header": _m_zero_header,
    "trunc_body": _m_trunc_body,
}


# --------------------------------------------------------------------------- #
# pypdfbox reproducer — fingerprint mirroring GposTableFuzzProbe.
# --------------------------------------------------------------------------- #
def _py_fingerprint(data: bytes, *, embedded: bool) -> str:
    """Reproduce the Java probe's projection on the pypdfbox side.

    The probe prints ``hasGPOS`` (presence in the table map), ``gposClass``
    (always the generic ``TTFTable`` upstream — a present GPOS is never decoded)
    and ``gposInit`` (always ``false`` upstream — the generic table is never
    read). pypdfbox carries no generic ``TTFTable`` placeholder per tag; a GPOS
    that is present-but-corrupt is exposed through :meth:`get_gpos`, which must
    NOT raise (the wave-1534 contract). We therefore project the *same* upstream
    constants for the present case and additionally require that exercising the
    GPOS accessors never throws.
    """
    try:
        font = TTFParser(embedded).parse(RandomAccessReadBuffer(data))
    except Exception:  # noqa: BLE001 - mirror probe's ok=false on any throw
        return "ok=false\n"

    has_gpos = "GPOS" in font.get_table_map()
    lines = ["ok=true", f"hasGPOS={str(has_gpos).lower()}"]
    if not has_gpos:
        lines += ["gposClass=-", "gposInit=-"]
        return "\n".join(lines) + "\n"

    # Present: exercise the full GPOS accessor surface; none may raise even on
    # a corrupt body (that is exactly the bug wave 1534 fixed).
    gpos = font.get_gpos()
    assert gpos is not None
    gpos.get_supported_script_tags()
    gpos.get_supported_feature_tags()
    gpos.get_lookup_count()
    gpos.get_lookup_types()
    gpos.get_script_list()
    gpos.get_feature_list()
    gpos.get_lookup_list()
    gpos.get_lookup(0)
    gpos.get_lookup_subtables(0)
    gpos.get_feature_record(0)
    gpos.get_lookup_indices_for_feature("kern")
    gpos.has_kerning()
    gpos.get_kerning(0, 1)

    # Mirror the upstream generic-table constants for the present case.
    lines += ["gposClass=TTFTable", "gposInit=false"]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
@requires_oracle
@pytest.mark.parametrize("case", list(_CASES), ids=list(_CASES))
@pytest.mark.parametrize("embedded", [False, True], ids=["strict", "embedded"])
def test_gpos_table_fuzz_matches_pdfbox(case: str, embedded: bool) -> None:
    data = _splice(_CASES[case])
    arm = ["embedded"] if embedded else []

    fd, path = tempfile.mkstemp(suffix=".ttf")
    os.close(fd)
    try:
        Path(path).write_bytes(data)
        java = run_probe_text("GposTableFuzzProbe", path, *arm)
    finally:
        os.unlink(path)

    py = _py_fingerprint(data, embedded=embedded)
    assert py == java, f"GPOS fuzz divergence ({case}, embedded={embedded})"


@requires_oracle
@pytest.mark.parametrize("case", list(_CASES), ids=list(_CASES))
def test_gpos_accessors_never_raise(case: str) -> None:
    """Standalone guard for the wave-1534 fix: every GPOS accessor must
    degrade gracefully on a corrupt body rather than leak a fontTools decode
    exception (the regression this wave closed)."""
    data = _splice(_CASES[case])
    font = TTFParser(False).parse(RandomAccessReadBuffer(data))
    if "GPOS" not in font.get_table_map():
        pytest.skip("GPOS dropped at the directory level for this case")
    gpos = font.get_gpos()
    assert gpos is not None
    # None of these may raise on any malformed body.
    assert isinstance(gpos.get_supported_script_tags(), set)
    assert isinstance(gpos.get_supported_feature_tags(), list)
    assert isinstance(gpos.get_lookup_count(), int)
    assert isinstance(gpos.get_lookup_types(), list)
    assert isinstance(gpos.get_lookup_indices_for_feature("kern"), list)
    assert isinstance(gpos.has_kerning(), bool)
    assert gpos.get_kerning(0, 1) == 0 or isinstance(gpos.get_kerning(0, 1), int)
    assert gpos.get_kerning(-1, 5) == 0
