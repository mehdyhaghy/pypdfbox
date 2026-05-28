"""Live PDFBox differential parity for EMBEDDED CMap stream parsing.

This complements ``test_predefined_cmap_oracle.py`` /
``test_predefined_cmap_type0_oracle.py`` (which load predefined CMaps by
*name* via ``CMapParser.parsePredefined``) by driving the other entry point:
``CMapParser.parse(RandomAccessRead)`` over a *raw embedded CMap byte stream*
— the bytes that would live in a PDF ``/Encoding`` CMap stream or a CIDFont's
embedded CMap. It pins the surfaces a predefined-by-name probe never touches:

* **begincodespacerange variable-byte detection** on a *mixed-width* codespace
  (a 1-byte ``<00>..<80>`` band interleaved with two disjoint 2-byte bands
  ``<8140>..<9FFC>`` and ``<E040>..<FBFC>``). The ``SWEEP`` lines record, for
  every leading byte, how many bytes ``CMap.readCode`` commits to — exactly the
  ISO 32000-1 §9.7.6.2 byte-length disambiguation. A trailing ``0x40`` probe
  byte sits inside the low-byte band of the 2-byte ranges so the boundary is
  observable; the run-length-compressed sweep reveals the 1/2/1/2/1 partition.
* **begincidrange / begincidchar** code->CID mapping (both the incrementing
  range form and the single-char form), including a single-byte cidchar so the
  per-length ``codeToCid`` dicts are exercised on more than one byte width.
* **usecmap inheritance** — a stream that does ``/Identity-H usecmap`` then
  overrides one code; the inherited identity mapping must surface for the
  un-overridden codes and the override must win for ``<0041>``.
* a **ToUnicode-style** ``/CMapType 2`` stream with ``beginbfchar`` /
  ``beginbfrange`` and no CID data — ``toCID`` must return ``0`` for every code.

The oracle output is produced by ``oracle/probes/EmbeddedCMapProbe.java``:

    NAME <cmapName>
    WMODE <wmode>
    SWEEP <leadingByteHex> len=<n>     (only at readCode-length run boundaries)
    CID <codeHex> -> <cid> len=<n>

The Python side reconstructs the identical line format from
``CMapParser().parse(...)`` so any divergence in tokenization, codespace
partitioning, CID mapping, or usecmap folding surfaces as a single differing
line.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap.cmap import CMap
from pypdfbox.fontbox.cmap.cmap_parser import CMapParser
from pypdfbox.io import RandomAccessReadBuffer
from tests.oracle.harness import requires_oracle, run_probe_text

# ---- embedded CMap streams (exactly the bytes the probe receives) ----

_MIXED_WIDTH = b"""%!PS-Adobe-3.0 Resource-CMap
/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CMapName /Test-Embedded def
/CMapType 1 def
/WMode 0 def
1 begincodespacerange
<00> <80>
endcodespacerange
2 begincodespacerange
<8140> <9FFC>
<E040> <FBFC>
endcodespacerange
2 begincidrange
<8140> <817E> 633
<E040> <E07E> 7479
endcidrange
1 begincidchar
<20> 1
endcidchar
2 begincidchar
<8240> 5000
endcidchar
endcmap
end
end
"""

_USECMAP = b"""%!PS-Adobe-3.0 Resource-CMap
/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CMapName /Test-UseCMap def
/CMapType 1 def
/Identity-H usecmap
1 begincidchar
<0041> 999
endcidchar
endcmap
end
end
"""

_TOUNICODE = b"""/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CMapName /Test-ToUnicode def
/CMapType 2 def
1 begincodespacerange
<0000> <FFFF>
endcodespacerange
2 beginbfchar
<0001> <0041>
<0002> <0042>
endbfchar
1 beginbfrange
<0010> <0012> <0061>
endbfrange
endcmap
end
end
"""

# stream bytes -> probe codes
_CASES: dict[str, tuple[bytes, list[str]]] = {
    "mixed_width": (
        _MIXED_WIDTH,
        ["20", "41", "80", "8140", "817E", "8240", "E040", "E07E", "9FFC", "FFFF"],
    ),
    "usecmap": (_USECMAP, ["0041", "0042", "FFFF", "0000"]),
    "tounicode": (_TOUNICODE, ["0001", "0002", "0010", "0011", "0012", "0013"]),
}


def _to_int(data: bytes) -> int:
    code = 0
    for b in data:
        code = (code << 8) | (b & 0xFF)
    return code


def _read_len(cmap: CMap, code: bytes) -> int:
    """Bytes consumed by ``CMap.read_code`` — the bytes-form returns
    ``(code, length)``; ``length`` is what the Java ``InputStream`` form
    reports as ``before - after available``."""
    _, length = cmap.read_code(code, 0)
    return length


def _py_lines(stream: bytes, codes: list[str]) -> list[str]:
    cmap = CMapParser().parse(RandomAccessReadBuffer(stream))
    lines = [f"NAME {cmap.get_name()}", f"WMODE {cmap.get_wmode()}"]

    # Codespace byte-length sweep: identical 0x40-padded probe per leading
    # byte, run-length-compressed to the boundaries (mirrors the probe).
    prev_len = -1
    for lead in range(0x100):
        probe = bytes([lead, 0x40])
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
def test_embedded_cmap_parse_matches_pdfbox(case: str) -> None:
    """pypdfbox's ``CMapParser.parse`` over a raw embedded CMap stream must
    equal Apache PDFBox's for codespace byte-length disambiguation,
    begincidrange/begincidchar CID mapping, usecmap inheritance, and a
    ToUnicode (CMapType 2) stream with no CID data.
    """
    stream, codes = _CASES[case]
    java = run_probe_text(
        "EmbeddedCMapProbe", stream.hex(), *codes
    ).splitlines()
    py = _py_lines(stream, codes)
    assert py == java, (
        f"embedded-CMap parity broken for {case}:\n"
        f"  JAVA: {java}\n  PY:   {py}"
    )
