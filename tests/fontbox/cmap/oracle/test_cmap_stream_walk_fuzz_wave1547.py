"""Live Apache PDFBox differential STREAM-WALK fuzz for the embedded-CMap
parser + ``CMap.readCode(InputStream)`` decode loop, wave 1547.

Prior cmap parse-fuzz waves (1508 ``CMapParseFuzzProbe``, the codespace sweep
``CMapCodespaceProbe``) feed each probe code to an *isolated* buffer and look it
up once. This wave drives ``CMap.readCode`` repeatedly over a SINGLE multi-code
byte STREAM until EOF and projects the sequence of ``(code, bytesConsumed,
cid)`` tuples — the angle that catches:

* **codespace partitioning across boundaries** — a 1-byte code immediately
  followed by a 2-byte code in the same stream;
* **the no-match rewind** — upstream ``readCode`` marks the stream after the
  initial ``minCodeLength`` bytes, reads up to ``maxCodeLength`` looking for a
  matching codespace range, and ``in.reset()``s back to ``minCodeLength`` when
  none matches, so the *next* code starts at the right offset. pypdfbox's
  ``_read_code_from_stream`` originally consumed the speculatively-read
  extension bytes (no rewind), which mis-aligned every subsequent code in a
  walk over codes that fall outside the codespace. Fixed in wave 1547 (see
  CHANGES.md) by pushing back the extension bytes via ``rewind`` — this test
  pins the corrected both-sides contract;
* **variable-byte length detection driven by malformed codespace declarations**
  — mismatched lo/hi byte lengths, overlapping 1-/2-byte bands, reversed
  (lo>hi) codespace and cidrange entries, range counts larger than the entries
  provided, ``usecmap`` of a missing CMap, ``WMode`` outside {0,1}, surrogate /
  multi-byte bf destinations, and odd-length / wrong-byte-count bf dst tokens.

Projection (matching ``oracle/probes/CMapStreamWalkFuzzProbe.java`` verbatim)::

    ok=false                              (sole line on any parse-time throw)
  -- or --
    ok=true
    name=<cmapName>
    wmode=<wmode>
    cscount=<number of codespace ranges>
    minlen=<minCodeLength> maxlen=<maxCodeLength>
    STEP <codeHexBigEndian> consumed=<n> cid=<cid>   (one per readCode)
    END consumed=<total bytes consumed>

This probe is intentionally a NEW file rather than an edit of the wave-1508
``CMapParseFuzzProbe.java`` (which a concurrent test still depends on for the
single-lookup projection).
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox.fontbox.cmap.cmap_parser import CMapParser
from pypdfbox.io import RandomAccessReadBuffer
from tests.oracle.harness import requires_oracle, run_probe_text

# A 2-band mixed-width CID CMap (Adobe-Japan1 shape): 0x00..0x80 is 1 byte,
# 0x8140..0x9FFC is 2 bytes.
_CID_BASE = b"""%!PS-Adobe-3.0
begincmap
/CMapName /WalkTest def
/CMapType 1 def
/WMode 0 def
/Registry (Adobe) def
/Ordering (Japan1) def
/Supplement 0 def
2 begincodespacerange
<00> <80>
<8140> <9FFC>
endcodespacerange
2 begincidchar
<20> 1
<8140> 633
endcidchar
1 begincidrange
<8141> <817E> 634
endcidrange
endcmap
end
"""

# A single 2-byte codespace ToUnicode CMap.
_UCS = b"""%!PS-Adobe-3.0 Resource-CMap
begincmap
/CMapName /WalkUcs def
/CMapType 2 def
/WMode 0 def
/Registry (Adobe) def
/Ordering (UCS) def
/Supplement 0 def
1 begincodespacerange
<0000> <FFFF>
endcodespacerange
2 beginbfchar
<0041> <0041>
<0042> <0042>
endbfchar
endcmap
end
"""

# Walk blobs probed against each CMap (a heterogeneous stream of codes that
# span 1- and 2-byte bands, plus bytes that match NO codespace).
_WALK_CID = "20814041FF208200817E"
_WALK_UCS = "004100428000FFFF41"


def _mutants() -> dict[str, tuple[bytes, str]]:
    """(cmap source, walk-hex) pairs. Deterministic, seed-free."""
    m: dict[str, tuple[bytes, str]] = {}

    # ---- valid baselines (negative controls) ----
    m["cid_base"] = (_CID_BASE, _WALK_CID)
    m["ucs_base"] = (_UCS, _WALK_UCS)

    # ---- codespace: mismatched lo/hi byte lengths ----
    # PDFBOX-4923: <00> <FFFF> widens lo to two bytes (accepted).
    m["cs_len_mismatch_00"] = (
        _UCS.replace(b"<0000> <FFFF>", b"<00> <FFFF>"), _WALK_UCS
    )
    # Non-zero short lo paired with long hi -> ValueError -> parse throws.
    m["cs_len_mismatch_nz"] = (
        _UCS.replace(b"<0000> <FFFF>", b"<10> <FFFF>"), _WALK_UCS
    )

    # ---- codespace: overlapping 1- and 2-byte bands ----
    # 0x81 leads BOTH a 1-byte (<00><FF>) and a 2-byte (<8140><9FFC>) band;
    # readCode must commit to the SHORTEST (1-byte) match.
    m["cs_overlap"] = (
        _CID_BASE.replace(b"<00> <80>", b"<00> <FF>"), _WALK_CID
    )

    # ---- codespace: reversed (lo > hi) ----
    m["cs_reversed"] = (
        _CID_BASE.replace(b"<8140> <9FFC>", b"<9FFC> <8140>"), _WALK_CID
    )

    # ---- codespace: declared count larger than entries provided ----
    m["cs_overcount"] = (
        _CID_BASE.replace(b"2 begincodespacerange", b"5 begincodespacerange"),
        _WALK_CID,
    )
    m["cs_undercount"] = (
        _CID_BASE.replace(b"2 begincodespacerange", b"1 begincodespacerange"),
        _WALK_CID,
    )

    # ---- codespace: multi-byte code spanning a boundary in the walk ----
    # Walk includes 0x8200 (leading byte 0x82 within the 2-byte band's lo..hi
    # leading-byte range but the low byte 0x00 < 0x40 so it is NOT a full match)
    m["cs_partial_match"] = (_CID_BASE, "82008140")

    # ---- cidrange: lo > hi ----
    m["cidrange_reversed"] = (
        _CID_BASE.replace(b"<8141> <817E> 634", b"<817E> <8141> 634"), _WALK_CID
    )
    # ---- cidrange: differing lengths -> parse throws ----
    m["cidrange_difflen"] = (
        _CID_BASE.replace(b"<8141> <817E> 634", b"<41> <817E> 634"), _WALK_CID
    )

    # ---- bfchar: odd-length / wrong-byte-count dst ----
    m["bf_odd_dst"] = (_UCS.replace(b"<0041> <0041>", b"<0041> <041>"), _WALK_UCS)
    m["bf_empty_dst"] = (_UCS.replace(b"<0041> <0041>", b"<0041> <>"), _WALK_UCS)
    m["bf_three_byte_dst"] = (
        _UCS.replace(b"<0041> <0041>", b"<0041> <01F600>"), _WALK_UCS
    )

    # ---- bfchar / count larger than entries provided ----
    m["bf_overcount"] = (_UCS.replace(b"2 beginbfchar", b"9 beginbfchar"), _WALK_UCS)

    # ---- surrogate-pair bf destination ----
    m["bf_surrogate"] = (
        _UCS.replace(b"<0041> <0041>", b"<0041> <D83DDE00>"), _WALK_UCS
    )

    # ---- usecmap of a missing CMap ----
    m["usecmap_missing"] = (
        _CID_BASE.replace(b"begincmap\n", b"begincmap\n/NoSuchCMap usecmap\n"),
        _WALK_CID,
    )

    # ---- WMode outside {0, 1} ----
    m["wmode_2"] = (_CID_BASE.replace(b"/WMode 0 def", b"/WMode 2 def"), _WALK_CID)
    m["wmode_neg"] = (_CID_BASE.replace(b"/WMode 0 def", b"/WMode -1 def"), _WALK_CID)

    # ---- walk entirely outside the codespace ----
    m["walk_all_miss"] = (_CID_BASE, "FFFEFD")
    m["walk_ucs_miss_then_hit"] = (_UCS, "FF000041")

    # ---- truncated walk tail (last code shorter than minCodeLength) ----
    m["walk_trunc_tail"] = (_UCS, "004100")  # last single byte < 2-byte min

    # ---- no codespace at all (constructor defaults min=4 max=0) ----
    m["no_codespace"] = (
        b"%!PS-Adobe-3.0\nbegincmap\n/CMapName /Empty def\nendcmap\nend\n",
        "00410042",
    )

    return m


_MUTANTS = _mutants()

# Blobs with NO codespace range parsed -> ``CMap`` keeps the constructor
# defaults (minCodeLength=4, maxCodeLength=0). Upstream ``readCode`` then does
# ``new byte[0]`` + ``read(buf, 0, 4)`` which throws on a ByteArrayInputStream
# (probe emits "STEP throw"), while pypdfbox deliberately hardens this path to
# read one byte at a time (pinned by ``test_cmap.test_empty_cmap_read_code_
# reads_one_byte_without_crashing`` + wave 1508). The header projection still
# agrees, so we assert header parity for these and pin the documented walk
# divergence explicitly. (Same root cause as wave 1508's ``_NO_CODESPACE_CASES``.)
_NO_CODESPACE_CASES = {"no_codespace"}


def _py_lines(stream: bytes, walk_hex: str) -> list[str]:
    """Reconstruct the probe projection from pypdfbox for one blob."""
    try:
        cmap = CMapParser().parse(RandomAccessReadBuffer(stream))
    except Exception:
        return ["ok=false"]
    lines = [
        "ok=true",
        f"name={cmap.get_name()}",
        f"wmode={cmap.get_wmode()}",
        f"cscount={len(cmap.get_codespace_ranges())}",
        f"minlen={cmap.get_min_code_length()} maxlen={cmap.get_max_code_length()}",
    ]
    walk = bytes.fromhex(walk_hex)
    ras = RandomAccessReadBuffer(walk)
    total = 0
    guard = 0
    while ras.available() > 0 and guard < 4096:
        guard += 1
        before = ras.available()
        try:
            code = cmap.read_code(ras)
            cid = cmap.to_cid(code)
        except Exception:
            lines.append("STEP throw")
            break
        consumed = before - ras.available()
        total += consumed
        lines.append(f"STEP {code:X} consumed={consumed} cid={cid}")
        if consumed <= 0:
            break
    lines.append(f"END consumed={total}")
    return lines


@requires_oracle
@pytest.mark.parametrize("name", list(_MUTANTS))
def test_cmap_stream_walk_fuzz_matches_pdfbox(name: str) -> None:
    """pypdfbox ``CMapParser.parse`` + a ``readCode`` stream-walk projection
    (code / bytes-consumed / CID per step) must equal Apache PDFBox 3.0.7 on
    every mutant."""
    # Silence the "Invalid character code sequence" warnings the no-match cases
    # emit on both sides (the projection only compares values, not log lines).
    logging.disable(logging.CRITICAL)
    try:
        stream, walk_hex = _MUTANTS[name]
        java = run_probe_text(
            "CMapStreamWalkFuzzProbe", stream.hex(), walk_hex
        ).splitlines()
        py = _py_lines(stream, walk_hex)
    finally:
        logging.disable(logging.NOTSET)

    if name in _NO_CODESPACE_CASES:
        # Documented intentional divergence: header parity holds, but the walk
        # diverges because upstream readCode throws on a no-codespace CMap while
        # pypdfbox reads one byte (see _NO_CODESPACE_CASES above + CHANGES.md).
        assert py[:5] == java[:5], (
            f"no-codespace header parity broken for {name}:\n"
            f"  JAVA: {java}\n  PY:   {py}"
        )
        assert "STEP throw" in java, java
        assert any(ln.startswith("STEP ") and "throw" not in ln for ln in py), py
        return

    assert py == java, (
        f"cmap stream-walk fuzz parity broken for {name}:\n"
        f"  JAVA: {java}\n  PY:   {py}"
    )


@requires_oracle
def test_no_match_rewind_documented_contract() -> None:
    """Pin the root-cause both-sides contract directly: when a stream-walk hits
    a code outside every codespace range, upstream ``readCode`` reads up to
    ``maxCodeLength`` then ``in.reset()``s back to ``minCodeLength`` (so the
    next code re-aligns). pypdfbox was hardened in wave 1547 to push the
    speculatively-read extension bytes back via ``rewind``; before the fix it
    consumed all ``maxCodeLength`` bytes, mis-aligning the rest of the walk.
    """
    # 0xFF leads no band; the 2-byte band needs 0x81..0x9F, so readCode extends
    # to 2 bytes, misses, and must rewind 1 byte -> consume exactly 1 (minlen).
    java = run_probe_text("CMapStreamWalkFuzzProbe", _CID_BASE.hex(), "FF20").splitlines()
    assert "ok=true" in java
    # Two single-byte steps: 0xFF (miss, consume 1) then 0x20 (hit, consume 1).
    assert any(ln == "STEP FF consumed=1 cid=0" for ln in java), java
    assert any(ln == "STEP 20 consumed=1 cid=1" for ln in java), java
    assert "END consumed=2" in java

    logging.disable(logging.CRITICAL)
    try:
        py = _py_lines(_CID_BASE, "FF20")
    finally:
        logging.disable(logging.NOTSET)
    assert py == java, f"JAVA: {java}\nPY:   {py}"
