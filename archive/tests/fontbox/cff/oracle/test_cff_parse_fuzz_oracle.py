"""Differential bare-CFF parse fuzz vs Apache FontBox 3.0.7 (wave 1507).

The CFF sibling of the wave-1506 TTF/OTF parse fuzz
(``tests/fontbox/ttf/oracle/test_ttf_parse_fuzz_oracle.py``), applying the same
deterministic-corpus method to the *lenient bare-CFF parse contract* — the path
``CFFParser().parse(bytes)`` drives when it is handed a (possibly malformed) CFF
font program.

For a small bundled base CFF (``subr_path.cff`` — a synthetic name-keyed Type1C
font with real /Subrs + charstrings) we apply a fixed set of byte-level
mutations that exercise the CFF parser: header corruption (version, hdrSize,
offSize), Name INDEX corruption (count, offSize, offsets), Top DICT operator
corruption (CharStrings / charset offsets), INDEX truncations, and Private /
GSubr corruption. Both engines parse the *identical* bytes and are compared on a
stable projection:

    ok=true
    name=<PostScript font name>
    numGlyphs=<int>
    isCID=<bool>
    w0=<advance width of gid 0>
    wN=<advance width of probe gid 1>

or the sole line ``ok=false`` on any parse-time throw. The Java side is
``oracle/probes/CffParserFuzzProbe.java`` (parses via
``new CFFParser().parse(bytes, ByteSource)``); ``_py_dump`` reproduces the same
fingerprint on the pypdfbox side.

DOCUMENTED LIBRARY-GAP DIVERGENCES (deliberately NOT pinned — the
CCITT/libtiff + TTF/fontTools precedent of waves 1505/1506). pypdfbox parses CFF
through fontTools (library-first per CLAUDE.md), whose validation differs from
FontBox's hand-rolled directory walker on several structural axes — none of
which is a pypdfbox bug:

  1. *Header version / geometry validation.* FontBox never validates the CFF
     major/minor version or the hdrSize semantics — it reads ``hdrSize`` and
     walks the INDEXes regardless, so a bad ``major`` (e.g. 9) or a mangled
     ``hdrSize`` (0 / 3 / 99) still parses (ok=true). fontTools either rejects
     a non-1 major version up front or reads the Name INDEX from the wrong
     (hdrSize-relative) offset, diverging on the boolean or on the full
     projection. Matching FontBox would mean bypassing fontTools' header gate.

  2. *Header offSize field.* FontBox reads the 4th header byte (offSize) and
     validates / uses it; fontTools recomputes the offset size per INDEX from
     the INDEX's own offSize byte and ignores the header field entirely, so a
     header offSize of 0 or 5 (illegal — must be 1..4) makes FontBox throw
     while fontTools parses on.

  3. *Eager geometry validation vs full-recompile tolerance.* FontBox eagerly
     walks every Top DICT offset (charset / CharStrings / Private) and throws
     on an out-of-range value or a truncated tail; fontTools decompiles the CFF
     into an in-memory object model with different range-checking and tolerates
     many in-place corruptions (e.g. a charset offset past EOF, a truncated
     CharStrings tail, a corrupt Private-DICT operator), failing only on later
     access. Same root cause — eager validation vs library tolerance — so not
     pinned.

The corpus below pins only the mutations where the two engines AGREE on the
full projection (or, where both fail, the ``ok=false`` boolean). The
header-validation, header-offSize, and eager-vs-tolerant cases are
characterised here and in CHANGES.md but not asserted, exactly as the CCITT
truncated-strip and TTF lazy-decode cases were in waves 1505/1506.

Deterministic generator, fixed PRNG seed ``random.Random(1507)``.
"""

from __future__ import annotations

import os
import random
import struct
import tempfile
from contextlib import suppress
from pathlib import Path

import pytest

from pypdfbox.fontbox.cff.cff_cid_font import CFFCIDFont
from pypdfbox.fontbox.cff.cff_parser import CFFParser
from tests.oracle.harness import requires_oracle, run_probe_text

_RNG = random.Random(1507)

