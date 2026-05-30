"""Live PDFBox differential parity for variable-length code decoding driven by
codespace ranges of DIFFERENT byte widths in one embedded (stream) CMap.

Complements ``test_embedded_cmap_oracle.py``: that test uses *disjoint* 1-byte
and 2-byte codespace bands (the textbook CJK partition). This one stresses the
harder corners of the ISO 32000-1 §9.7.6.2 byte-length disambiguation that
``CMap.read_code`` / ``to_cid`` implement:

* **Overlapping widths.** A full 1-byte band ``<00>..<FF>`` registered
  *alongside* a 2-byte band ``<8140>..<9FFC>``. Every leading byte is then
  covered by both a 1-byte and a 2-byte codespace, so ``read_code`` must commit
  to the **shortest** match (1 byte) for every leading byte — it tests
  ``byte_count == min_code_length`` first and returns on the first match. The
  ``SWEEP`` lines pin that the whole 0x00..0xFF range decodes as len=1.
* **2-byte-only leading byte.** A second CMap drops the 1-byte band's coverage
  of the high bytes so the 0x81..0x9F leading bytes are reachable *only* via
  the 2-byte band — ``read_code`` must extend to 2 bytes there and stay at 1
  byte elsewhere, giving an observable 1/2/1 partition.
* **Cross-width CID collision.** ``begincidchar`` entries at *both* widths
  where the numeric code value collides (``<41>`` as a 1-byte char vs
  ``<0041>`` as a 2-byte char map to different CIDs). ``to_cid``'s
  ``min..max`` length sweep is then observably order-sensitive — it returns the
  shortest-length non-zero CID first.

Oracle output (``oracle/probes/CMapCodespaceProbe.java``)::

    NAME <cmapName>
    MINLEN <minCodeLength>
    MAXLEN <maxCodeLength>
    SWEEP <leadingByteHex> len=<n>     (only at readCode-length run boundaries)
    CID <codeHex> -> <cid> len=<n>

The Python side reconstructs the identical line format so any divergence in
codespace partitioning, shortest-match selection, or the ``to_cid`` length
sweep surfaces as a single differing line.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap.cmap import CMap
from pypdfbox.fontbox.cmap.cmap_parser import CMapParser
from pypdfbox.io import RandomAccessReadBuffer
from tests.oracle.harness import requires_oracle, run_probe_text

# A 1-byte band covering everything, plus a 2-byte band that overlaps it on
# the 0x81..0x9F leading bytes. Mixed-width CID data at both widths with a
# colliding numeric value (0x41).
_OVERLAP = b"""%!PS-Adobe-3.0 Resource-CMap
/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CMapName /Test-Overlap def
/CMapType 1 def
/WMode 0 def
1 begincodespacerange
<00> <FF>
endcodespacerange
1 begincodespacerange
<8140> <9FFC>
endcodespacerange
1 begincidrange
<8140> <817E> 1000
endcidrange
1 begincidchar
<41> 7
endcidchar
1 begincidchar
<0041> 8
endcidchar
endcmap
end
end
"""

# A 1-byte band that stops at 0x7F, plus a 2-byte band on 0x81..0x9F, so the
# 0x80 leading byte is covered by NEITHER and the high bytes are 2-byte-only.
# This yields a 1/2/fallback partition in the SWEEP.
_DISJOINT_GAP = b"""%!PS-Adobe-3.0 Resource-CMap
/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CMapName /Test-Gap def
/CMapType 1 def
/WMode 0 def
1 begincodespacerange
<00> <7F>
endcodespacerange
1 begincodespacerange
<8140> <9FFC>
endcodespacerange
2 begincidrange
<00> <7F> 100
<8140> <817E> 2000
endcidrange
endcmap
end
end
"""

# stream bytes -> probe codes (mix of 1- and 2-byte codes)
_CASES: dict[str, tuple[bytes, list[str]]] = {
    "overlap": (
        _OVERLAP,
        ["41", "0041", "8140", "817E", "9FFC", "00", "FF", "80"],
    ),
    "disjoint_gap": (
        _DISJOINT_GAP,
        ["00", "41", "7F", "80", "8140", "817E", "9FFC", "FF"],
    ),
}


def _to_int(data: bytes) -> int:
    code = 0
    for b in data:
        code = (code << 8) | (b & 0xFF)
    return code


def _read_len(cmap: CMap, code: bytes) -> int:
    _, length = cmap.read_code(code, 0)
    return length


def _py_lines(stream: bytes, codes: list[str]) -> list[str]:
    cmap = CMapParser().parse(RandomAccessReadBuffer(stream))
    lines = [
        f"NAME {cmap.get_name()}",
        f"MINLEN {cmap.get_min_code_length()}",
        f"MAXLEN {cmap.get_max_code_length()}",
    ]

    prev_len = -1
    for lead in range(0x100):
        probe = bytes([lead, 0x41])
        length = _read_len(cmap, probe)
        if length != prev_len:
            lines.append(f"SWEEP {lead:02X} len={length}")
            prev_len = length

    for hexcode in codes:
        data = bytes.fromhex(hexcode)
        cid = cmap.to_cid(_to_int(data))
        length = _read_len(cmap, data)
        lines.append(f"CID {hexcode.upper()} -> {cid} len={length}")
    return lines


@requires_oracle
@pytest.mark.parametrize("case", list(_CASES))
def test_cmap_codespace_decode_matches_pdfbox(case: str) -> None:
    """pypdfbox's variable-length code decoding (``read_code``) and CID
    resolution (``to_cid``) over codespace ranges of different byte widths must
    equal Apache PDFBox 3.0.7 — including overlapping-width shortest-match
    selection and the cross-width ``to_cid`` length sweep.
    """
    stream, codes = _CASES[case]
    java = run_probe_text("CMapCodespaceProbe", stream.hex(), *codes).splitlines()
    py = _py_lines(stream, codes)
    assert py == java, (
        f"cmap codespace-decode parity broken for {case}:\n"
        f"  JAVA: {java}\n  PY:   {py}"
    )