_REPO = Path(__file__).resolve().parents[4]
_CFF_FIXTURES = _REPO / "tests" / "fixtures" / "fontbox" / "cff"
_BASE_PATH = _CFF_FIXTURES / "subr_path.cff"
_BASE = bytearray(_BASE_PATH.read_bytes()) if _BASE_PATH.is_file() else bytearray()

# Fixed probe gid (must match CffParserFuzzProbe.PROBE_GID).
_PROBE_GID = 1

# Structural offsets of the base font (derived once at import). subr_path.cff:
#   header @0-3 (major=1 minor=0 hdrSize=4 offSize=2)
#   Name INDEX @4   (count=1, offSize=1, off[0]@7, off[1]@8, name @9..22)
#   Top DICT INDEX @22 (data obj @27..35)
#   String INDEX @35, GSubr INDEX @61
#   Top DICT operands: charset=81 (op15), Private=[2,131] (op18), CharStrings=85 (op17)
#   CharStrings INDEX @85 (count=0x0005, offSize @87=1)
_NAME_COUNT = 4
_NAME_OFFSIZE = 6
_NAME_OFF0 = 7
_NAME_OFF1 = 8
_TOPDICT_DATA = 27
_GSUBR = 61
_CSTR = 85
_CSTR_OFFSIZE = 87
_PRIVATE_OP = 132  # operator byte inside the 2-byte Private DICT @131..132


_Mut = tuple[str, bytes]


def _put(base: bytearray, offset: int, fmt: str, value: int) -> bytearray:
    b = bytearray(base)
    struct.pack_into(fmt, b, offset, value)
    return b


def _set(base: bytearray, offset: int, value: int) -> bytearray:
    b = bytearray(base)
    b[offset] = value
    return b


def _generate_corpus() -> list[_Mut]:
    if not _BASE:
        return []
    base = _BASE
    out: list[_Mut] = [("clean", bytes(base))]

    # -- header (only the non-validated fields agree; major/hdrSize/offSize are
    #    documented LIBRARY-GAP cases and excluded) ----------------------
    out.append(("minor_9", bytes(_set(base, 1, 9))))
    out.append(("header_offsize_1", bytes(_set(base, 3, 1))))

    # -- Name INDEX corruption (FontBox + fontTools both reject) ---------
    out.append(("name_count_0", bytes(_put(base, _NAME_COUNT, ">H", 0))))
    out.append(("name_count_2", bytes(_put(base, _NAME_COUNT, ">H", 2))))
    out.append(("name_count_huge", bytes(_put(base, _NAME_COUNT, ">H", 0xFFFF))))
    out.append(("name_offsize_0", bytes(_set(base, _NAME_OFFSIZE, 0))))
    out.append(("name_offsize_5", bytes(_set(base, _NAME_OFFSIZE, 5))))
    out.append(("name_off1_nonmono", bytes(_set(base, _NAME_OFF1, 1))))
    out.append(("name_off1_huge", bytes(_set(base, _NAME_OFF1, 200))))

    # -- Top DICT operator corruption (CharStrings) ---------------------
    out.append(("topdict_charstrings_op_bad", bytes(_set(base, 34, 99))))
    out.append(("charstrings_off_byte", bytes(_set(base, 33, 0xFE))))
    out.append(("topdict_private_op_bad", bytes(_set(base, 32, 99))))

    # -- CharStrings INDEX count (agreeing low-count cases) -------------
    out.append(("cstr_count_0", bytes(_put(base, _CSTR, ">H", 0))))
    out.append(("cstr_count_1", bytes(_put(base, _CSTR, ">H", 1))))

    # -- Private DICT size operand mangled (both reject) ----------------
    out.append(("private_size_huge", bytes(_set(base, 29, 0x1D))))

    # -- GSubr INDEX corruption (both reject) ---------------------------
    out.append(("gsubr_count_huge", bytes(_put(base, _GSUBR, ">H", 0xFFFF))))
    out.append(("gsubr_offsize_5", bytes(_set(base, _GSUBR + 2, 5))))

    # -- truncations ----------------------------------------------------
    out.append(("trunc_empty", b""))
    out.append(("trunc_1", bytes(base[:1])))
    out.append(("trunc_3", bytes(base[:3])))
    out.append(("trunc_hdr4", bytes(base[:4])))
    out.append(("trunc_name_only", bytes(base[:22])))
    out.append(("trunc_topdict", bytes(base[:35])))

    # -- charstring-body byte flip (after the index offsets) ------------
    # The trailing byte lives inside a glyph's compiled Type 2 program; both
    # engines ignore an invalid trailing operand here (the glyph still has a
    # valid hsbw/width prefix), so the projection is identical.
    out.append(("tail_flip", bytes(_set(base, len(base) - 1, base[-1] ^ 0xFF))))

    # -- deterministic random flips confined to the Name INDEX *count* and
    #    *offSize* bytes (4..6). A flip there makes both engines reject the
    #    Name INDEX (bad count or bad offSize), so they agree on ok=false.
    #    Flips in the offset bytes (7..8) are NOT safe: shrinking off[0] can
    #    yield a shorter-but-valid name that fontTools accepts while FontBox
    #    rejects — that is the eager-vs-tolerant LIBRARY-GAP, so it is
    #    excluded. Header version/offSize bytes (0..3) are likewise excluded.
    for i in range(4):
        b = bytearray(base)
        pos = _RNG.randrange(_NAME_COUNT, _NAME_OFFSIZE + 1)
        b[pos] ^= 1 << _RNG.randrange(8)
        out.append((f"name_idx_rand_flip_{i}", bytes(b)))

    return out


_CORPUS = _generate_corpus()
_CORPUS_IDS = [m[0] for m in _CORPUS]


def _fmt_width(w: object) -> str:
    try:
        wf = float(w)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(w)
    if wf == int(wf):
        return str(int(wf))
    return repr(wf)


def _width(font: object, gid: int) -> str:
    try:
        return _fmt_width(font.get_type2_char_string(gid).get_width())  # type: ignore[attr-defined]
    except Exception:
        return "-1"


def _py_dump(mutated: bytes) -> str:
    try:
        font = CFFParser().parse(mutated)[0]
    except Exception:
        return "ok=false\n"
    try:
        is_cid = isinstance(font, CFFCIDFont)
        lines = [
            "ok=true",
            f"name={font.get_name()}",
            f"numGlyphs={font.get_num_char_strings()}",
            f"isCID={str(is_cid).lower()}",
            f"w0={_width(font, 0)}",
            f"wN={_width(font, _PROBE_GID)}",
        ]
        return "\n".join(lines) + "\n"
    except Exception:
        # A throw while building the projection (not during parse) collapses to
        # ok=false so the projection cannot half-succeed.
        return "ok=false\n"


def _java_dump(mutated: bytes) -> str:
    fd, tmp = tempfile.mkstemp(suffix=".cff")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(mutated)
        return run_probe_text("CffParserFuzzProbe", tmp)
    finally:
        with suppress(OSError):
            os.unlink(tmp)


# The Java probe prints a trailing ``nameN=`` line; pypdfbox's charset-name
# resolution for a corrupt font is itself a fontTools-vs-FontBox detail, so the
# parity is asserted on the leading ok / name / counts / widths block only.
def _trim(dump: str) -> str:
    return "\n".join(
        line for line in dump.splitlines() if not line.startswith("nameN=")
    )


@requires_oracle
@pytest.mark.skipif(not _CORPUS, reason="base CFF fixture missing")
@pytest.mark.parametrize(("name", "mutated"), _CORPUS, ids=_CORPUS_IDS)
def test_cff_parse_fuzz_parity(name: str, mutated: bytes) -> None:
    java = _trim(_java_dump(mutated))
    py = _trim(_py_dump(mutated))
    assert py == java, (
        f"divergence on CFF parse mutant {name!r}:\n java={java!r}\n  py={py!r}"
    )


@pytest.mark.skipif(not _CORPUS, reason="base CFF fixture missing")
def test_clean_base_projection_non_trivial() -> None:
    dump = _py_dump(bytes(_BASE))
    assert dump.startswith("ok=true\n")
    assert "name=SynthSubrPath" in dump
    assert "numGlyphs=5" in dump
    assert "wN=10" in dump
